"""Static chat archive store.

A self-contained SQLite database (`output/static_archive.db`) that holds a
*static* copy of chat records the user has explicitly archived, decoupled from
the live decrypted WeChat databases. This backs the "静态聊天记录" board:

- ``conversations``      one row per archived (account, username)
- ``messages``           raw message dicts (JSON) as returned by ``/api/chat/messages``
- ``sync_checkpoints``   per-conversation incremental cursor for "导出最新消息"
- ``ai_artifacts``       AI outputs (summaries / user profiles) — used by later milestones

The message payload is stored verbatim so it can be replayed into the existing
chat bubble components without re-deriving anything. Ordering/pagination mirrors
``/api/chat/messages`` (newest page first, ascending within a page).
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Optional

from .app_paths import get_output_dir
from .logging_config import get_logger

logger = get_logger(__name__)

_INIT_LOCK = threading.Lock()
_INITIALIZED_PATHS: set[str] = set()


def get_archive_db_path() -> Path:
    return get_output_dir() / "static_archive.db"


def _connect() -> sqlite3.Connection:
    path = get_archive_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def _ensure_initialized(conn: sqlite3.Connection) -> None:
    key = str(get_archive_db_path())
    if key in _INITIALIZED_PATHS:
        return
    with _INIT_LOCK:
        if key in _INITIALIZED_PATHS:
            return
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                account TEXT NOT NULL,
                username TEXT NOT NULL,
                name TEXT DEFAULT '',
                avatar TEXT DEFAULT '',
                is_group INTEGER DEFAULT 0,
                message_count INTEGER DEFAULT 0,
                first_time INTEGER DEFAULT 0,
                last_time INTEGER DEFAULT 0,
                updated_at INTEGER DEFAULT 0,
                PRIMARY KEY (account, username)
            );

            CREATE TABLE IF NOT EXISTS messages (
                account TEXT NOT NULL,
                username TEXT NOT NULL,
                msg_key TEXT NOT NULL,
                create_time INTEGER DEFAULT 0,
                local_id INTEGER DEFAULT 0,
                server_id TEXT DEFAULT '',
                payload TEXT NOT NULL,
                PRIMARY KEY (account, username, msg_key)
            );

            CREATE INDEX IF NOT EXISTS idx_messages_conv_time
                ON messages(account, username, create_time DESC, local_id DESC);

            CREATE TABLE IF NOT EXISTS sync_checkpoints (
                account TEXT NOT NULL,
                username TEXT NOT NULL,
                last_create_time INTEGER DEFAULT 0,
                last_server_id TEXT DEFAULT '',
                last_local_id INTEGER DEFAULT 0,
                updated_at INTEGER DEFAULT 0,
                PRIMARY KEY (account, username)
            );

            CREATE TABLE IF NOT EXISTS ai_artifacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account TEXT NOT NULL,
                username TEXT NOT NULL,
                kind TEXT NOT NULL,
                scope_json TEXT DEFAULT '',
                content TEXT DEFAULT '',
                created_at INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS ai_chats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account TEXT NOT NULL,
                username TEXT NOT NULL,
                kind TEXT NOT NULL,            -- 'summary' | 'profile'
                target_user TEXT DEFAULT '',   -- profile: sender username being analysed
                target_name TEXT DEFAULT '',
                title TEXT DEFAULT '',
                start_time INTEGER DEFAULT 0,
                end_time INTEGER DEFAULT 0,
                created_at INTEGER DEFAULT 0,
                updated_at INTEGER DEFAULT 0
            );

            CREATE INDEX IF NOT EXISTS idx_ai_chats_conv
                ON ai_chats(account, username, kind, updated_at DESC);

            CREATE TABLE IF NOT EXISTS ai_chat_turns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                role TEXT NOT NULL,            -- 'user' | 'assistant'
                content TEXT DEFAULT '',
                created_at INTEGER DEFAULT 0
            );

            CREATE INDEX IF NOT EXISTS idx_ai_chat_turns_chat
                ON ai_chat_turns(chat_id, id);
            """
        )
        conn.commit()
        _INITIALIZED_PATHS.add(key)


def _msg_key(msg: dict[str, Any]) -> str:
    """Stable dedup key for one message dict from ``/api/chat/messages``."""
    server_id_str = str(msg.get("serverIdStr") or "").strip()
    if server_id_str and server_id_str != "0":
        return f"s:{server_id_str}"
    server_id = msg.get("serverId")
    if server_id not in (None, 0, "0", ""):
        return f"s:{server_id}"
    local_id = msg.get("localId")
    if local_id not in (None, 0, "0", ""):
        return f"l:{local_id}"
    return f"i:{msg.get('id')}"


# ---------------------------------------------------------------------------
# Conversations
# ---------------------------------------------------------------------------

def upsert_conversation(
    account: str,
    username: str,
    *,
    name: Optional[str] = None,
    avatar: Optional[str] = None,
    is_group: Optional[bool] = None,
) -> None:
    now = int(time.time())
    inferred_group = bool(is_group) if is_group is not None else username.endswith("@chatroom")
    conn = _connect()
    try:
        _ensure_initialized(conn)
        existing = conn.execute(
            "SELECT name, avatar, is_group FROM conversations WHERE account=? AND username=?",
            (account, username),
        ).fetchone()
        if existing is None:
            conn.execute(
                "INSERT INTO conversations (account, username, name, avatar, is_group, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (account, username, name or "", avatar or "", 1 if inferred_group else 0, now),
            )
        else:
            conn.execute(
                "UPDATE conversations SET name=?, avatar=?, is_group=?, updated_at=?"
                " WHERE account=? AND username=?",
                (
                    name if name is not None else existing["name"],
                    avatar if avatar is not None else existing["avatar"],
                    1 if inferred_group else 0,
                    now,
                    account,
                    username,
                ),
            )
        conn.commit()
    finally:
        conn.close()


def _refresh_conversation_stats(conn: sqlite3.Connection, account: str, username: str) -> None:
    row = conn.execute(
        "SELECT COUNT(*) AS c, MIN(create_time) AS mn, MAX(create_time) AS mx"
        " FROM messages WHERE account=? AND username=?",
        (account, username),
    ).fetchone()
    count = int(row["c"] or 0)
    first_time = int(row["mn"] or 0)
    last_time = int(row["mx"] or 0)
    conn.execute(
        "UPDATE conversations SET message_count=?, first_time=?, last_time=?, updated_at=?"
        " WHERE account=? AND username=?",
        (count, first_time, last_time, int(time.time()), account, username),
    )


def list_conversations(account: str) -> list[dict[str, Any]]:
    conn = _connect()
    try:
        _ensure_initialized(conn)
        rows = conn.execute(
            "SELECT account, username, name, avatar, is_group, message_count,"
            " first_time, last_time, updated_at FROM conversations"
            " WHERE account=? ORDER BY last_time DESC, updated_at DESC",
            (account,),
        ).fetchall()
        return [
            {
                "account": r["account"],
                "username": r["username"],
                "name": r["name"] or r["username"],
                "avatar": r["avatar"] or "",
                "isGroup": bool(r["is_group"]),
                "messageCount": int(r["message_count"] or 0),
                "firstTime": int(r["first_time"] or 0),
                "lastTime": int(r["last_time"] or 0),
                "updatedAt": int(r["updated_at"] or 0),
            }
            for r in rows
        ]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------

def upsert_messages(account: str, username: str, messages: list[dict[str, Any]]) -> int:
    """Insert message dicts (dedup by msg_key). Returns count of NEW rows added."""
    if not messages:
        return 0
    conn = _connect()
    try:
        _ensure_initialized(conn)
        before = conn.execute(
            "SELECT COUNT(*) AS c FROM messages WHERE account=? AND username=?",
            (account, username),
        ).fetchone()["c"]
        for msg in messages:
            if not isinstance(msg, dict):
                continue
            key = _msg_key(msg)
            create_time = int(msg.get("createTime") or 0)
            local_id = int(msg.get("localId") or 0)
            server_id = str(msg.get("serverIdStr") or msg.get("serverId") or "").strip()
            payload = json.dumps(msg, ensure_ascii=False)
            conn.execute(
                "INSERT INTO messages (account, username, msg_key, create_time, local_id, server_id, payload)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)"
                " ON CONFLICT(account, username, msg_key) DO UPDATE SET"
                " create_time=excluded.create_time, local_id=excluded.local_id,"
                " server_id=excluded.server_id, payload=excluded.payload",
                (account, username, key, create_time, local_id, server_id, payload),
            )
        _refresh_conversation_stats(conn, account, username)
        after = conn.execute(
            "SELECT COUNT(*) AS c FROM messages WHERE account=? AND username=?",
            (account, username),
        ).fetchone()["c"]
        conn.commit()
        return int(after) - int(before)
    finally:
        conn.close()


def list_messages(
    account: str,
    username: str,
    *,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """Return archived messages mirroring ``/api/chat/messages`` semantics:

    newest page first (by offset), ascending within the returned page.
    """
    limit = max(1, min(int(limit), 500))
    offset = max(0, int(offset))
    conn = _connect()
    try:
        _ensure_initialized(conn)
        total = int(
            conn.execute(
                "SELECT COUNT(*) AS c FROM messages WHERE account=? AND username=?",
                (account, username),
            ).fetchone()["c"]
        )
        rows = conn.execute(
            "SELECT payload FROM messages WHERE account=? AND username=?"
            " ORDER BY create_time DESC, local_id DESC LIMIT ? OFFSET ?",
            (account, username, limit, offset),
        ).fetchall()
        # rows are newest-first; reverse to ascending for display
        messages: list[dict[str, Any]] = []
        for r in reversed(rows):
            try:
                messages.append(json.loads(r["payload"]))
            except Exception:
                continue
        return {
            "total": total,
            "hasMore": (offset + limit) < total,
            "messages": messages,
        }
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Checkpoints
# ---------------------------------------------------------------------------

def get_checkpoint(account: str, username: str) -> Optional[dict[str, Any]]:
    conn = _connect()
    try:
        _ensure_initialized(conn)
        r = conn.execute(
            "SELECT last_create_time, last_server_id, last_local_id, updated_at"
            " FROM sync_checkpoints WHERE account=? AND username=?",
            (account, username),
        ).fetchone()
        if r is None:
            return None
        return {
            "lastCreateTime": int(r["last_create_time"] or 0),
            "lastServerId": r["last_server_id"] or "",
            "lastLocalId": int(r["last_local_id"] or 0),
            "updatedAt": int(r["updated_at"] or 0),
        }
    finally:
        conn.close()


def set_checkpoint(
    account: str,
    username: str,
    *,
    last_create_time: int,
    last_server_id: str = "",
    last_local_id: int = 0,
) -> None:
    now = int(time.time())
    conn = _connect()
    try:
        _ensure_initialized(conn)
        conn.execute(
            "INSERT INTO sync_checkpoints (account, username, last_create_time, last_server_id, last_local_id, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?)"
            " ON CONFLICT(account, username) DO UPDATE SET"
            " last_create_time=excluded.last_create_time, last_server_id=excluded.last_server_id,"
            " last_local_id=excluded.last_local_id, updated_at=excluded.updated_at",
            (account, username, int(last_create_time or 0), last_server_id or "", int(last_local_id or 0), now),
        )
        conn.commit()
    finally:
        conn.close()


def list_messages_chrono(
    account: str,
    username: str,
    *,
    start_time: int = 0,
    end_time: int = 0,
    limit: int = 0,
) -> list[dict[str, Any]]:
    """Return archived messages in ascending chronological order (for AI context).

    If ``limit`` > 0, keep the most recent ``limit`` within the time range, still
    returned ascending. ``start_time``/``end_time`` (Unix seconds) are optional.
    """
    conn = _connect()
    try:
        _ensure_initialized(conn)
        clauses = ["account=?", "username=?"]
        params: list[Any] = [account, username]
        if start_time:
            clauses.append("create_time>=?")
            params.append(int(start_time))
        if end_time:
            clauses.append("create_time<=?")
            params.append(int(end_time))
        where = " AND ".join(clauses)
        if limit and int(limit) > 0:
            rows = conn.execute(
                f"SELECT payload FROM messages WHERE {where}"
                " ORDER BY create_time DESC, local_id DESC LIMIT ?",
                (*params, int(limit)),
            ).fetchall()
            rows = list(reversed(rows))
        else:
            rows = conn.execute(
                f"SELECT payload FROM messages WHERE {where}"
                " ORDER BY create_time ASC, local_id ASC",
                params,
            ).fetchall()
        out: list[dict[str, Any]] = []
        for r in rows:
            try:
                out.append(json.loads(r["payload"]))
            except Exception:
                continue
        return out
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# AI artifacts (summaries / profiles)
# ---------------------------------------------------------------------------

def add_ai_artifact(account: str, username: str, kind: str, scope: dict[str, Any], content: str) -> int:
    conn = _connect()
    try:
        _ensure_initialized(conn)
        cur = conn.execute(
            "INSERT INTO ai_artifacts (account, username, kind, scope_json, content, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (account, username, kind, json.dumps(scope, ensure_ascii=False), content, int(time.time())),
        )
        conn.commit()
        return int(cur.lastrowid or 0)
    finally:
        conn.close()


def list_ai_artifacts(
    account: str, username: str, *, kind: Optional[str] = None, limit: int = 20
) -> list[dict[str, Any]]:
    conn = _connect()
    try:
        _ensure_initialized(conn)
        clauses = ["account=?", "username=?"]
        params: list[Any] = [account, username]
        if kind:
            clauses.append("kind=?")
            params.append(kind)
        where = " AND ".join(clauses)
        rows = conn.execute(
            f"SELECT id, kind, scope_json, content, created_at FROM ai_artifacts"
            f" WHERE {where} ORDER BY created_at DESC LIMIT ?",
            (*params, int(limit)),
        ).fetchall()
        out: list[dict[str, Any]] = []
        for r in rows:
            try:
                scope = json.loads(r["scope_json"] or "{}")
            except Exception:
                scope = {}
            out.append(
                {
                    "id": int(r["id"]),
                    "kind": r["kind"],
                    "scope": scope,
                    "content": r["content"] or "",
                    "createdAt": int(r["created_at"] or 0),
                }
            )
        return out
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Members (per-sender activity, for user profiles)
# ---------------------------------------------------------------------------

def list_members(
    account: str, username: str, *, start_time: int = 0, end_time: int = 0, top: int = 300
) -> list[dict[str, Any]]:
    """Aggregate per-sender message counts from the archive, sorted by activity."""
    conn = _connect()
    try:
        _ensure_initialized(conn)
        clauses = ["account=?", "username=?"]
        params: list[Any] = [account, username]
        if start_time:
            clauses.append("create_time>=?")
            params.append(int(start_time))
        if end_time:
            clauses.append("create_time<=?")
            params.append(int(end_time))
        where = " AND ".join(clauses)
        rows = conn.execute(f"SELECT payload FROM messages WHERE {where}", params).fetchall()
        counts: dict[str, int] = {}
        names: dict[str, str] = {}
        for r in rows:
            try:
                m = json.loads(r["payload"])
            except Exception:
                continue
            if m.get("isSent"):
                key, nm = "__self__", "我"
            else:
                key = str(m.get("senderUsername") or "").strip()
                if not key:
                    continue
                nm = str(m.get("senderDisplayName") or "").strip() or key
            counts[key] = counts.get(key, 0) + 1
            if nm and (key not in names or names[key] == key):
                names[key] = nm
        members = [
            {"username": k, "name": names.get(k, k), "count": v, "isSelf": k == "__self__"}
            for k, v in counts.items()
        ]
        members.sort(key=lambda x: x["count"], reverse=True)
        return members[:top]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# AI chats (multi-turn, with memory)
# ---------------------------------------------------------------------------

def create_ai_chat(
    account: str,
    username: str,
    kind: str,
    *,
    target_user: str = "",
    target_name: str = "",
    title: str = "",
    start_time: int = 0,
    end_time: int = 0,
) -> int:
    now = int(time.time())
    conn = _connect()
    try:
        _ensure_initialized(conn)
        cur = conn.execute(
            "INSERT INTO ai_chats (account, username, kind, target_user, target_name, title,"
            " start_time, end_time, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (account, username, kind, target_user, target_name, title,
             int(start_time or 0), int(end_time or 0), now, now),
        )
        conn.commit()
        return int(cur.lastrowid or 0)
    finally:
        conn.close()


def _chat_row_to_dict(r: Any, turn_count: int = 0) -> dict[str, Any]:
    return {
        "id": int(r["id"]),
        "account": r["account"],
        "username": r["username"],
        "kind": r["kind"],
        "targetUser": r["target_user"] or "",
        "targetName": r["target_name"] or "",
        "title": r["title"] or "",
        "startTime": int(r["start_time"] or 0),
        "endTime": int(r["end_time"] or 0),
        "createdAt": int(r["created_at"] or 0),
        "updatedAt": int(r["updated_at"] or 0),
        "turnCount": int(turn_count),
    }


def list_ai_chats(
    account: str, username: str, *, kind: Optional[str] = None, target_user: Optional[str] = None
) -> list[dict[str, Any]]:
    conn = _connect()
    try:
        _ensure_initialized(conn)
        clauses = ["c.account=?", "c.username=?"]
        params: list[Any] = [account, username]
        if kind:
            clauses.append("c.kind=?")
            params.append(kind)
        if target_user is not None:
            clauses.append("c.target_user=?")
            params.append(target_user)
        where = " AND ".join(clauses)
        rows = conn.execute(
            f"SELECT c.*, (SELECT COUNT(*) FROM ai_chat_turns t WHERE t.chat_id=c.id) AS tc"
            f" FROM ai_chats c WHERE {where} ORDER BY c.updated_at DESC",
            params,
        ).fetchall()
        return [_chat_row_to_dict(r, r["tc"]) for r in rows]
    finally:
        conn.close()


def get_ai_chat(chat_id: int) -> Optional[dict[str, Any]]:
    conn = _connect()
    try:
        _ensure_initialized(conn)
        r = conn.execute("SELECT * FROM ai_chats WHERE id=?", (int(chat_id),)).fetchone()
        if r is None:
            return None
        tc = conn.execute("SELECT COUNT(*) AS c FROM ai_chat_turns WHERE chat_id=?", (int(chat_id),)).fetchone()["c"]
        return _chat_row_to_dict(r, tc)
    finally:
        conn.close()


def has_empty_ai_chat(account: str, username: str, kind: str, target_user: str = "") -> bool:
    conn = _connect()
    try:
        _ensure_initialized(conn)
        r = conn.execute(
            "SELECT c.id FROM ai_chats c WHERE c.account=? AND c.username=? AND c.kind=? AND c.target_user=?"
            " AND (SELECT COUNT(*) FROM ai_chat_turns t WHERE t.chat_id=c.id)=0 LIMIT 1",
            (account, username, kind, target_user),
        ).fetchone()
        return r is not None
    finally:
        conn.close()


def delete_ai_chat(chat_id: int) -> None:
    conn = _connect()
    try:
        _ensure_initialized(conn)
        conn.execute("DELETE FROM ai_chat_turns WHERE chat_id=?", (int(chat_id),))
        conn.execute("DELETE FROM ai_chats WHERE id=?", (int(chat_id),))
        conn.commit()
    finally:
        conn.close()


def add_ai_chat_turn(chat_id: int, role: str, content: str) -> int:
    now = int(time.time())
    conn = _connect()
    try:
        _ensure_initialized(conn)
        cur = conn.execute(
            "INSERT INTO ai_chat_turns (chat_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (int(chat_id), role, content, now),
        )
        conn.execute("UPDATE ai_chats SET updated_at=? WHERE id=?", (now, int(chat_id)))
        conn.commit()
        return int(cur.lastrowid or 0)
    finally:
        conn.close()


def list_ai_chat_turns(chat_id: int) -> list[dict[str, Any]]:
    conn = _connect()
    try:
        _ensure_initialized(conn)
        rows = conn.execute(
            "SELECT role, content, created_at FROM ai_chat_turns WHERE chat_id=? ORDER BY id ASC",
            (int(chat_id),),
        ).fetchall()
        return [
            {"role": r["role"], "content": r["content"] or "", "createdAt": int(r["created_at"] or 0)}
            for r in rows
        ]
    finally:
        conn.close()


def set_ai_chat_title(chat_id: int, title: str) -> None:
    conn = _connect()
    try:
        _ensure_initialized(conn)
        conn.execute("UPDATE ai_chats SET title=? WHERE id=?", (title, int(chat_id)))
        conn.commit()
    finally:
        conn.close()


def compute_checkpoint_from_messages(messages: list[dict[str, Any]]) -> Optional[dict[str, Any]]:
    """Pick the newest message (max createTime) as the checkpoint cursor."""
    best: Optional[dict[str, Any]] = None
    best_ct = -1
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        ct = int(msg.get("createTime") or 0)
        if ct > best_ct:
            best_ct = ct
            best = msg
    if best is None:
        return None
    return {
        "last_create_time": int(best.get("createTime") or 0),
        "last_server_id": str(best.get("serverIdStr") or best.get("serverId") or "").strip(),
        "last_local_id": int(best.get("localId") or 0),
    }
