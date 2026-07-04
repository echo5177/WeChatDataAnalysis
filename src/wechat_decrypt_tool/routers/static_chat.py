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

from typing import Literal, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from .. import static_archive_ai as ai
from .. import static_archive_store as store
from ..logging_config import get_logger
from ..media_helpers import _list_decrypted_accounts
from ..path_fix import PathFixRoute
from ..routers.chat import list_chat_messages

logger = get_logger(__name__)

router = APIRouter(route_class=PathFixRoute)

# Per-page fetch size when pulling from the live pipeline during import.
_IMPORT_PAGE_SIZE = 500
# Smaller page for incremental sync: usually only a few new messages exist, so a
# big page just wastes live-side parsing. Pages up if the delta is larger.
_INCREMENTAL_PAGE_SIZE = 120
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
    mode: Literal["auto", "full", "incremental"] = Field(
        "auto",
        description="auto=有断点则增量、无断点则全量；full=全量导入；incremental=仅取断点之后",
    )
    max_messages: int = Field(
        0,
        description="全量模式下最多导入多少条（<=0 表示尽量全部，受安全上限约束）；增量模式忽略",
    )


def _fetch_live_page(
    request: Request, account: str, username: str, offset: int, order: str, limit: int = _IMPORT_PAGE_SIZE
) -> list[dict]:
    try:
        resp = list_chat_messages(
            request,
            username=username,
            account=account,
            limit=limit,
            offset=offset,
            order=order,
        )
    except HTTPException:
        raise
    except Exception as e:  # pragma: no cover - defensive
        logger.exception("[static-import] live fetch failed: %s", e)
        raise HTTPException(status_code=500, detail=f"读取实时消息失败: {e}")
    if not isinstance(resp, dict):
        return []
    return list(resp.get("messages") or [])


def _fetch_full(request: Request, account: str, username: str, cap: int) -> list[dict]:
    """Import as much of the conversation as possible (asc pages, newest-first order)."""
    unbounded = cap <= 0
    collected: list[dict] = []
    offset = 0
    for _ in range(_IMPORT_MAX_PAGES):
        batch = _fetch_live_page(request, account, username, offset, "asc")
        if not batch:
            break
        collected.extend(batch)
        offset += _IMPORT_PAGE_SIZE
        if not unbounded and len(collected) >= cap:
            return collected[:cap]
        if len(batch) < _IMPORT_PAGE_SIZE:
            break
    return collected


def _fetch_incremental(request: Request, account: str, username: str, boundary: int) -> list[dict]:
    """Walk newest→older (desc pages) and stop once we pass the checkpoint time.

    Only messages with createTime >= boundary are collected; the boundary message
    itself is re-collected and deduped away on upsert, guaranteeing no gap for
    same-second messages.
    """
    collected: list[dict] = []
    offset = 0
    page = _INCREMENTAL_PAGE_SIZE
    for _ in range(_IMPORT_MAX_PAGES):
        batch = _fetch_live_page(request, account, username, offset, "desc", limit=page)
        if not batch:
            break
        reached_old = False
        for m in batch:
            if int(m.get("createTime") or 0) >= boundary:
                collected.append(m)
            else:
                reached_old = True
        if reached_old:
            break
        offset += page
        if len(batch) < page:
            break
    return collected


@router.post("/api/static/import", summary="从实时管线导入/刷新一个会话到静态归档")
def import_static_conversation(req: StaticImportRequest, request: Request):
    username = str(req.username or "").strip()
    if not username:
        raise HTTPException(status_code=400, detail="Missing username.")
    account = _resolve_account(req.account)

    # Register/refresh the conversation row first (so it shows up even if empty).
    store.upsert_conversation(account, username, name=req.name, is_group=req.is_group)

    checkpoint = store.get_checkpoint(account, username)
    boundary = int(checkpoint["lastCreateTime"]) if checkpoint else 0

    mode = req.mode
    if mode == "auto":
        mode = "incremental" if boundary > 0 else "full"

    if mode == "incremental":
        collected = _fetch_incremental(request, account, username, boundary)
    else:
        collected = _fetch_full(request, account, username, int(req.max_messages or 0))

    added = store.upsert_messages(account, username, collected)

    # Advance the checkpoint to the newest message we now hold (never move it backwards).
    cursor = store.compute_checkpoint_from_messages(collected)
    if cursor is not None and int(cursor["last_create_time"]) >= boundary:
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
        "mode": mode,
        "imported": len(collected),
        "added": added,
        "conversation": conv,
    }


# ---------------------------------------------------------------------------
# AI analysis (reads only the static archive)
# ---------------------------------------------------------------------------

@router.get("/api/static/ai/config", summary="AI 分析配置状态（是否已配置 LLM）")
async def get_static_ai_config():
    return {
        "status": "success",
        "configured": ai.is_configured(),
        "model": ai.effective_model(),
    }


@router.get("/api/static/ai/models", summary="列出可用的 LLM 模型（供下拉切换）")
async def list_static_ai_models():
    if not ai.is_configured():
        return {"status": "success", "configured": False, "models": [], "default": ""}
    return {
        "status": "success",
        "configured": True,
        "models": ai.list_models(),
        "default": ai.effective_model(),
    }


class StaticAiRequest(BaseModel):
    account: Optional[str] = Field(None, description="账号目录名（可选）")
    username: str = Field(..., description="会话 username")
    kind: Literal["summary", "profile"] = Field("summary", description="分析类型：summary 总结 / profile 用户画像")
    model: Optional[str] = Field(None, description="指定模型（可选，默认用环境变量 LLM_MODEL）")
    start_time: Optional[int] = Field(None, description="起始时间（Unix 秒，可选）")
    end_time: Optional[int] = Field(None, description="结束时间（Unix 秒，可选）")
    max_messages: int = Field(500, description="最多分析多少条（取该范围内最新的 N 条）")


@router.post("/api/static/ai/analyze", summary="对归档会话做 AI 分析（总结/用户画像）")
def analyze_static_conversation(req: StaticAiRequest):
    username = str(req.username or "").strip()
    if not username:
        raise HTTPException(status_code=400, detail="Missing username.")
    account = _resolve_account(req.account)
    if not ai.is_configured():
        raise HTTPException(
            status_code=400,
            detail="未配置 LLM。请设置环境变量 LLM_API_KEY（可选 LLM_BASE_URL / LLM_MODEL）后重启后端。",
        )

    conv = next((c for c in store.list_conversations(account) if c["username"] == username), None)
    conv_name = (conv or {}).get("name") or username

    kwargs = dict(
        start_time=int(req.start_time or 0),
        end_time=int(req.end_time or 0),
        max_messages=int(req.max_messages or 500),
        model=(str(req.model).strip() if req.model else None),
    )
    try:
        if req.kind == "profile":
            result = ai.profile_users(account, username, conv_name, **kwargs)
        else:
            result = ai.summarize_conversation(account, username, conv_name, **kwargs)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("[static-ai] analyze failed: %s", e)
        raise HTTPException(status_code=502, detail=f"LLM 调用失败: {e}")

    return {
        "status": "success",
        "kind": req.kind,
        "content": result["content"],
        "messages": result["messages"],
        "model": result.get("model", ""),
    }


@router.get("/api/static/ai/artifacts", summary="列出会话的历史 AI 分析产物")
async def list_static_ai_artifacts(username: str, account: Optional[str] = None, kind: Optional[str] = None):
    if not username:
        raise HTTPException(status_code=400, detail="Missing username.")
    account = _resolve_account(account)
    artifacts = store.list_ai_artifacts(account, username, kind=kind)
    return {"status": "success", "account": account, "username": username, "artifacts": artifacts}
