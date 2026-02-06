from __future__ import annotations

from typing import Optional

import requests


class TelegramAlertManager:
    def __init__(
        self,
        bot_token: Optional[str],
        chat_id: Optional[str],
        timeout_seconds: int = 10,
    ):
        self._bot_token = bot_token
        self._chat_id = chat_id
        self._timeout_seconds = timeout_seconds

    def is_configured(self) -> bool:
        return bool(self._bot_token and self._chat_id)

    def send_alert(self, message: str) -> bool:
        if not self.is_configured():
            return False
        url = f"https://api.telegram.org/bot{self._bot_token}/sendMessage"
        payload = {"chat_id": self._chat_id, "text": message}
        try:
            response = requests.post(url, json=payload, timeout=self._timeout_seconds)
            return response.ok
        except requests.RequestException:
            return False
