from __future__ import annotations

import os
from collections.abc import Sequence
from typing import Any

import httpx

from adola._errors import AdolaAPIError
from adola.types import (
    CompressRequest,
    CompressResponse,
    CompressionOptions,
    Model,
    ProtectedOptions,
    Span,
)

DEFAULT_BASE_URL = "https://api.adola.app"
USER_AGENT = "adola-python/0.1.1"


class Adola:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float | httpx.Timeout = 30.0,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("ADOLA_API_KEY")
        if not self.api_key:
            raise ValueError("api_key or ADOLA_API_KEY is required")
        self.base_url = _normalize_base_url(base_url or os.getenv("ADOLA_BASE_URL") or DEFAULT_BASE_URL)
        self._owns_client = http_client is None
        self._client = http_client or httpx.Client(timeout=timeout)

    def __enter__(self) -> "Adola":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def models(self) -> list[Model]:
        return self._request("GET", "/v1/models")

    def compress(
        self,
        input: str | None = None,
        *,
        query: str | None = None,
        spans: Sequence[Span] | None = None,
        model: str = "rose-1",
        compression: CompressionOptions | None = None,
        protected: ProtectedOptions | None = None,
        include_spans: bool = False,
    ) -> CompressResponse:
        payload = _compress_payload(
            input=input,
            query=query,
            spans=spans,
            model=model,
            compression=compression,
            protected=protected,
            include_spans=include_spans,
        )
        return self._request("POST", "/v1/compress", json=payload)

    def batch_compress(self, requests: Sequence[CompressRequest]) -> list[CompressResponse]:
        if not requests:
            raise ValueError("requests must not be empty")
        return self._request("POST", "/v1/batch/compress", json={"requests": list(requests)})

    def _request(self, method: str, path: str, *, json: Any | None = None) -> Any:
        try:
            response = self._client.request(
                method,
                f"{self.base_url}{path}",
                headers=_headers(self.api_key),
                json=json,
            )
        except httpx.RequestError as exc:
            raise AdolaAPIError(f"Request failed: {exc}") from exc
        return _decode_response(response)


class AsyncAdola:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float | httpx.Timeout = 30.0,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("ADOLA_API_KEY")
        if not self.api_key:
            raise ValueError("api_key or ADOLA_API_KEY is required")
        self.base_url = _normalize_base_url(base_url or os.getenv("ADOLA_BASE_URL") or DEFAULT_BASE_URL)
        self._owns_client = http_client is None
        self._client = http_client or httpx.AsyncClient(timeout=timeout)

    async def __aenter__(self) -> "AsyncAdola":
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def models(self) -> list[Model]:
        return await self._request("GET", "/v1/models")

    async def compress(
        self,
        input: str | None = None,
        *,
        query: str | None = None,
        spans: Sequence[Span] | None = None,
        model: str = "rose-1",
        compression: CompressionOptions | None = None,
        protected: ProtectedOptions | None = None,
        include_spans: bool = False,
    ) -> CompressResponse:
        payload = _compress_payload(
            input=input,
            query=query,
            spans=spans,
            model=model,
            compression=compression,
            protected=protected,
            include_spans=include_spans,
        )
        return await self._request("POST", "/v1/compress", json=payload)

    async def batch_compress(self, requests: Sequence[CompressRequest]) -> list[CompressResponse]:
        if not requests:
            raise ValueError("requests must not be empty")
        return await self._request("POST", "/v1/batch/compress", json={"requests": list(requests)})

    async def _request(self, method: str, path: str, *, json: Any | None = None) -> Any:
        try:
            response = await self._client.request(
                method,
                f"{self.base_url}{path}",
                headers=_headers(self.api_key),
                json=json,
            )
        except httpx.RequestError as exc:
            raise AdolaAPIError(f"Request failed: {exc}") from exc
        return _decode_response(response)


def _compress_payload(
    *,
    input: str | None,
    query: str | None,
    spans: Sequence[Span] | None,
    model: str,
    compression: CompressionOptions | None,
    protected: ProtectedOptions | None,
    include_spans: bool,
) -> CompressRequest:
    if not input and not spans:
        raise ValueError("input or spans is required")
    payload: CompressRequest = {
        "model": model,  # type: ignore[typeddict-item]
        "include_spans": include_spans,
    }
    if input is not None:
        payload["input"] = input
    if query is not None:
        payload["query"] = query
    if spans is not None:
        payload["spans"] = list(spans)
    if compression is not None:
        payload["compression"] = compression
    if protected is not None:
        payload["protected"] = protected
    return payload


def _decode_response(response: httpx.Response) -> Any:
    if response.is_success:
        return response.json()
    message = _error_message(response)
    raise AdolaAPIError(
        message,
        status_code=response.status_code,
        request_id=response.headers.get("x-request-id"),
        response=response,
    )


def _error_message(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return response.text or response.reason_phrase
    detail = body.get("detail") if isinstance(body, dict) else None
    if isinstance(detail, str):
        return detail
    if isinstance(detail, list):
        messages = [
            item.get("msg")
            for item in detail
            if isinstance(item, dict) and isinstance(item.get("msg"), str)
        ]
        if messages:
            return "; ".join(messages)
    return response.reason_phrase


def _headers(api_key: str) -> dict[str, str]:
    return {
        "Accept": "application/json",
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": USER_AGENT,
    }


def _normalize_base_url(base_url: str) -> str:
    return base_url.rstrip("/")
