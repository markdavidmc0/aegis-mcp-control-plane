package aegis.compliance

default allow := false

# General compliance checks
allow if {
    input.actor_id != ""
    not compliance_violation
}

compliance_violation if {
    input.cost_centre_id == ""
}

compliance_violation if {
    contains(input.arguments.code, "import os")
}

compliance_violation if {
    contains(input.arguments.code, "os.system")
}
