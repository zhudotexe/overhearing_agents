from typing import Callable, TYPE_CHECKING

import outlines
import transformers
from kani import AIFunction, ChatMessage
from kani.engines import WrapperEngine

if TYPE_CHECKING:
    from kani.engines.huggingface import HuggingEngine
    from kani.engines.openai import OpenAIEngine


class GuidedHFEngine(WrapperEngine):
    """
    A constrained decoding engine.
    """

    def __init__(
        self, engine, *args, guidance_re: str | Callable[[list[ChatMessage], list[AIFunction] | None], str], **kwargs
    ):
        """
        :param engine: The engine to wrap
        :param guidance_re: The regex to enforce decoding to,
            or a callable that creates a regex given chat history and functions.
        """

        super().__init__(engine, *args, **kwargs)
        self.engine: "HuggingEngine"  # type hint for IDEs
        self.guidance_re = guidance_re
        self.outlines_tokenizer = outlines.models.TransformerTokenizer(self.engine.tokenizer)

    def create_logits_processor(self, messages: list[ChatMessage], functions: list[AIFunction] | None):
        if isinstance(self.guidance_re, str):
            regex_string = self.guidance_re
        else:
            regex_string = self.guidance_re(messages, functions)
        json_logits_processor = outlines.processors.RegexLogitsProcessor(regex_string, self.outlines_tokenizer)
        return transformers.LogitsProcessorList([json_logits_processor])

    async def predict(self, messages: list[ChatMessage], functions: list[AIFunction] | None = None, **hyperparams):
        # each time we call predict or stream, pass a new instance of JSONLogitsProcessor
        if "logits_processor" not in hyperparams:
            hyperparams["logits_processor"] = self.create_logits_processor(messages, functions)
        return await super().predict(messages=messages, functions=functions, **hyperparams)

    async def stream(self, messages: list[ChatMessage], functions: list[AIFunction] | None = None, **hyperparams):
        # each time we call predict or stream, pass a new instance of JSONLogitsProcessor
        if "logits_processor" not in hyperparams:
            hyperparams["logits_processor"] = self.create_logits_processor(messages, functions)
        async for elem in super().stream(messages=messages, functions=functions, **hyperparams):
            yield elem


class GuidedOAIEngine(WrapperEngine):
    """
    A constrained decoding engine. The wrapped engine must be an OpenAIEngine proxying a vLLM instance.
    """

    def __init__(
        self, engine, *args, guidance_re: str | Callable[[list[ChatMessage], list[AIFunction] | None], str], **kwargs
    ):
        super().__init__(engine, *args, **kwargs)
        self.engine: "OpenAIEngine"  # type hint for IDEs
        self.guidance_re = guidance_re

    def _set_hyperparams(self, hyperparams: dict, messages, functions) -> dict:
        if "extra_body" not in hyperparams:
            hyperparams["extra_body"] = self.hyperparams.get("extra_body", {})
        if isinstance(self.guidance_re, str):
            regex_str = self.guidance_re
        else:
            regex_str = self.guidance_re(messages, functions)
        hyperparams["extra_body"].setdefault("guided_regex", regex_str)
        hyperparams["extra_body"].setdefault("guided_decoding_backend", "outlines")
        return hyperparams

    async def predict(self, messages: list[ChatMessage], functions: list[AIFunction] | None = None, **hyperparams):
        # each time we call predict or stream, ensure we pass the guided decoding regex
        self._set_hyperparams(hyperparams, messages, functions)
        return await super().predict(messages=messages, functions=functions, **hyperparams)

    async def stream(self, messages: list[ChatMessage], functions: list[AIFunction] | None = None, **hyperparams):
        self._set_hyperparams(hyperparams, messages, functions)
        async for elem in super().stream(messages=messages, functions=functions, **hyperparams):
            yield elem
