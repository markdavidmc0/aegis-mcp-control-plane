"""LiteLLM Proxy Router for /v1/chat/completions."""

from typing import Any

import httpx
import logfire
from fastapi import APIRouter, Depends, HTTPException, Response, status

from src.control_plane.dependencies import get_data_plane_client, get_user_context
from src.control_plane.failover_router import ModelFailoverRouter
from src.control_plane.schemas import UserContext

router = APIRouter(prefix="/v1", tags=["LLM Proxy"])
failover_router = ModelFailoverRouter()


@router.post("/chat/completions")
async def chat_completions_proxy(
    payload: dict[str, Any],
    response: Response,
    user: UserContext = Depends(get_user_context),
    data_plane_client: httpx.AsyncClient = Depends(get_data_plane_client),
):
    """Proxies chat completions requests to upstream LLM router / Data Plane with failover."""
    if "messages" not in payload or not isinstance(payload["messages"], list):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payload must include a non-empty 'messages' list.",
        )

    headers = {"X-User-ID": user.user_id}
    if user.composite_key:
        headers["X-Actor-ID"] = user.composite_key.actor_id
        headers["X-Agent-ID"] = user.composite_key.agent_id
        headers["X-Cost-Centre-ID"] = user.composite_key.cost_centre_id
        headers["X-Session-ID"] = user.composite_key.session_id
        headers["X-Aegis-URN"] = user.composite_key.urn

    urn = user.composite_key.urn if user.composite_key else None
    with logfire.span(
        "llm_proxy.chat_completions",
        user_id=user.user_id,
        urn=urn,
    ):
        try:
            result, audit_headers = await failover_router.execute_with_failover(
                client=data_plane_client,
                endpoint="/v1/chat/completions",
                payload=payload,
                headers=headers,
            )

            for k, v in audit_headers.items():
                response.headers[k] = v

            return result

        except HTTPException:
            raise
        except Exception as err:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"LLM Routing Execution Failed: {str(err)}",
            ) from err

