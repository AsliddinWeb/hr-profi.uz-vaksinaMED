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


    async def _multipart(self, method: str, data: dict[str, str], files: dict[str, tuple[str, bytes]]) -> Any:
        try:
            r = await self._http.post(f"{API}/bot{self._token}/{method}", data=data, files=files)
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

    async def send_video(self, chat_id: int | str, filename: str, data: bytes, caption: str | None = None) -> Any:
        """Video (pleyer bilan ko'rinadi). Bot yuklash limiti 50 MB."""
        return await self._multipart("sendVideo", {"chat_id": str(chat_id), "supports_streaming": "true", **({"caption": caption[:1000]} if caption else {})}, {"video": (filename, data)})

    async def send_photo_group(self, chat_id: int | str, photos: list[tuple[str, bytes]], caption: str | None = None) -> Any:
        """Albom: 2-10 ta surat bitta xabarda (kanal tezlik limitini tejaydi). Bitta surat bo'lsa sendPhoto."""
        if len(photos) == 1:
            return await self._multipart("sendPhoto", {"chat_id": str(chat_id), **({"caption": caption[:1000]} if caption else {})}, {"photo": photos[0]})
        import json  # noqa: PLC0415

        media = [{"type": "photo", "media": f"attach://p{i}", **({"caption": caption[:1000]} if caption and i == 0 else {})} for i in range(len(photos))]
        return await self._multipart("sendMediaGroup", {"chat_id": str(chat_id), "media": json.dumps(media)}, {f"p{i}": p for i, p in enumerate(photos)})


def esc(text: str | None) -> str:
    return html.escape(text or "", quote=False)
