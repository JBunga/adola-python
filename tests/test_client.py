from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import httpx
import pytest

from adola import Adola, AdolaAPIError, AsyncAdola

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def load_fixture(name: str) -> object:
    return json.loads((FIXTURES / name).read_text())


def test_models_sends_auth_and_parses_response() -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json=load_fixture("models-response.json"))

    client = Adola(
        api_key="test-key",
        base_url="https://unit.test/",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    models = client.models()

    assert models[0]["id"] == "rose-1"
    assert calls[0].url == "https://unit.test/v1/models"
    assert calls[0].headers["authorization"] == "Bearer test-key"
    assert calls[0].headers["user-agent"] == "adola-python/0.1.0"


def test_compress_sends_schema_payload() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["payload"] = json.loads(request.content)
        return httpx.Response(200, json=load_fixture("compress-response.json"))

    client = Adola(
        api_key="test-key",
        base_url="https://unit.test",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    response = client.compress(
        input="source text",
        query="needle",
        compression={"target_ratio": 0.5, "preserve_order": False},
        protected={"xml_tags": ["safe"], "patterns": ["SECRET"]},
        include_spans=False,
    )

    assert response["receipt"]["tokens_saved"] == 6
    assert seen["payload"] == {
        "model": "rose-1",
        "input": "source text",
        "query": "needle",
        "compression": {"target_ratio": 0.5, "preserve_order": False},
        "protected": {"xml_tags": ["safe"], "patterns": ["SECRET"]},
        "include_spans": False,
    }


def test_compress_accepts_spans_without_input() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert json.loads(request.content)["spans"] == [{"id": "a", "text": "span text"}]
        return httpx.Response(200, json=load_fixture("compress-response.json"))

    client = Adola(
        api_key="test-key",
        base_url="https://unit.test",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    assert client.compress(spans=[{"id": "a", "text": "span text"}])["model"] == "rose-1"


def test_compress_requires_input_or_spans() -> None:
    client = Adola(
        api_key="test-key",
        http_client=httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(500))),
    )

    with pytest.raises(ValueError, match="input or spans"):
        client.compress()


def test_batch_compress_posts_requests_array() -> None:
    request_fixture = load_fixture("compress-request.json")

    def handler(request: httpx.Request) -> httpx.Response:
        assert json.loads(request.content) == {"requests": [request_fixture]}
        return httpx.Response(200, json=[load_fixture("compress-response.json")])

    client = Adola(
        api_key="test-key",
        base_url="https://unit.test",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    response = client.batch_compress([request_fixture])  # type: ignore[list-item]

    assert response[0]["output"].startswith("Adola removes")


def test_api_error_includes_status_and_request_id() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            422,
            headers={"x-request-id": "req_123"},
            json={"detail": [{"msg": "input or spans is required"}]},
        )

    client = Adola(
        api_key="test-key",
        base_url="https://unit.test",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    with pytest.raises(AdolaAPIError) as exc_info:
        client.models()

    assert exc_info.value.status_code == 422
    assert exc_info.value.request_id == "req_123"
    assert str(exc_info.value) == "input or spans is required"


def test_request_error_is_wrapped() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route")

    client = Adola(
        api_key="test-key",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    with pytest.raises(AdolaAPIError, match="Request failed"):
        client.models()


def test_env_base_url_and_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ADOLA_API_KEY", "env-key")
    monkeypatch.setenv("ADOLA_BASE_URL", "https://env.test/")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://env.test/v1/models"
        assert request.headers["authorization"] == "Bearer env-key"
        return httpx.Response(200, json=load_fixture("models-response.json"))

    client = Adola(http_client=httpx.Client(transport=httpx.MockTransport(handler)))

    assert client.models()[0]["name"] == "Rose 1"


def test_async_client() -> None:
    async def run() -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            assert request.headers["authorization"] == "Bearer async-key"
            return httpx.Response(200, json=load_fixture("compress-response.json"))

        async with AsyncAdola(
            api_key="async-key",
            base_url="https://unit.test",
            http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        ) as client:
            response = await client.compress(input="source")

        assert response["receipt"]["tokens_saved"] == 6

    asyncio.run(run())


@pytest.mark.skipif(not os.getenv("ADOLA_API_KEY"), reason="ADOLA_API_KEY is required")
def test_live_models_and_compress() -> None:
    with Adola() as client:
        assert client.models()[0]["id"] == "rose-1"
        response = client.compress(
            input="Adola trims prompt context before the request reaches a model.",
            query="What does Adola trim?",
            compression={"target_ratio": 0.5},
        )
    assert response["receipt"]["tokens_saved"] >= 0
