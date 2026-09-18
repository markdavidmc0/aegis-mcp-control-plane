"""Security Threat Mitigation & OWASP Vulnerability Audit Test Suite.

Validates process sandbox isolation, credential shielding, resource exhaustion limits,
and path traversal defenses for the Data Plane execution environment.
"""

import pytest

from src.data_plane.schemas import DataPlaneUserContext
from src.data_plane.worker import DataPlaneSandboxRunner, LocalToolDispatcher

# ---------------------------------------------------------------------------
# FIXTURES
# ---------------------------------------------------------------------------

@pytest.fixture
def sandbox_runner() -> DataPlaneSandboxRunner:
    """Returns a DataPlaneSandboxRunner instance configured with strict 2-second timeout."""
    return DataPlaneSandboxRunner(timeout_seconds=2.0)


@pytest.fixture
def local_dispatcher(tmp_path) -> LocalToolDispatcher:
    """Returns a LocalToolDispatcher configured with an isolated temporary tool directory."""
    tools_dir = tmp_path / "arm-tools"
    tools_dir.mkdir(parents=True, exist_ok=True)
    return LocalToolDispatcher(tools_dir=str(tools_dir))


@pytest.fixture
def dummy_user_context() -> DataPlaneUserContext:
    """Provides a task-isolated user context with execute permissions."""
    return DataPlaneUserContext(
        user_id="usr_sec_audit",
        role="developer",
        scopes=["tools:execute"],
    )


# ---------------------------------------------------------------------------
# 1. OWASP AGENT-01 / RCE: Host File System & GCP Metadata Isolation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.security
async def test_gcp_metadata_and_host_proc_harvesting_blocked(
    sandbox_runner: DataPlaneSandboxRunner,
    dummy_user_context: DataPlaneUserContext,
):
    """OWASP AGENT-01 & LLM02 Defense Test.

    Verifies malicious Python payloads inside the Data Plane sandbox cannot exfiltrate
    GCP Node Service Account tokens via internal Metadata IPs or inspect the host proc table.
    """
    malicious_script = """
import urllib.request
import os

# Attack 1: Attempt Host Process Table Probe
try:
    proc_data = os.listdir('/proc/1/root/etc')
    print(f"PROC_EXPOSED: {proc_data}")
except Exception as e:
    print(f"BLOCKED_PROC: {type(e).__name__}")

# Attack 2: Attempt GCP Metadata Credential Exfiltration
try:
    req = urllib.request.Request(
        "http://169.254.169.254/computeMetadata/v1/instance/service-accounts/default/token"
    )
    req.add_header("Metadata-Flavor", "Google")
    with urllib.request.urlopen(req, timeout=1) as response:
        print(f"METADATA_EXPOSED: {response.read().decode('utf-8')}")
except Exception as e:
    print(f"BLOCKED_METADATA: {type(e).__name__}")
"""

    res = await sandbox_runner.execute_payload(
        code_snippet=malicious_script,
        user_context=dummy_user_context,
    )

    stdout = res.get("stdout", "")

    assert "access_token" not in stdout, "CRITICAL: GCP Metadata Token was harvested!"
    assert "PROC_EXPOSED" not in stdout, "CRITICAL: Host filesystem /proc table was exposed!"


# ---------------------------------------------------------------------------
# 2. OWASP AGENT-03 / LLM05: Environment Variable & Secret Shielding
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.security
async def test_env_var_secret_harvesting_shielded(
    sandbox_runner: DataPlaneSandboxRunner,
    dummy_user_context: DataPlaneUserContext,
    monkeypatch,
):
    """OWASP AGENT-03 & LLM05 Defense Test.

    Ensures sensitive host environment variables (e.g. API keys) are protected
    from untrusted code execution snippets.
    """
    monkeypatch.setenv("OPENAI_API_KEY", "sk-proj-CRITICAL-HOST-KEY-EXPOSED")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-CRITICAL-HOST-KEY-EXPOSED")

    harvest_script = """
import os
print("KEYS:", os.environ.get('OPENAI_API_KEY'), os.environ.get('ANTHROPIC_API_KEY'))
"""

    res = await sandbox_runner.execute_payload(
        code_snippet=harvest_script,
        user_context=dummy_user_context,
    )

    stdout = res.get("stdout", "")

    assert "sk-proj-CRITICAL-HOST-KEY-EXPOSED" not in stdout
    assert "sk-ant-CRITICAL-HOST-KEY-EXPOSED" not in stdout


# ---------------------------------------------------------------------------
# 3. OWASP LLM04: Resource Exhaustion & DoS Protection
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.security
async def test_resource_exhaustion_infinite_loop_timeout(
    sandbox_runner: DataPlaneSandboxRunner,
    dummy_user_context: DataPlaneUserContext,
):
    """OWASP LLM04 DoS Defense Test.

    Proves an infinite loop or CPU exhaustion attempt inside a snippet
    is forcefully interrupted by the process timeout boundary.
    """
    infinite_loop_script = "while True:\n    pass"

    res = await sandbox_runner.execute_payload(
        code_snippet=infinite_loop_script,
        user_context=dummy_user_context,
    )

    assert res.get("status") == "error"
    assert "timed out" in res.get("error", "").lower()


# ---------------------------------------------------------------------------
# 4. Path Traversal Defenses
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.security
async def test_path_traversal_prevention_in_dispatcher(
    local_dispatcher: LocalToolDispatcher,
    dummy_user_context: DataPlaneUserContext,
):
    """Input Sanitization Test.

    Ensures tool execution requests targeting arbitrary host binaries (e.g. ../../../bin/bash)
    are trapped and rejected by LocalToolDispatcher.
    """
    path_traversal_tools = [
        "../../../../bin/sh",
        "../etc/passwd",
        "/usr/bin/python3",
        "..\\..\\cmd.exe",
    ]

    for malicious_tool in path_traversal_tools:
        response = await local_dispatcher.dispatch_tool_call(
            tool_name=malicious_tool,
            arguments={"query": "test"},
            user_context=dummy_user_context,
        )

        assert response.get("jsonrpc") == "2.0"
        assert "error" in response
        assert response["error"]["code"] in [-32601, -32602]


# ---------------------------------------------------------------------------
# 5. OWASP AGENT-02: Identity Spoofing & Composite Key Boundary Enforcement
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.security
async def test_composite_key_identity_enforcement():
    """OWASP AGENT-02 Defense Test.

    Validates that DataPlaneUserContext preserves composite key identity
    and enforces validation constraints against injection payloads.
    """
    from pydantic import ValidationError

    from src.data_plane.schemas import AgentCompositeKey

    # Attack: Header Injection / Path Traversal inside composite key elements
    malicious_inputs = [
        "actor\r\nInjected-Header: evil",
        "actor/../etc/passwd",
        "actor;rm -rf /",
        "actor:urn:tamper",
    ]

    for bad_actor in malicious_inputs:
        with pytest.raises(ValidationError):
            AgentCompositeKey(
                actor_id=bad_actor,
                agent_id="agent",
                cost_centre_id="cc",
                session_id="sess",
            )
