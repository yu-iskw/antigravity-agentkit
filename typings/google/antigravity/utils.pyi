from collections.abc import Awaitable, Callable
from typing import Any

AskUserHandler = Callable[..., Awaitable[Any]]

class _InteractiveUtils:
    ask_user_handler: AskUserHandler

interactive: _InteractiveUtils
