"""Unit tests for Automated Model Failover routing and policies."""

from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from src.control_plane.failover_router import ModelFailoverPolicy, ModelFailoverRouter


@pytest.mark.unit
def test_model_failover_policy_schema_defaults() -> None:
    """Validate ModelFailoverPolicy default schema, immutability, and extra forbid."""
    policy = ModelFailoverPolicy()
    assert policy.primary_model == "gemini-3.8-flash-8192"
    assert policy.fallback_tiers == ["gemini-3.8-flash-32768", "gpt-4o"]
    assert policy.max_retries_per_tier >= 1

    # Assert immutability (frozen=True)
    with pytest.raises(ValidationError):
        policy.primary_model = "claude-3-5-sonnet"  # type: ignore[misc]

    # Assert extra="forbid"
    with pytest.raises(ValidationError):
        ModelFailoverPolicy(unexpected_arg="invalid")  # type: ignore[call-arg]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_primary_model_succeeds_directly_no_failover() -> None:
    """Primary model succeeds directly on first attempt (200 OK), no failover triggered."""
    router = ModelFailoverRouter()
    mock_client = AsyncMock(spec=httpx.AsyncClient)

    # Mock 200 OK response from primary model
    mock_response = httpx.Response(
        status_code=200,
        json={"choices": [{"message": {"role": "assistant", "content": "Primary success"}}]},
        headers={"Content-Type": "application/json"},
    )
    mock_client.post.return_value = mock_response

    payload = {
        "model": "gemini-3.8-flash-8192",
        "messages": [{"role": "user", "content": "Hello"}],
    }

    result, headers = await router.execute_with_failover(
        client=mock_client,
        endpoint="/v1/chat/completions",
        payload=payload,
    )

    assert result["choices"][0]["message"]["content"] == "Primary success"
    assert headers["X-Aegis-Model-Requested"] == "gemini-3.8-flash-8192"
    assert headers["X-Aegis-Model-Served"] == "gemini-3.8-flash-8192"
    assert headers["X-Aegis-Failover-Triggered"] == "false"
    assert mock_client.post.call_count == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_primary_rate_limited_failover_to_tier_2_success() -> None:
    """Primary returns 429 Rate Limited; failover switches to Tier 2 and succeeds with audit headers."""
    router = ModelFailoverRouter()
    mock_client = AsyncMock(spec=httpx.AsyncClient)

    # Primary returns 429, Tier 2 returns 200 OK
    res_429 = httpx.Response(
        status_code=429,
        json={"error": "Rate limit exceeded"},
        headers={"Content-Type": "application/json"},
    )
    res_200 = httpx.Response(
        status_code=200,
        json={"choices": [{"message": {"role": "assistant", "content": "Tier 2 success"}}]},
        headers={"Content-Type": "application/json"},
    )

    mock_client.post.side_effect = [res_429, res_200]

    payload = {
        "model": "gemini-3.8-flash-8192",
        "messages": [{"role": "user", "content": "Hello"}],
    }

    result, headers = await router.execute_with_failover(
        client=mock_client,
        endpoint="/v1/chat/completions",
        payload=payload,
    )

    assert result["choices"][0]["message"]["content"] == "Tier 2 success"
    assert headers["X-Aegis-Model-Requested"] == "gemini-3.8-flash-8192"
    assert headers["X-Aegis-Model-Served"] == "gemini-3.8-flash-32768"
    assert headers["X-Aegis-Failover-Triggered"] == "true"
    assert mock_client.post.call_count == 2


@pytest.mark.unit
@pytest.mark.asyncio
async def test_primary_and_tier_2_fail_tier_3_succeeds() -> None:
    """Primary and Tier 2 fail (500/503); failover switches to Tier 3 (gpt-4o) which succeeds."""
    router = ModelFailoverRouter()
    mock_client = AsyncMock(spec=httpx.AsyncClient)

    res_500 = httpx.Response(
        status_code=500,
        json={"error": "Internal Server Error"},
        headers={"Content-Type": "application/json"},
    )
    res_503 = httpx.Response(
        status_code=503,
        json={"error": "Service Unavailable"},
        headers={"Content-Type": "application/json"},
    )
    res_200 = httpx.Response(
        status_code=200,
        json={"choices": [{"message": {"role": "assistant", "content": "Tier 3 gpt-4o success"}}]},
        headers={"Content-Type": "application/json"},
    )

    mock_client.post.side_effect = [res_500, res_503, res_200]

    payload = {
        "model": "gemini-3.8-flash-8192",
        "messages": [{"role": "user", "content": "Compute task"}],
    }

    result, headers = await router.execute_with_failover(
        client=mock_client,
        endpoint="/v1/chat/completions",
        payload=payload,
    )

    assert result["choices"][0]["message"]["content"] == "Tier 3 gpt-4o success"
    assert headers["X-Aegis-Model-Requested"] == "gemini-3.8-flash-8192"
    assert headers["X-Aegis-Model-Served"] == "gpt-4o"
    assert headers["X-Aegis-Failover-Triggered"] == "true"
    assert mock_client.post.call_count == 3


@pytest.mark.unit
@pytest.mark.asyncio
async def test_all_tiers_fail_raises_502_bad_gateway() -> None:
    """All tiers fail; raises HTTPException(502 Bad Gateway) exhaustion error."""
    router = ModelFailoverRouter()
    mock_client = AsyncMock(spec=httpx.AsyncClient)

    res_429 = httpx.Response(status_code=429, json={"error": "Rate limit exceeded"})
    res_500 = httpx.Response(status_code=500, json={"error": "Internal error"})
    res_502 = httpx.Response(status_code=502, json={"error": "Bad gateway"})

    mock_client.post.side_effect = [res_429, res_500, res_502]

    payload = {
        "model": "gemini-3.8-flash-8192",
        "messages": [{"role": "user", "content": "Fail all"}],
    }

    with pytest.raises(HTTPException) as exc_info:
        await router.execute_with_failover(
            client=mock_client,
            endpoint="/v1/chat/completions",
            payload=payload,
        )

    assert exc_info.value.status_code == 502
    assert "exhausted" in exc_info.value.detail.lower()
