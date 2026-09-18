package aegis.tools

default allow := false

# Allow if actor has tools:execute scope and arguments are valid
allow if {
    input.scope == "tools:execute"
    not arguments_violation
}

arguments_violation if {
    input.tool == "profile_tensor_kernel"
    input.arguments.matrix_dim > 8192
}

arguments_violation if {
    contains(input.arguments.code, "import os")
}

arguments_violation if {
    contains(input.arguments.code, "os.system")
}
