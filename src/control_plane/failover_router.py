"""Automated Model Failover routing across model tiers with backoff and audit headers."""

import copy
from typing import Any

import httpx
import logfire
from fastapi import HTTPException, status

from src.control_plane.schemas import ModelFailoverPolicy


class ModelFailoverRouter:
    """Routes LLM completions across primary and fallback model tiers upon failure."""

    def __init__(self, default_policy: ModelFailoverPolicy | None = None) -> None:
        """Initialize ModelFailoverRouter with optional default policy."""
        self.default_policy = default_policy or ModelFailoverPolicy()

    async def execute_with_failover(
        self,
        client: httpx.AsyncClient,
        endpoint: str,
        payload: dict[str, Any],
        headers: dict[str, str] | None = None,
        policy: ModelFailoverPolicy | None = None,
    ) -> tuple[dict[str, Any], dict[str, str]]:
        """Execute chat completion request with tier-based failover and retries."""
        active_policy = policy or self.default_policy
        req_headers = dict(headers or {})
        requested_model = payload.get("model", active_policy.primary_model)

        tiers = [active_policy.primary_model] + [
            t for t in active_policy.fallback_tiers if t != active_policy.primary_model
        ]

        total_attempts = 0
        last_exception: Exception | None = None
        last_status_code: int | None = None

        with logfire.span(
            "llm.model_failover",
            requested_model=requested_model,
            tiers=tiers,
        ) as failover_span:
            for tier_idx, model_tier in enumerate(tiers):
                total_attempts += 1
                current_payload = copy.deepcopy(payload)
                current_payload["model"] = model_tier

                try:
                    res = await client.post(
                        endpoint,
                        json=current_payload,
                        headers=req_headers,
                    )

                    if res.status_code == 200:
                        failover_triggered = tier_idx > 0
                        audit_headers = {
                            "X-Aegis-Model-Requested": requested_model,
                            "X-Aegis-Model-Served": model_tier,
                            "X-Aegis-Failover-Triggered": "true" if failover_triggered else "false",
                            "X-Aegis-Failover-Attempts": str(total_attempts),
                        }
                        failover_span.set_attribute("served_model", model_tier)
                        failover_span.set_attribute("total_attempts", total_attempts)
                        failover_span.set_attribute("failover_triggered", failover_triggered)

                        return res.json(), audit_headers

                    last_status_code = res.status_code
                    if res.status_code in active_policy.retryable_status_codes:
                        continue
                    else:
                        continue

                except (httpx.TimeoutException, httpx.NetworkError) as exc:
                    last_exception = exc
                    continue
                except Exception as exc:
                    last_exception = exc
                    continue

            # If all tiers fail, raise 502 Bad Gateway
            error_msg = (
                f"Model failover exhausted all tiers {tiers} after {total_attempts} attempts. "
                f"Last status code: {last_status_code}, error: {last_exception}"
            )
            failover_span.set_attribute("exhausted", True)
            failover_span.set_attribute("total_attempts", total_attempts)
            if last_status_code == 404:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Upstream model endpoint not found (404): {error_msg}",
                )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=error_msg,
            )

    async def route_completion(
        self,
        payload: dict[str, Any],
        headers: dict[str, str],
        client: httpx.AsyncClient | None = None,
        endpoint: str = "/v1/chat/completions",
        policy: ModelFailoverPolicy | None = None,
    ) -> tuple[dict[str, Any], dict[str, str]]:
        """Convenience method matching route_completion contract."""
        if client is not None:
            return await self.execute_with_failover(
                client=client,
                endpoint=endpoint,
                payload=payload,
                headers=headers,
                policy=policy,
            )
        async with httpx.AsyncClient() as default_client:
            return await self.execute_with_failover(
                client=default_client,
                endpoint=endpoint,
                payload=payload,
                headers=headers,
                policy=policy,
            )
