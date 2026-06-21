from typing import Any

class Text:
    text: str

class Thought:
    text: str

class ToolCall:
    name: str
    args: object

class ToolResult:
    result: object

class McpStdioServer:
    def __init__(self, *args: Any, **kwargs: Any) -> None: ...
