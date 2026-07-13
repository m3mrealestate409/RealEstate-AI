"""
Provider-agnostic notifications (e.g. "a new visitor is chatting").

One small abstraction drives every channel the user might pick:

- "telegram"  → POST to the Telegram Bot API (official, free, no ban risk).
- "webhook"   → POST to ANY URL with a caller-defined JSON body + headers. This
                covers an unofficial WhatsApp HTTP service, the WhatsApp Cloud
                API (graph.facebook.com + a Bearer header + Meta's body shape),
                Zapier/Make/n8n, Slack/Discord, etc.
- "off"       → disabled.

All sends are best-effort and time-boxed: a notification failure must never
affect the visitor's chat.
"""
from __future__ import annotations

import json
import logging

import httpx

logger = logging.getLogger(__name__)

_TIMEOUT = 8.0


def build_new_chat_message(first_message: str, page_url: str | None) -> str:
    lines = ["🟢 New website chat", ""]
    if first_message:
        lines.append("Visitor: " + first_message.strip()[:300])
    if page_url:
        lines.append("Page: " + page_url)
    lines.append("")
    lines.append("Open the Live Chat console to reply / take over.")
    return "\n".join(lines)


def _render_template(template: str, text: str, extra: dict | None = None) -> str:
    """Substitute {{text}} (and a few extras) into a JSON body template, keeping
    the result valid JSON by inserting a JSON-escaped value (quotes stripped)."""
    def esc(v: str) -> str:
        return json.dumps(str(v))[1:-1]  # escape then drop the surrounding quotes

    out = template.replace("{{text}}", esc(text))
    for k, v in (extra or {}).items():
        out = out.replace("{{" + k + "}}", esc(v if v is not None else ""))
    return out


def send(provider: str, config: dict | None, text: str, extra: dict | None = None) -> tuple[bool, str]:
    """Send a notification. Returns (ok, detail). Never raises."""
    provider = (provider or "off").lower()
    config = config or {}
    try:
        if provider == "telegram":
            token = (config.get("bot_token") or "").strip()
            chat_id = (config.get("chat_id") or "").strip()
            if not token or not chat_id:
                return False, "Telegram bot_token and chat_id are required."
            r = httpx.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": text},
                timeout=_TIMEOUT,
            )
            return (r.status_code < 300), f"Telegram HTTP {r.status_code}: {r.text[:200]}"

        if provider == "webhook":
            url = (config.get("url") or "").strip()
            if not url.startswith(("http://", "https://")):
                return False, "Webhook url must start with http:// or https://"
            template = config.get("body_template") or '{"text": "{{text}}"}'
            body_str = _render_template(template, text, extra)
            try:
                body = json.loads(body_str)
            except json.JSONDecodeError as e:
                return False, f"Body template is not valid JSON after substitution: {e}"
            headers = {"Content-Type": "application/json"}
            for k, v in (config.get("headers") or {}).items():
                headers[str(k)] = str(v)
            r = httpx.post(url, json=body, headers=headers, timeout=_TIMEOUT)
            return (r.status_code < 300), f"Webhook HTTP {r.status_code}: {r.text[:200]}"

        return False, "Notifications are off."
    except Exception as exc:  # noqa: BLE001 — best-effort
        logger.warning("Notification send failed (%s): %s", provider, exc)
        return False, str(exc)
