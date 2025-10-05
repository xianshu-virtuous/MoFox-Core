from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from src.llm_models.payload_content.tool_option import ToolCall

from . import BaseDataModel

if TYPE_CHECKING:
    pass


@dataclass
class LLMGenerationDataModel(BaseDataModel):
    content: str | None = None
    reasoning: str | None = None
    model: str | None = None
    tool_calls: list["ToolCall"] | None = None
    prompt: str | None = None
    selected_expressions: list[int] | None = None
    reply_set: list[tuple[str, Any]] | None = None
