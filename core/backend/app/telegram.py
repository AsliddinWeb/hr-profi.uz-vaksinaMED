"""Telegram Bot API uchun minimal klient (httpx). Bot token bo'lmasa Telegram o'chirilgan hisoblanadi."""

import html
from typing import Any

import httpx

API = "https://api.telegram.org"


class TelegramError(Exception):
    def __init__(self, description: str, status: int = 0, retry_after: int | None = None):
        super().__init__(description)
        self.description = description
        self.status = status
        self.retry_after = retry_after

    @property
    def chat_unreachable(self) -> bool:
        """Foydalanuvchi botni bloklagan yoki chat o'chirilgan: qayta urinish befoyda."""
        d = self.description.lower()
        return self.status == 403 or "chat not found" in d or "user is deactivated" in d


class TelegramClient:
    def __init__(self, token: str, transport: httpx.AsyncBaseTransport | None = None):
        self._token = token
        self._http = httpx.AsyncClient(transport=transport, timeout=httpx.Timeout(40, connect=10))

    async def close(self) -> None:
        await self._http.aclose()

    async def call(self, method: str, **params: Any) -> Any:
        try:
            r = await self._http.post(f"{API}/bot{self._token}/{method}", json=params)
        except httpx.HTTPError as exc:
            raise TelegramError(f"network: {type(exc).__name__}") from exc
        try:
            body = r.json()
        except ValueError:
            raise TelegramError(f"bad response {r.status_code}", r.status_code) from None
        if not body.get("ok"):
            retry = (body.get("parameters") or {}).get("retry_after")
            raise TelegramError(body.get("description", "error"), body.get("error_code", r.status_code), retry)
        return body["result"]

    async def get_me(self) -> dict:
        return await self.call("getMe")

    async def get_updates(self, offset: int | None, timeout: int = 25) -> list[dict]:
        params: dict[str, Any] = {"timeout": timeout, "allowed_updates": ["message"]}
        if offset is not None:
            params["offset"] = offset
        return await self.call("getUpdates", **params)

    async def send_message(self, chat_id: int, text: str) -> None:
        await self.call(
            "sendMessage",
            chat_id=chat_id,
            text=text,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )

    async def send_document(self, chat_id: int, filename: str, data: bytes, caption: str | None = None) -> None:
        """Fayl yuborish (multipart). Telegram bot uchun limit 50 MB."""
        try:
            r = await self._http.post(
                f"{API}/bot{self._token}/sendDocument",
                data={"chat_id": str(chat_id), **({"caption": caption[:1000]} if caption else {})},
                files={"document": (filename, data)},
            )
        except httpx.HTTPError as exc:
            raise TelegramError(f"network: {type(exc).__name__}") from exc
        try:
            body = r.json()
        except ValueError:
            raise TelegramError(f"bad response {r.status_code}", r.status_code) from None
        if not body.get("ok"):
            retry = (body.get("parameters") or {}).get("retry_after")
            raise TelegramError(body.get("description", "error"), body.get("error_code", r.status_code), retry)


def esc(text: str | None) -> str:
    return html.escape(text or "", quote=False)
