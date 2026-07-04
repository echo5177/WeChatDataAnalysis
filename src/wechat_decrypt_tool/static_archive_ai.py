"""AI analysis over the static chat archive.

Reads ONLY the static archive (`static_archive.db`) — never the live WeChat DBs —
assembles a compact transcript, and calls an OpenAI-compatible chat-completions
endpoint (DeepSeek / 智谱 / Kimi / OpenAI / any compatible gateway).

Configuration via environment variables (nothing is stored on disk or in git):
- ``LLM_API_KEY``   required
- ``LLM_BASE_URL``  optional, default ``https://api.deepseek.com/v1``
- ``LLM_MODEL``     optional, default ``deepseek-chat``

Privacy note: the selected conversation's text is sent to the configured provider.
"""

from __future__ import annotations

import datetime
import os
from typing import Any, Optional

import httpx

from . import static_archive_store as store
from .logging_config import get_logger

logger = get_logger(__name__)

DEFAULT_BASE_URL = "https://api.deepseek.com/v1"
DEFAULT_MODEL = "deepseek-chat"

# Keep the transcript under a safe character budget for a single-pass request.
_TRANSCRIPT_CHAR_BUDGET = 16000
_DEFAULT_MAX_MESSAGES = 500

# Multi-turn chat context: bigger budget (user doesn't mind tokens, but the model's
# context window is still finite — keep the most recent within these bounds).
_CHAT_CONTEXT_MAX_MESSAGES = 2500
_CHAT_TRANSCRIPT_CHAR_BUDGET = 48000

_MEDIA_PLACEHOLDER = {
    "image": "[图片]",
    "video": "[视频]",
    "voice": "[语音]",
    "emoji": "[表情]",
    "file": "[文件]",
    "link": "[链接]",
    "transfer": "[转账]",
    "redPacket": "[红包]",
    "chatHistory": "[聊天记录]",
    "voip": "[通话]",
}


def _cfg() -> dict[str, str]:
    return {
        "base_url": (os.environ.get("LLM_BASE_URL", "").strip() or DEFAULT_BASE_URL).rstrip("/"),
        "api_key": os.environ.get("LLM_API_KEY", "").strip(),
        "model": os.environ.get("LLM_MODEL", "").strip() or DEFAULT_MODEL,
    }


def is_configured() -> bool:
    return bool(_cfg()["api_key"])


def effective_model() -> str:
    return _cfg()["model"] if is_configured() else ""


def list_models() -> list[str]:
    """List available model ids from the OpenAI-compatible provider (GET /models).

    Falls back to the configured default model if the endpoint is unavailable.
    """
    cfg = _cfg()
    if not cfg["api_key"]:
        return []
    url = f"{cfg['base_url']}/models"
    try:
        with httpx.Client(timeout=20) as client:
            resp = client.get(url, headers={"Authorization": f"Bearer {cfg['api_key']}"})
        if resp.status_code >= 400:
            return [cfg["model"]]
        data = resp.json()
        ids = [str(m.get("id")) for m in (data.get("data") or []) if isinstance(m, dict) and m.get("id")]
        if cfg["model"] and cfg["model"] not in ids:
            ids.insert(0, cfg["model"])
        return ids or [cfg["model"]]
    except Exception as e:
        logger.info("[static-ai] list_models failed, using default: %s", e)
        return [cfg["model"]]


def _fmt_time(ts: Any) -> str:
    try:
        return datetime.datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return ""


def build_transcript(messages: list[dict[str, Any]], *, char_budget: int = _TRANSCRIPT_CHAR_BUDGET) -> str:
    lines: list[str] = []
    for m in messages:
        if not isinstance(m, dict):
            continue
        rt = str(m.get("renderType") or "text")
        if rt == "system":
            continue
        sender = "我" if m.get("isSent") else (m.get("senderDisplayName") or m.get("senderUsername") or "对方")
        if rt in ("text", "quote"):
            content = str(m.get("content") or "").strip()
        else:
            content = _MEDIA_PLACEHOLDER.get(rt) or (str(m.get("content") or "").strip() or f"[{rt}]")
        content = content.replace("\n", " ").strip()
        if not content:
            continue
        lines.append(f"[{_fmt_time(m.get('createTime'))}] {sender}: {content}")
    text = "\n".join(lines)
    if len(text) > char_budget:
        # keep the most recent portion
        text = text[-char_budget:]
        text = text[text.find("\n") + 1:]
    return text


def build_chat_context(chat: dict[str, Any]) -> tuple[str, int]:
    """Build the system message (context transcript + role instruction) for a chat."""
    account = chat["account"]
    username = chat["username"]
    msgs = store.list_messages_chrono(
        account,
        username,
        start_time=int(chat.get("startTime") or 0),
        end_time=int(chat.get("endTime") or 0),
        limit=_CHAT_CONTEXT_MAX_MESSAGES,
    )
    transcript = build_transcript(msgs, char_budget=_CHAT_TRANSCRIPT_CHAR_BUDGET)

    conv = next((c for c in store.list_conversations(account) if c["username"] == username), None)
    conv_name = (conv or {}).get("name") or username

    if chat.get("kind") == "profile":
        target = str(chat.get("targetName") or chat.get("targetUser") or "该用户").strip()
        system = (
            "你是一名中文人物画像与对话分析助手。下面提供的是一个群聊的聊天记录（多人对话）。"
            f"用户想重点了解其中的「{target}」这个人。请务必结合整个群聊的上下文——其他人说了什么、"
            f"大家如何回应「{target}」——来判断 TA 的角色、性格、关注点、专业能力与互动关系，"
            "而不要只看 TA 自己发的内容。只依据聊天记录客观分析，不确定处标注（推测），避免刻板印象。"
            f"\n\n【群聊「{conv_name}」聊天记录】\n{transcript}"
        )
    else:
        system = (
            "你是一名严谨的中文聊天记录分析助手。下面是一段会话/群聊的聊天记录，"
            "请依据它回答用户的问题；不要编造记录中不存在的信息，无法确定的地方要说明。"
            f"\n\n【会话「{conv_name}」聊天记录】\n{transcript}"
        )
    return system, len(msgs)


def run_chat_turn(
    chat: dict[str, Any],
    history: list[dict[str, Any]],
    user_message: str,
    *,
    model: Optional[str] = None,
) -> str:
    """Run one multi-turn chat step: system context + prior turns + new user message."""
    system, _ctx = build_chat_context(chat)
    messages: list[dict[str, str]] = [{"role": "system", "content": system}]
    for h in history:
        role = str(h.get("role") or "")
        if role in ("user", "assistant"):
            messages.append({"role": role, "content": str(h.get("content") or "")})
    messages.append({"role": "user", "content": user_message})
    return _chat(messages, model=model, max_tokens=3000)


def _chat(
    messages: list[dict[str, str]], *, model: Optional[str] = None, temperature: float = 0.4, max_tokens: int = 2000
) -> str:
    cfg = _cfg()
    if not cfg["api_key"]:
        raise RuntimeError("未配置 LLM，请设置环境变量 LLM_API_KEY（可选 LLM_BASE_URL / LLM_MODEL）")
    use_model = str(model or "").strip() or cfg["model"]
    url = f"{cfg['base_url']}/chat/completions"
    payload = {
        "model": use_model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    headers = {"Authorization": f"Bearer {cfg['api_key']}", "Content-Type": "application/json"}
    logger.info("[static-ai] calling LLM model=%s base=%s", use_model, cfg["base_url"])
    with httpx.Client(timeout=180) as client:
        resp = client.post(url, json=payload, headers=headers)
    if resp.status_code >= 400:
        raise RuntimeError(f"LLM 返回 {resp.status_code}: {resp.text[:300]}")
    data = resp.json()
    try:
        return str(data["choices"][0]["message"]["content"]).strip()
    except Exception as e:  # pragma: no cover - defensive
        raise RuntimeError(f"LLM 响应解析失败: {e}; 原始: {str(data)[:300]}")


def _gather(account: str, username: str, start_time: int, end_time: int, max_messages: int) -> tuple[list[dict[str, Any]], str]:
    msgs = store.list_messages_chrono(
        account,
        username,
        start_time=int(start_time or 0),
        end_time=int(end_time or 0),
        limit=int(max_messages or _DEFAULT_MAX_MESSAGES),
    )
    if not msgs:
        raise ValueError("该会话在归档中没有可分析的消息，请先导入。")
    return msgs, build_transcript(msgs)


def summarize_conversation(
    account: str,
    username: str,
    conv_name: str,
    *,
    start_time: int = 0,
    end_time: int = 0,
    max_messages: int = _DEFAULT_MAX_MESSAGES,
    model: Optional[str] = None,
) -> dict[str, Any]:
    msgs, transcript = _gather(account, username, start_time, end_time, max_messages)
    system = (
        "你是一名严谨的中文聊天记录分析助手。只依据用户提供的聊天记录进行分析，"
        "不要编造记录中不存在的信息，无法确定的地方要说明。"
    )
    user = (
        f"以下是会话「{conv_name}」的聊天记录（格式为 [时间] 发送者: 内容，媒体消息用占位符表示）：\n\n"
        f"{transcript}\n\n"
        "请输出一份结构化总结，包含：\n"
        "1. 一句话概述；\n"
        "2. 主要话题（分点）；\n"
        "3. 关键事件 / 决定 / 待办事项（若有，注明相关的人）；\n"
        "4. 参与者概况（各自主要在聊什么）；\n"
        "5. 时间线要点。\n"
        "用简体中文，条理清晰，使用 Markdown。"
    )
    content = _chat([{"role": "system", "content": system}, {"role": "user", "content": user}], model=model)
    scope = {
        "start_time": int(start_time or 0),
        "end_time": int(end_time or 0),
        "messages": len(msgs),
        "model": str(model or "").strip() or effective_model(),
    }
    store.add_ai_artifact(account, username, "summary", scope, content)
    return {"content": content, "messages": len(msgs), "model": scope["model"]}


def profile_users(
    account: str,
    username: str,
    conv_name: str,
    *,
    start_time: int = 0,
    end_time: int = 0,
    max_messages: int = _DEFAULT_MAX_MESSAGES,
    model: Optional[str] = None,
) -> dict[str, Any]:
    msgs, transcript = _gather(account, username, start_time, end_time, max_messages)
    system = (
        "你是一名中文人物画像分析助手。只依据聊天记录客观分析，避免主观臆断和刻板印象，"
        "对不确定的推断要标注「（推测）」。"
    )
    user = (
        f"以下是会话「{conv_name}」的聊天记录：\n\n{transcript}\n\n"
        "请为聊天中的主要参与者分别生成用户画像，每个人包含：\n"
        "- 说话风格与语气；\n"
        "- 关注的主要话题 / 兴趣；\n"
        "- 与他人的互动关系；\n"
        "- 可观察到的性格特点（附依据）。\n"
        "「我」代表归档者本人。用简体中文，按人分段，使用 Markdown。"
    )
    content = _chat([{"role": "system", "content": system}, {"role": "user", "content": user}], model=model)
    scope = {
        "start_time": int(start_time or 0),
        "end_time": int(end_time or 0),
        "messages": len(msgs),
        "model": str(model or "").strip() or effective_model(),
    }
    store.add_ai_artifact(account, username, "profile", scope, content)
    return {"content": content, "messages": len(msgs), "model": scope["model"]}
