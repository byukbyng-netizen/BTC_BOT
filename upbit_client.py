"""Small stdlib-only Upbit REST client for domestic spot trading."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
import uuid
import ssl
from typing import Any, Callable
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE_URL = "https://api.upbit.com"


def _default_opener(request, timeout):
    try:
        import certifi
        context = ssl.create_default_context(cafile=certifi.where())
        return urlopen(request, timeout=timeout, context=context)
    except ImportError:
        return urlopen(request, timeout=timeout)


class UpbitError(RuntimeError):
    pass


class UpbitMarketError(UpbitError):
    pass


def normalize_market(value: str) -> str:
    value = value.strip().upper()
    if "-" in value:
        return value
    if "/" in value:
        base, quote = value.split("/", 1)
        return f"{quote}-{base}"
    raise UpbitMarketError(f"잘못된 마켓 형식: {value}")


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def _jwt(access_key: str, secret_key: str, query: dict[str, Any] | None = None) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    payload: dict[str, Any] = {"access_key": access_key, "nonce": str(uuid.uuid4())}
    if query:
        query_string = urlencode(query, doseq=True)
        payload["query_hash"] = hashlib.sha512(query_string.encode()).hexdigest()
        payload["query_hash_alg"] = "SHA512"
    encoded = f"{_b64(json.dumps(header, separators=(',', ':')).encode())}.{_b64(json.dumps(payload, separators=(',', ':')).encode())}"
    return f"{encoded}.{_b64(hmac.new(secret_key.encode(), encoded.encode(), hashlib.sha256).digest())}"


class UpbitRestClient:
    def __init__(self, access_key: str | None, secret_key: str | None, base_url: str = BASE_URL, opener: Callable[..., Any] = _default_opener, timeout: float = 10):
        self.access_key, self.secret_key = access_key, secret_key
        self.base_url, self.opener, self.timeout = base_url.rstrip("/"), opener, timeout

    def _request(self, method: str, path: str, query: dict[str, Any] | None = None, private: bool = False, body: dict[str, Any] | None = None):
        query = query or {}
        url = f"{self.base_url}{path}"
        if query:
            url += "?" + urlencode(query, doseq=True)
        headers = {"Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        if private:
            if not self.access_key or not self.secret_key:
                raise UpbitError("인증 API에는 UPBIT_ACCESS_KEY/UPBIT_SECRET_KEY가 필요합니다.")
            headers["Authorization"] = f"Bearer {_jwt(self.access_key, self.secret_key, query or body)}"
        request = Request(url, data=json.dumps(body).encode() if body is not None else None, headers=headers, method=method)
        try:
            with self.opener(request, timeout=self.timeout) as response:
                raw = response.read()
        except Exception as exc:
            raise UpbitError(f"업비트 API 요청 실패: {exc}") from exc
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise UpbitError("업비트 API가 JSON이 아닌 응답을 반환했습니다.") from exc
        if isinstance(payload, dict) and payload.get("error"):
            error = payload["error"]
            raise UpbitError(f"{error.get('name', 'api_error')}: {error.get('message', '')}")
        return payload

    def market_all(self) -> list[dict[str, Any]]:
        return self._request("GET", "/v1/market/all", {"is_details": "true"})

    def validate_market(self, market: str, markets: list[dict[str, Any]] | None = None) -> str:
        code = normalize_market(market)
        rows = markets if markets is not None else self.market_all()
        if code not in {row.get("market") for row in rows}:
            raise UpbitMarketError(f"거래 불가 마켓: {code}")
        return code

    def ticker(self, market: str) -> list[dict[str, Any]]:
        return self._request("GET", "/v1/ticker", {"markets": normalize_market(market)})

    def candles(self, market: str, unit: int = 15, count: int = 200) -> list[dict[str, Any]]:
        if unit not in {1, 3, 5, 10, 15, 30, 60, 240}:
            raise UpbitError("지원하지 않는 분봉 단위입니다.")
        return self._request("GET", f"/v1/candles/minutes/{unit}", {"market": normalize_market(market), "count": count})

    def orderbook(self, market: str) -> list[dict[str, Any]]:
        return self._request("GET", "/v1/orderbook", {"markets": normalize_market(market)})

    def get_accounts(self):
        return self._request("GET", "/v1/accounts", private=True)

    def order_chance(self, market: str):
        return self._request("GET", "/v1/orders/chance", {"market": normalize_market(market)}, private=True)

    def orders(self, market: str | None = None, state: str = "wait"):
        query = {"market": normalize_market(market), "state": state} if market else {"state": state}
        return self._request("GET", "/v1/orders", query, private=True)

    def order(self, uuid_value: str):
        return self._request("GET", "/v1/order", {"uuid": uuid_value}, private=True)

    def cancel_order(self, uuid_value: str):
        return self._request("DELETE", "/v1/order", {"uuid": uuid_value}, private=True)


