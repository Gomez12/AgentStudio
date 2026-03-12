TOOL_METADATA = {
    "name": "echo",
    "description": "Echo the provided text back to the agent.",
    "input_schema": {
        "type": "object",
        "properties": {
            "text": {"type": "string"},
        },
        "required": ["text"],
    },
}


def build_tool():
    def echo(*, text: str) -> str:
        return text

    return echo
