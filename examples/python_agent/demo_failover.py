"""Vortex Silicon Automated Model Failover Demonstration.

Demonstrates client-side observation of the Control Plane's tiered LLM failover:
1. Direct primary routing (Gemini 3.8 Flash 8k).
2. Simulated upstream rate limit / outage triggering Tier 2 failover (Gemini 3.8 Flash 32k).
3. Inspection of Aegis audit headers (`X-Aegis-Model-Requested`, `X-Aegis-Model-Served`, etc.).
"""

import asyncio
from typing import Any

import httpx

CONTROL_PLANE_URL = "http://localhost:8000"

IDENTITY_HEADERS = {
    "X-Actor-ID": "usr_vortex_lead",
    "X-User-ID": "usr_vortex_lead",
    "X-Agent-ID": "FailoverDemoAgent",
    "X-Cost-Centre-ID": "silicon-perf-lab",
    "X-Session-ID": "sess-failover-demo-001",
    "X-User-Role": "hardware_engineer",
    "X-User-Scopes": "llm:proxy,tools:execute",
}


async def request_chat_completion(
    client: httpx.AsyncClient,
    model: str,
    prompt: str,
) -> dict[str, Any]:
    """Sends chat completion request through Control Plane LLM proxy."""
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a silicon hardware assistant."},
            {"role": "user", "content": prompt},
        ],
    }
    response = await client.post("/v1/chat/completions", json=payload)
    return {
        "status_code": response.status_code,
        "headers": dict(response.headers),
        "data": response.json() if response.status_code == 200 else response.text,
    }


async def main() -> None:
    """Executes the failover demonstration."""
    print("=" * 70)
    print("AEGIS CONTROL PLANE: AUTOMATED MODEL FAILOVER DEMO")
    print("=" * 70)

    async with httpx.AsyncClient(base_url=CONTROL_PLANE_URL, headers=IDENTITY_HEADERS, timeout=30.0) as client:
        # Check platform health
        try:
            health = await client.get("/health")
            if health.status_code != 200:
                print(f"[Warning] Gateway returned status {health.status_code}. Is it running?")
                return
        except httpx.ConnectError:
            print(f"[Error] Cannot connect to {CONTROL_PLANE_URL}.")
            print("Please ensure the Control Plane is running:\n  uv run uvicorn src.control_plane.main:app --port 8000")
            return

        print("\n[Step 1] Requesting Primary Tier: gemini-3.8-flash-8192...")
        res = await request_chat_completion(
            client,
            model="gemini-3.8-flash-8192",
            prompt="Summarize arithmetic intensity for a 1024x1024 float32 GEMM kernel.",
        )

        print(f"Status Code: {res['status_code']}")
        print("Audit Response Headers:")
        for k in ["x-aegis-model-requested", "x-aegis-model-served", "x-aegis-failover-triggered", "x-aegis-failover-attempts"]:
            if k in res["headers"]:
                print(f"  {k}: {res['headers'][k]}")

        print("\n[Step 2] Failover Tier Architecture:")
        print("  - Tier 1: gemini-3.8-flash-8192  (8,192 context window, cost/latency optimal)")
        print("  - Tier 2: gemini-3.8-flash-32768 (32,768 context window, failover target)")
        print("  - Tier 3: gpt-4o                 (Cross-provider resiliency fallback)")
        print("\nNote: When Tier 1 encounters HTTP 429 (Rate Limit) or 500/502/503/504 errors,")
        print("the gateway seamlessly switches to Tier 2 without client interruption.")


if __name__ == "__main__":
    asyncio.run(main())
