"""The tool list sent to the model, and the system prompt. Section 2.1 and 2.3."""

SYSTEM_PROMPT = (
    "You are a coding agent. You are working in the directory {workdir}.\n"
    "Use the provided tools to complete the user's task.\n"
    "Call finish when the task is done or cannot be done."
)

_STR = {"type": "string"}

TOOLS = [
    {
        "name": "edit_file",
        "description": "Replace the one occurrence of `old` in a file with `new`.",
        "parameters": {
            "type": "object",
            "properties": {"path": _STR, "old": _STR, "new": _STR},
            "required": ["path", "old", "new"],
        },
    },
    {
        "name": "finish",
        "description": "End the run, reporting whether the task succeeded.",
        "parameters": {
            "type": "object",
            "properties": {"success": {"type": "boolean"}, "summary": _STR},
            "required": ["success", "summary"],
        },
    },
    {
        "name": "list_dir",
        "description": "List the entries of a directory, one per line.",
        "parameters": {
            "type": "object",
            "properties": {"path": _STR},
            "required": ["path"],
        },
    },
    {
        "name": "read_file",
        "description": "Read a UTF-8 text file.",
        "parameters": {
            "type": "object",
            "properties": {"path": _STR},
            "required": ["path"],
        },
    },
    {
        "name": "run_command",
        "description": "Run a shell command in the workspace.",
        "parameters": {
            "type": "object",
            "properties": {"command": _STR},
            "required": ["command"],
        },
    },
    {
        "name": "todo_write",
        "description": "Replace the todo list with `items`.",
        "parameters": {
            "type": "object",
            "properties": {"items": {"type": "array"}},
            "required": ["items"],
        },
    },
    {
        "name": "write_file",
        "description": "Write a UTF-8 text file, creating parent directories.",
        "parameters": {
            "type": "object",
            "properties": {"path": _STR, "content": _STR},
            "required": ["path", "content"],
        },
    },
]

# Argument name -> the JSON type it must have. Section 3.
ARG_TYPES = {
    "path": str,
    "old": str,
    "new": str,
    "content": str,
    "command": str,
    "summary": str,
    "success": bool,
    "items": list,
}

REQUIRED = {t["name"]: t["parameters"]["required"] for t in TOOLS}
