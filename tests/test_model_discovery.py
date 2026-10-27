"""Unit tests for local model discovery (Ollama & llama.cpp) and edge-case handling."""

import pytest
import httpx
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.services.llm_service import LLMService
from app.core.models import ModelDiscoveryResponse, LocalModelInfo


# --- SERVICE LAYER TESTS ---

def test_format_size_bytes_helper():
    """Verify byte formatting helper function."""
    assert LLMService._format_size_bytes(None) is None
    assert LLMService._format_size_bytes(-5) is None
    assert LLMService._format_size_bytes(500) == "500 B"
    assert LLMService._format_size_bytes(2048) == "2.0 KB"
    assert LLMService._format_size_bytes(5 * 1024 * 1024) == "5.0 MB"
    assert LLMService._format_size_bytes(4500000000) == "4.2 GB"


@pytest.mark.asyncio
async def test_discover_ollama_http_error(monkeypatch):
    """Verify handling when Ollama returns non-200 HTTP code."""
    async def mock_get(*args, **kwargs):
        return httpx.Response(500, text="Internal Server Error")

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    res: ModelDiscoveryResponse = await LLMService.discover_local_models("local-ollama")
    assert res.is_connected is False
    assert "error status http 500" in res.status_message.lower()


@pytest.mark.asyncio
async def test_discover_ollama_generic_exception(monkeypatch):
    """Verify handling when an unexpected error occurs during Ollama query."""
    async def mock_get(*args, **kwargs):
        raise RuntimeError("Unexpected OS error")

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    res: ModelDiscoveryResponse = await LLMService.discover_local_models("local-ollama")
    assert res.is_connected is False
    assert "unexpected os error" in res.status_message.lower()


@pytest.mark.asyncio
async def test_discover_llamacpp_http_error(monkeypatch):
    """Verify handling when llama.cpp returns non-200 HTTP code."""
    async def mock_get(*args, **kwargs):
        return httpx.Response(502, text="Bad Gateway")

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    res: ModelDiscoveryResponse = await LLMService.discover_local_models("local-llamacpp")
    assert res.is_connected is False
    assert "error status http 502" in res.status_message.lower()


@pytest.mark.asyncio
async def test_discover_llamacpp_timeout(monkeypatch):
    """Verify handling when llama.cpp request times out."""
    async def mock_get(*args, **kwargs):
        raise httpx.TimeoutException("Query timed out")

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    res: ModelDiscoveryResponse = await LLMService.discover_local_models("local-llamacpp")
    assert res.is_connected is False
    assert "timed out" in res.status_message.lower()


@pytest.mark.asyncio
async def test_discover_llamacpp_generic_exception(monkeypatch):
    """Verify handling when an unexpected error occurs during llama.cpp query."""
    async def mock_get(*args, **kwargs):
        raise RuntimeError("Unexpected connection socket error")

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    res: ModelDiscoveryResponse = await LLMService.discover_local_models("local-llamacpp")
    assert res.is_connected is False
    assert "unexpected connection socket error" in res.status_message.lower()


@pytest.mark.asyncio
async def test_discover_ollama_success(monkeypatch):
    """Verify successful Ollama model discovery and normalization."""
    mock_payload = {
        "models": [
            {
                "name": "llama3.1:8b",
                "model": "llama3.1:8b",
                "size": 4920730000,
                "modified_at": "2026-10-20T14:32:00Z",
                "details": {
                    "format": "gguf",
                    "family": "llama",
                    "parameter_size": "8.0B",
                    "quantization_level": "Q4_K_M"
                }
            },
            {
                "name": "mistral:7b-instruct",
                "size": 4100000000,
                "details": {
                    "parameter_size": "7.2B",
                    "quantization_level": "Q4_0"
                }
            }
        ]
    }

    async def mock_get(*args, **kwargs):
        return httpx.Response(200, json=mock_payload)

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    res: ModelDiscoveryResponse = await LLMService.discover_local_models("local-ollama")
    assert res.is_connected is True
    assert res.provider == "local-ollama"
    assert res.total_models == 2
    assert len(res.models) == 2

    # Check model 1 metadata
    m1 = res.models[0]
    assert m1.id == "llama3.1:8b"
    assert m1.parameter_count == "8.0B"
    assert m1.quantization_format == "Q4_K_M"
    assert "4.6 GB" in m1.size_human or "4.5 GB" in m1.size_human or "GB" in m1.size_human
    assert m1.status == "available"


@pytest.mark.asyncio
async def test_discover_ollama_empty_models(monkeypatch):
    """Verify handling when Ollama is running but no models are installed."""
    async def mock_get(*args, **kwargs):
        return httpx.Response(200, json={"models": []})

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    res: ModelDiscoveryResponse = await LLMService.discover_local_models("local-ollama")
    assert res.is_connected is True
    assert res.total_models == 0
    assert len(res.models) == 0
    assert "no models" in res.status_message.lower()


@pytest.mark.asyncio
async def test_discover_ollama_connection_error(monkeypatch):
    """Verify handling when Ollama daemon is offline / connection refused."""
    async def mock_get(*args, **kwargs):
        raise httpx.ConnectError("Connection refused to 11434")

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    res: ModelDiscoveryResponse = await LLMService.discover_local_models("local-ollama")
    assert res.is_connected is False
    assert res.total_models == 0
    assert "not running" in res.status_message.lower() or "unreachable" in res.status_message.lower()


@pytest.mark.asyncio
async def test_discover_ollama_timeout(monkeypatch):
    """Verify handling when Ollama request times out."""
    async def mock_get(*args, **kwargs):
        raise httpx.TimeoutException("Query timed out")

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    res: ModelDiscoveryResponse = await LLMService.discover_local_models("local-ollama")
    assert res.is_connected is False
    assert "timed out" in res.status_message.lower()


@pytest.mark.asyncio
async def test_discover_llamacpp_success(monkeypatch):
    """Verify successful llama.cpp model discovery and normalization."""
    mock_payload = {
        "data": [
            {
                "id": "qwen2.5-coder-7b-instruct.Q4_K_M.gguf",
                "object": "model",
                "created": 1729000000,
                "owned_by": "llamacpp",
                "meta": {
                    "parameters": "7B",
                    "quantization": "Q4_K_M",
                    "size": 4480000000
                }
            }
        ]
    }

    async def mock_get(*args, **kwargs):
        return httpx.Response(200, json=mock_payload)

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    res: ModelDiscoveryResponse = await LLMService.discover_local_models("local-llamacpp")
    assert res.is_connected is True
    assert res.provider == "local-llamacpp"
    assert res.total_models == 1
    m = res.models[0]
    assert m.id == "qwen2.5-coder-7b-instruct.Q4_K_M.gguf"
    assert m.parameter_count == "7B"
    assert m.quantization_format == "Q4_K_M"
    assert m.status == "available"


@pytest.mark.asyncio
async def test_discover_llamacpp_connection_error(monkeypatch):
    """Verify handling when llama.cpp server is offline."""
    async def mock_get(*args, **kwargs):
        raise httpx.ConnectError("Connection refused to port 8000")

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    res: ModelDiscoveryResponse = await LLMService.discover_local_models("local-llamacpp")
    assert res.is_connected is False
    assert "not running" in res.status_message.lower() or "unreachable" in res.status_message.lower()


@pytest.mark.asyncio
async def test_discover_unsupported_provider():
    """Verify unsupported provider returns graceful response."""
    res: ModelDiscoveryResponse = await LLMService.discover_local_models("unsupported-provider")
    assert res.is_connected is False
    assert "unsupported" in res.status_message.lower()


# --- REST API ENDPOINT TESTS ---

@pytest.mark.asyncio
async def test_api_local_models_endpoint_success(monkeypatch):
    """Verify GET /api/models/local returns 200 with model list."""
    async def mock_discover(provider: str):
        return ModelDiscoveryResponse(
            provider=provider,
            endpoint_url="http://localhost:11434/api/tags",
            is_connected=True,
            models=[
                LocalModelInfo(
                    id="deepseek-coder:6.7b",
                    name="deepseek-coder:6.7b",
                    provider=provider,
                    parameter_count="6.7B",
                    quantization_format="Q4_K_M",
                    size_human="3.8 GB",
                    status="available"
                )
            ],
            total_models=1,
            status_message="Connected"
        )

    monkeypatch.setattr(LLMService, "discover_local_models", mock_discover)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/models/local?provider=local-ollama")
        assert response.status_code == 200
        data = response.json()
        assert data["is_connected"] is True
        assert data["total_models"] == 1
        assert data["models"][0]["id"] == "deepseek-coder:6.7b"


@pytest.mark.asyncio
async def test_api_local_models_endpoint_offline(monkeypatch):
    """Verify GET /api/models/local returns 503 when backend is offline."""
    async def mock_discover(provider: str):
        return ModelDiscoveryResponse(
            provider=provider,
            endpoint_url="http://localhost:11434/api/tags",
            is_connected=False,
            models=[],
            total_models=0,
            status_message="Ollama server is not running or unreachable at localhost:11434."
        )

    monkeypatch.setattr(LLMService, "discover_local_models", mock_discover)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/models/local?provider=local-ollama")
        assert response.status_code == 503
        data = response.json()
        assert data["is_connected"] is False
        assert "not running" in data["status_message"].lower()
