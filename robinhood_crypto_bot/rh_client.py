from __future__ import annotations

import base64
import json
import time
from dataclasses import dataclass
from typing import Any

import requests
from nacl.signing import SigningKey


ROBINHOOD_BASE_URL = "https://trading.robinhood.com"


class RobinhoodAPIError(RuntimeError):
    pass


@dataclass(frozen=True)
class RobinhoodCredentials:
    api_key: str
    private_key_base64: str

    def validate(self) -> None:
        if not self.api_key.strip():
            raise RobinhoodAPIError("Missing ROBINHOOD_API_KEY.")
        if not self.private_key_base64.strip():
            raise RobinhoodAPIError("Missing ROBINHOOD_PRIVATE_KEY_BASE64.")


class RobinhoodCryptoClient:
    def __init__(
        self,
        credentials: RobinhoodCredentials,
        *,
        base_url: str = ROBINHOOD_BASE_URL,
        timeout_seconds: int = 15,
    ) -> None:
        credentials.validate()
        self.api_key = credentials.api_key.strip()
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        private_key_bytes = base64.b64decode(credentials.private_key_base64.strip())
        self.signing_key = SigningKey(private_key_bytes[:32])
        self.session = requests.Session()

    def get_accounts(self) -> dict[str, Any]:
        return self.request("GET", "/api/v1/crypto/trading/accounts/")

    def get_holdings(self) -> dict[str, Any]:
        return self.request("GET", "/api/v1/crypto/trading/holdings/")

    def get_orders(self) -> dict[str, Any]:
        return self.request("GET", "/api/v1/crypto/trading/orders/")

    def get_products(self) -> dict[str, Any]:
        return self.request("GET", "/api/v1/crypto/trading/products/")

    def get_best_bid_ask(self, symbol: str) -> dict[str, Any]:
        return self.request("GET", f"/api/v1/crypto/marketdata/best_bid_ask/?symbol={symbol}")

    def request(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        method = method.upper()
        body_json = "" if body is None else json.dumps(body, separators=(",", ":"), sort_keys=True)
        headers = self._auth_headers(method, path, body_json)
        if body_json:
            headers["Content-Type"] = "application/json"
        response = self.session.request(
            method,
            f"{self.base_url}{path}",
            headers=headers,
            data=body_json if body_json else None,
            timeout=self.timeout_seconds,
        )
        if response.status_code >= 400:
            raise RobinhoodAPIError(f"{method} {path} failed: {response.status_code} {response.text[:500]}")
        if not response.text:
            return {}
        return response.json()

    def _auth_headers(self, method: str, path: str, body_json: str) -> dict[str, str]:
        timestamp = str(int(time.time()))
        message = f"{self.api_key}{timestamp}{path}{method}{body_json}"
        signed = self.signing_key.sign(message.encode("utf-8"))
        signature = base64.b64encode(signed.signature).decode("utf-8")
        return {
            "x-api-key": self.api_key,
            "x-signature": signature,
            "x-timestamp": timestamp,
        }

