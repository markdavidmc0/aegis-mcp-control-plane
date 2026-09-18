"""Vortex Silicon OPA / Rego Policy Compliance Gate Demonstration.

Demonstrates client-side observation of zero-trust policy enforcement:
1. Valid tool call (within bounds) -> Allowed.
2. Parameter boundary violation (e.g., matrix_dim > 8192) -> Denied by OPA policy.
3. Unsafe code execution pattern (e.g., import os; os.system) -> Denied by OPA policy.
"""

import asyncio
from typing import Any

import httpx

CONTROL_PLANE_URL = "http://localhost:8000"

IDENTITY_HEADERS = {
    "X-Actor-ID": "usr_vortex_lead",
    "X-User-ID": "usr_vortex_lead",
    "X-Agent-ID": "PolicyDemoAgent",
    "X-Cost-Centre-ID": "silicon-perf-lab",
    "X-Session-ID": "sess-policy-demo-001",
    "X-User-Role": "hardware_engineer",
    "X-User-Scopes": "tools:execute,llm:proxy",
}


async def call_mcp_tool(
    client: httpx.AsyncClient,
    tool_name: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    """Issues a JSON-RPC 2.0 tools/call request to the Control Plane MCP endpoint."""
    payload = {
        "jsonrpc": "2.0",
        "id": f"call-{tool_name}",
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": arguments,
        },
    }
    response = await client.post("/api/v1/mcp", json=payload)
    return response.json()


async def main() -> None:
    """Executes the OPA policy compliance demonstration."""
    print("=" * 70)
    print("AEGIS CONTROL PLANE: OPA / REGO POLICY COMPLIANCE GATE DEMO")
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

        print("\n[Test 1] Valid Tool Call: profile_tensor_kernel with matrix_dim=2048 (<= 8192)")
        res1 = await call_mcp_tool(
            client,
            tool_name="profile_tensor_kernel",
            arguments={"matrix_dim": 2048, "data_type": "float32"},
        )
        if "result" in res1:
            print("Result: ALLOWED by OPA Policy.")
            print(f"Data Plane Output: {res1['result']}")
        else:
            print(f"Response: {res1}")

        print("\n" + "-" * 70)
        print("[Test 2] Policy Violation: profile_tensor_kernel with matrix_dim=16384 (> 8192)")
        print("Expected: OPA Rego rule blocks call and returns JSON-RPC error -32000.")
        res2 = await call_mcp_tool(
            client,
            tool_name="profile_tensor_kernel",
            arguments={"matrix_dim": 16384, "data_type": "float32"},
        )
        if "error" in res2:
            print(f"Result: DENIED by OPA Policy (Code: {res2['error']['code']})")
            print(f"Error Message: {res2['error']['message']}")
        else:
            print(f"Unexpected response: {res2}")

        print("\n" + "-" * 70)
        print("[Test 3] Security Violation: execute_code with unsafe system operation")
        print("Expected: OPA Rego rule blocks code with unsafe patterns.")
        res3 = await call_mcp_tool(
            client,
            tool_name="execute_code",
            arguments={"code": "import os; os.system('ls -la')"},
        )
        if "error" in res3:
            print(f"Result: DENIED by OPA Policy (Code: {res3['error']['code']})")
            print(f"Error Message: {res3['error']['message']}")
        else:
            print(f"Unexpected response: {res3}")


if __name__ == "__main__":
    asyncio.run(main())
