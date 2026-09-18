package aegis.handoff

default allow := false

# Only SUPERVISOR callers can hand off to authorized sub-agents
allow if {
    input.caller_topology == "SUPERVISOR"
    target_authorized
}

target_authorized if {
    input.target_agent_id == input.authorized_targets[_]
}
