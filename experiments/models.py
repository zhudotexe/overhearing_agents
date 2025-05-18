"""
This file contains the implementations for each engine.
"""

import dataclasses
from typing import Literal

from kani import Kani

from experiments.prompts import read_prompt
from experiments.prompts.fewshot_noreason import FEWSHOT_REACT_NOREASON
from experiments.prompts.fewshot_react import FEWSHOT_REACT
from experiments.prompts.fewshot_transcribe import FEWSHOT_REACT_TRANSCRIBE
from overhearing_agents.engines.deduplicate import ResetContextOnDuplicatesMixin
from overhearing_agents.kanis.base import BaseKani, BaseRealtimeKani
from overhearing_agents.kanis.dnd import DNDMixin

TEXT_EXPERIMENT_TYPES = ["text-zeroshot", "text-fewshot", "text-fewshot-noreason"]
AUDIO_EXPERIMENT_TYPES = ["audio-zeroshot", "audio-fewshot", "audio-fewshot-transcribe", "audio-fewshot-noreason"]

MODEL_COMPAT_MATRIX = [
    # --- gpt-4o ---
    (
        "openai",
        [
            "text-zeroshot",
            "text-zeroshot-noreason",
            "audio-zeroshot",
            "audio-zeroshot-noreason",
            "audio-zeroshot-transcribe",
        ],
    ),
    # --- gpt-4o-mini ---
    (
        "openai-mini",
        [
            "text-zeroshot",
            "text-zeroshot-noreason",
            "audio-zeroshot",
            "audio-zeroshot-noreason",
            "audio-zeroshot-transcribe",
        ],
    ),
    # --- ultravox-0.5-llama-3.3-70b ---
    ("ultravox", [*TEXT_EXPERIMENT_TYPES, *AUDIO_EXPERIMENT_TYPES]),
    # --- qwen-2.5-omni ---
    ("qwen-25", [*TEXT_EXPERIMENT_TYPES, *AUDIO_EXPERIMENT_TYPES]),
    # --- phi-4-multimodal-instruct ---
    ("phi-4", [*TEXT_EXPERIMENT_TYPES, *AUDIO_EXPERIMENT_TYPES]),
    # --- ultravox-0.5-llama-3.2-1b ---
    ("ultravox-tiny", [*TEXT_EXPERIMENT_TYPES, *AUDIO_EXPERIMENT_TYPES]),
    # --- step-audio-chat ---
    # ("step-audio-chat", ["text-fewshot", "audio-fewshot"]),
    # --- text only ---
    ("text", ["spans"]),
]
ALL_MODELS = [f"{model}.{exptype}" for model, exptypes in MODEL_COMPAT_MATRIX for exptype in exptypes]

AUDIO_SYSTEM_PROMPT = read_prompt("realtime_tom_0shot_audio.md")
AUDIO_TRANSCRIBE_SYSTEM_PROMPT = read_prompt("realtime_tom_0shot_audio_transcribe.md")
AUDIO_NOREASON_SYSTEM_PROMPT = read_prompt("realtime_noreason_0shot_audio.md")
TEXT_SYSTEM_PROMPT = read_prompt("realtime_tom_0shot_text.md")
TEXT_NOREASON_SYSTEM_PROMPT = read_prompt("realtime_noreason_0shot_text.md")

# common kwargs for using an oai client with vllm
VLLM_OAI_KWARGS = dict(
    api_base=f"http://127.0.0.1:16724/v1",
    api_key="<the library wants this but it isn't needed>",
    timeout=600,
)


# ==== kani cls impls ====
class OverhearingKaniRealtime(DNDMixin, BaseRealtimeKani):
    pass


class OverhearingKani(DNDMixin, BaseKani):
    pass


class ResetOnDuplicatesOverhearingKani(ResetContextOnDuplicatesMixin, OverhearingKani):
    pass


# ==== experiment config ====
@dataclasses.dataclass
class ExperimentConfig:
    ai: Kani | None
    modality: Literal["audio", "text", "text-span"]
    yield_every: float = 10  # size of audio chunks to send to model


# ==== engine impls ====
async def config_for_key(model_key: str) -> ExperimentConfig:
    """Return a tuple with the kani (ready for querying) and the model type."""
    if model_key == "text.spans":
        return ExperimentConfig(ai=None, modality="text-span")

    model_name, exp_type = model_key.split(".")
    modality, prompt_type = exp_type.split("-", 1)

    # ==== openai ====
    # gpt-4o-realtime-preview-2024-12-17
    if model_name == "openai" and modality == "audio":
        if prompt_type == "zeroshot-transcribe":
            system_prompt = read_prompt("realtime_tom_0shot_audio_transcribe_openai.md")
        elif prompt_type == "zeroshot-noreason":
            system_prompt = read_prompt("realtime_noreason_0shot_audio_openai.md")
        else:  # zeroshot
            system_prompt = AUDIO_SYSTEM_PROMPT

        ai = OverhearingKaniRealtime(model="gpt-4o-realtime-preview-2024-12-17")
        await ai.connect(
            instructions=system_prompt,
            modalities=["text"],
            temperature=0.8,
        )
        return ExperimentConfig(ai=ai, modality="audio")

    # gpt-4o-2024-11-20
    if model_name == "openai" and modality == "text":
        from kani.engines.openai import OpenAIEngine

        if prompt_type == "zeroshot-noreason":
            system_prompt = read_prompt("realtime_noreason_0shot_text_openai.md")
        else:  # zeroshot
            system_prompt = TEXT_SYSTEM_PROMPT

        # roughly same decoding params as 4o-audio
        engine = OpenAIEngine(model="gpt-4o-2024-11-20", temperature=0.8, max_context_size=120000)
        ai = OverhearingKani(engine=engine, system_prompt=system_prompt)
        return ExperimentConfig(ai=ai, modality="text")

    # gpt-4o-mini-realtime-preview-2024-12-17
    if model_name == "openai-mini" and modality == "audio":
        if prompt_type == "zeroshot-transcribe":
            system_prompt = read_prompt("realtime_tom_0shot_audio_transcribe_openai.md")
        elif prompt_type == "zeroshot-noreason":
            system_prompt = read_prompt("realtime_noreason_0shot_audio_openai.md")
        else:  # zeroshot
            system_prompt = AUDIO_SYSTEM_PROMPT

        ai = OverhearingKaniRealtime(model="gpt-4o-mini-realtime-preview-2024-12-17")
        await ai.connect(
            instructions=system_prompt,
            modalities=["text"],
            temperature=0.8,
        )
        return ExperimentConfig(ai=ai, modality="audio")

    # gpt-4o-mini-2024-07-18
    if model_name == "openai-mini" and modality == "text":
        from kani.engines.openai import OpenAIEngine

        if prompt_type == "zeroshot-noreason":
            system_prompt = read_prompt("realtime_noreason_0shot_text_openai.md")
        else:  # zeroshot
            system_prompt = TEXT_SYSTEM_PROMPT

        # roughly same decoding params as 4o-audio
        engine = OpenAIEngine(model="gpt-4o-mini-2024-07-18", temperature=0.8, max_context_size=120000)
        ai = OverhearingKani(engine=engine, system_prompt=system_prompt)
        return ExperimentConfig(ai=ai, modality="text")

    # ========= OPEN-WEIGHT MODELS COMMON PROMPTNG ==========
    from overhearing_agents.engines.react import (
        create_guidance_regex_for_react,
        create_guidance_regex_for_react_noreason,
        create_guidance_regex_for_react_with_transcribe,
    )

    if modality == "audio":
        if prompt_type == "fewshot-transcribe":
            system_prompt = AUDIO_TRANSCRIBE_SYSTEM_PROMPT
            fewshot_examples = FEWSHOT_REACT_TRANSCRIBE
            guidance_re = create_guidance_regex_for_react_with_transcribe
        elif prompt_type == "fewshot-noreason":
            system_prompt = AUDIO_NOREASON_SYSTEM_PROMPT
            fewshot_examples = FEWSHOT_REACT_NOREASON
            guidance_re = create_guidance_regex_for_react_noreason
        elif prompt_type == "fewshot":
            system_prompt = AUDIO_SYSTEM_PROMPT
            fewshot_examples = FEWSHOT_REACT
            guidance_re = create_guidance_regex_for_react
        else:  # zeroshot
            system_prompt = AUDIO_SYSTEM_PROMPT
            fewshot_examples = None
            guidance_re = create_guidance_regex_for_react
    else:  # text
        if prompt_type == "fewshot":
            system_prompt = TEXT_SYSTEM_PROMPT
            fewshot_examples = FEWSHOT_REACT
            guidance_re = create_guidance_regex_for_react
        elif prompt_type == "fewshot-noreason":
            system_prompt = TEXT_NOREASON_SYSTEM_PROMPT
            fewshot_examples = FEWSHOT_REACT_NOREASON
            guidance_re = create_guidance_regex_for_react_noreason
        else:  # zeroshot
            system_prompt = TEXT_SYSTEM_PROMPT
            fewshot_examples = None
            guidance_re = create_guidance_regex_for_react

    if not prompt_type.endswith("noreason"):
        max_consecutive_duplicates = 2
        system_prompt += "\nThink step by step before outputting the action to take in JSON format."
    else:
        max_consecutive_duplicates = 999999

    # ==== phi-4-multimodal-instruct (non-vLLM) ====
    # microsoft/Phi-4-multimodal-instruct
    if model_name == "phi-4":
        from overhearing_agents.engines.guided import GuidedHFEngine
        from overhearing_agents.engines.phi4 import Phi4MultimodalEngine
        from overhearing_agents.engines.react import SimpleReActEngine

        # 588 audio tokens = 31s ~= 19tps
        # => 15m context ~= 17,100 tokens + wiggle room
        # we'll just use the same context for both text and audio for simplicity and decoding speed
        # (vLLM doesn't support KV caching for multimodal models yet)
        max_ctx_size = 18000

        model = Phi4MultimodalEngine(
            temperature=1.0,
            top_p=0.9,
            do_sample=True,
            max_new_tokens=512,
            num_logits_to_keep=1,
            max_context_size=max_ctx_size,
            model_load_kwargs=dict(_attn_implementation="flash_attention_2"),
        )
        engine = GuidedHFEngine(
            SimpleReActEngine(
                model,
                react_add_observation_to_function_msgs=True,
                react_use_natural_language_tool_prompt=True,
                react_translate_function_msgs_to_user=True,
            ),
            guidance_re=guidance_re,
        )
        ai = ResetOnDuplicatesOverhearingKani(
            engine=engine,
            system_prompt=system_prompt,
            always_included_messages=fewshot_examples,
            max_consecutive_duplicates=max_consecutive_duplicates,
        )
        return ExperimentConfig(ai=ai, modality=modality)

    # ==== qwen-2.5-omni ====
    # Qwen/Qwen2.5-Omni-7B
    if model_name == "qwen-25":
        import torch

        from overhearing_agents.engines.guided import GuidedHFEngine
        from overhearing_agents.engines.qwen25 import QwenOmniEngine
        from overhearing_agents.engines.react import SimpleReActEngine

        # 1176 audio tokens = 31.3702s ~= 38tps
        # => 15m context ~= 34,200 tokens + wiggle room
        # though max ctx is 32k so there we go
        max_ctx_size = 32768

        model = QwenOmniEngine(
            temperature=1.0,
            top_p=0.9,
            do_sample=True,
            max_new_tokens=512,
            return_audio=False,
            max_context_size=max_ctx_size,
            model_load_kwargs=dict(
                attn_implementation="flash_attention_2", torch_dtype=torch.bfloat16, enable_audio_output=False
            ),
        )
        engine = GuidedHFEngine(
            SimpleReActEngine(
                model,
                react_add_observation_to_function_msgs=True,
                react_use_natural_language_tool_prompt=True,
                react_translate_function_msgs_to_user=True,
            ),
            guidance_re=guidance_re,
        )
        ai = ResetOnDuplicatesOverhearingKani(
            engine=engine,
            system_prompt=system_prompt,
            always_included_messages=fewshot_examples,
            max_consecutive_duplicates=max_consecutive_duplicates,
        )
        return ExperimentConfig(ai=ai, modality=modality)

    # ==== step-audio-chat ====
    if model_name == "step-audio-chat":
        import torch

        from overhearing_agents.engines.guided import GuidedHFEngine
        from overhearing_agents.engines.react import SimpleReActEngine
        from overhearing_agents.engines.step import StepAudioChatEngine

        model = StepAudioChatEngine(
            # todo don't hardcode this
            tokenizer_path="/nlpgpu/data/andrz/deps/Step-Audio/Step-Audio-Tokenizer",
            llm_path="/nlpgpu/data/andrz/deps/Step-Audio/Step-Audio-Chat",
            temperature=1,
            top_p=0.9,
            do_sample=True,
            max_new_tokens=512,
            model_load_kwargs=dict(torch_dtype=torch.bfloat16),
        )
        engine = GuidedHFEngine(
            SimpleReActEngine(model, react_add_observation_to_function_msgs=False),
            guidance_re=guidance_re,
        )
        ai = ResetOnDuplicatesOverhearingKani(
            engine=engine,
            system_prompt=system_prompt,
            always_included_messages=fewshot_examples,
            max_consecutive_duplicates=max_consecutive_duplicates,
        )
        return ExperimentConfig(ai=ai, modality=modality)

    # ==== ultravox-0.5-llama-3.3-70b ====
    # fixie-ai/ultravox-v0_5-llama-3_3-70b
    if model_name == "ultravox":
        import torch

        from overhearing_agents.engines.guided import GuidedHFEngine
        from overhearing_agents.engines.react import SimpleReActEngine
        from overhearing_agents.engines.ultravox import UltravoxLlama33Engine

        # 295 audio toks = 31.3702s
        # = 9.5 tps so 10 tps
        # => 15m context ~= 9,000 tokens + wiggle room
        max_ctx_size = 10000

        model = UltravoxLlama33Engine(
            model_id="zhuexe/ultravox-v0_5-llama-3_3-70b-tempfix",
            temperature=1.0,
            top_p=0.9,
            do_sample=True,
            max_context_size=max_ctx_size,
            model_load_kwargs=dict(torch_dtype=torch.bfloat16),
            tool_calls_exclusive_in_message=False,
        )
        engine = GuidedHFEngine(
            SimpleReActEngine(model, react_add_observation_to_function_msgs=False),
            guidance_re=guidance_re,
        )
        ai = ResetOnDuplicatesOverhearingKani(
            engine=engine,
            system_prompt=system_prompt,
            always_included_messages=fewshot_examples,
            max_consecutive_duplicates=max_consecutive_duplicates,
        )
        return ExperimentConfig(ai=ai, modality=modality)

    # ==== ultravox-0.5-llama-3.2-1b ====
    # fixie-ai/ultravox-v0_5-llama-3_2-1b
    if model_name == "ultravox-tiny":
        import torch

        from overhearing_agents.engines.guided import GuidedHFEngine
        from overhearing_agents.engines.react import SimpleReActEngine
        from overhearing_agents.engines.ultravox import UltravoxLlama33Engine

        # 295 audio toks = 31.3702s
        # = 9.5 tps so 10 tps
        # => 15m context ~= 9,000 tokens + wiggle room
        max_ctx_size = 10000

        model = UltravoxLlama33Engine(
            model_id="fixie-ai/ultravox-v0_5-llama-3_2-1b",
            temperature=1.0,
            top_p=0.9,
            do_sample=True,
            max_context_size=max_ctx_size,
            model_load_kwargs=dict(torch_dtype=torch.bfloat16, device_map="auto"),
            tool_calls_exclusive_in_message=False,
            wacky_device_map_fix=False,
        )
        engine = GuidedHFEngine(
            SimpleReActEngine(model, react_add_observation_to_function_msgs=False),
            guidance_re=guidance_re,
        )
        ai = ResetOnDuplicatesOverhearingKani(
            engine=engine,
            system_prompt=system_prompt,
            always_included_messages=fewshot_examples,
            max_consecutive_duplicates=max_consecutive_duplicates,
        )
        return ExperimentConfig(ai=ai, modality=modality)

    # ==== phi-4-multimodal-instruct (vLLM, doesn't work very well) ====
    # # AUDIO: microsoft/Phi-4-multimodal-instruct
    # if model_name == "phi-4":
    #     from overhearing_agents.engines.guided import GuidedOAIEngine
    #     from overhearing_agents.engines.openai_audio import OpenAIAudioEngine
    #     from overhearing_agents.engines.react import SimpleReActEngine
    #
    #     if modality == "audio":
    #         max_ctx_size = 15 * 60
    #     else:  # text
    #         max_ctx_size = 100000
    #
    #     model = OpenAIAudioEngine(
    #         model="microsoft/Phi-4-multimodal-instruct",
    #         temperature=0.8,
    #         tool_choice="none",  # since we do react prompting
    #         max_context_size=max_ctx_size,
    #         token_len_is_audio_duration=modality == "audio",
    #         **VLLM_OAI_KWARGS,
    #     )
    #     engine = GuidedOAIEngine(
    #         SimpleReActEngine(
    #             model,
    #             react_add_observation_to_function_msgs=True,
    #             react_use_natural_language_tool_prompt=True,
    #             react_translate_function_msgs_to_user=True,
    #         ),
    #         guidance_re=guidance_re,
    #     )
    #     ai = OverhearingKani(engine=engine, system_prompt=system_prompt, always_included_messages=fewshot_examples)
    #     return ExperimentConfig(ai=ai, modality=modality)

    raise ValueError(f"Unknown model implementation for {model_key!r}")
