from collections.abc import AsyncIterator
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

class ChatResponse:
    @property
    def chunks(self) -> AsyncIterator[Text | Thought | ToolCall | ToolResult]: ...
    async def text(self) -> str: ...

class Agent:
    def __init__(self, *args: Any, **kwargs: Any) -> None: ...
    async def __aenter__(self) -> Agent: ...
    async def __aexit__(self, *args: Any) -> None: ...
    async def chat(self, prompt: str) -> ChatResponse: ...

class LocalAgentConfig:
    def __init__(self, *args: Any, **kwargs: Any) -> None: ...
