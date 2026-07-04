"""Static chat archive router (静态聊天记录).

Serves a *static*, locally-archived copy of chat records, decoupled from the
live decrypted WeChat databases. Data is imported on demand from the existing
``/api/chat/messages`` pipeline (reused verbatim, no duplication) and stored in
``static_archive.db`` via :mod:`static_archive_store`.

Endpoints:
- ``GET  /api/static/conversations``  list archived conversations
- ``GET  /api/static/messages``       read archived messages (mirrors /api/chat/messages shape)
- ``GET  /api/static/checkpoint``     read the per-conversation incremental cursor
- ``POST /api/static/import``         import/refresh a conversation from the live pipeline
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from .. import static_archive_store as store
from ..logging_config import get_logger
from ..media_helpers import _list_decrypted_accounts
from ..path_fix import PathFixRoute
from ..routers.chat import list_chat_messages

logger = get_logger(__name__)

router = APIRouter(route_class=PathFixRoute)

# Per-page fetch size when pulling from the live pipeline during import.
_IMPORT_PAGE_SIZE = 500
# Safety cap on pages so a runaway import can't loop forever.
_IMPORT_MAX_PAGES = 400


def _resolve_account(account: Optional[str]) -> str:
    """Resolve the account key. Archive reads don't require a decrypted account,
    but we default to the first decrypted one for parity with the rest of the app."""
    acc = str(account or "").strip()
    if acc:
        return acc
    accounts = _list_decrypted_accounts()
    if accounts:
        return accounts[0]
    raise HTTPException(status_code=404, detail="No account specified and no decrypted account found.")


@router.get("/api/static/conversations", summary="列出已归档的静态会话")
async def list_static_conversations(account: Optional[str] = None):
    acc = _resolve_account(account)
    conversations = store.list_conversations(acc)
    return {"status": "success", "account": acc, "conversations": conversations}


@router.get("/api/static/messages", summary="读取已归档的静态消息（形状同 /api/chat/messages）")
async def list_static_messages(
    username: str,
    account: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    order: str = "asc",
):
    if not username:
        raise HTTPException(status_code=400, detail="Missing username.")
    acc = _resolve_account(account)
    result = store.list_messages(acc, username, limit=limit, offset=offset)
    return {
        "status": "success",
        "account": acc,
        "username": username,
        "source": "static",
        "total": result["total"],
        "hasMore": result["hasMore"],
        "messages": result["messages"],
    }


@router.get("/api/static/checkpoint", summary="读取会话的增量断点")
async def get_static_checkpoint(username: str, account: Optional[str] = None):
    if not username:
        raise HTTPException(status_code=400, detail="Missing username.")
    acc = _resolve_account(account)
    checkpoint = store.get_checkpoint(acc, username)
    return {"status": "success", "account": acc, "username": username, "checkpoint": checkpoint}


class StaticImportRequest(BaseModel):
    account: Optional[str] = Field(None, description="账号目录名（可选，默认第一个已解密账号）")
    username: str = Field(..., description="要归档的会话 username")
    name: Optional[str] = Field(None, description="会话显示名（可选）")
    is_group: Optional[bool] = Field(None, description="是否群聊（可选，默认按 username 推断）")
    max_messages: int = Field(
        2000,
        description="本次最多导入多少条消息（<=0 表示尽量导入全部，受安全上限约束）",
    )


@router.post("/api/static/import", summary="从实时管线导入/刷新一个会话到静态归档")
def import_static_conversation(req: StaticImportRequest, request: Request):
    username = str(req.username or "").strip()
    if not username:
        raise HTTPException(status_code=400, detail="Missing username.")
    account = _resolve_account(req.account)

    # Register/refresh the conversation row first (so it shows up even if empty).
    store.upsert_conversation(
        account,
        username,
        name=req.name,
        is_group=req.is_group,
    )

    cap = int(req.max_messages or 0)
    unbounded = cap <= 0
    collected: list[dict] = []
    total_reported = 0
    offset = 0
    pages = 0

    while pages < _IMPORT_MAX_PAGES:
        pages += 1
        try:
            resp = list_chat_messages(
                request,
                username=username,
                account=account,
                limit=_IMPORT_PAGE_SIZE,
                offset=offset,
                order="asc",
            )
        except HTTPException:
            raise
        except Exception as e:  # pragma: no cover - defensive
            logger.exception("[static-import] live fetch failed: %s", e)
            raise HTTPException(status_code=500, detail=f"读取实时消息失败: {e}")

        batch = list(resp.get("messages") or []) if isinstance(resp, dict) else []
        total_reported = int(resp.get("total") or 0) if isinstance(resp, dict) else 0
        if not batch:
            break
        collected.extend(batch)
        offset += _IMPORT_PAGE_SIZE

        if not unbounded and len(collected) >= cap:
            collected = collected[:cap]
            break
        if total_reported and offset >= total_reported:
            break
        if len(batch) < _IMPORT_PAGE_SIZE:
            break

    added = store.upsert_messages(account, username, collected)

    # Advance the checkpoint to the newest message we now hold.
    cursor = store.compute_checkpoint_from_messages(collected)
    if cursor is not None:
        store.set_checkpoint(
            account,
            username,
            last_create_time=cursor["last_create_time"],
            last_server_id=cursor["last_server_id"],
            last_local_id=cursor["last_local_id"],
        )

    conversations = store.list_conversations(account)
    conv = next((c for c in conversations if c["username"] == username), None)

    return {
        "status": "success",
        "account": account,
        "username": username,
        "imported": len(collected),
        "added": added,
        "totalAvailable": total_reported,
        "capped": (not unbounded) and total_reported > cap,
        "conversation": conv,
    }
