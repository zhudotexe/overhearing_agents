import collections
import functools
import io
import json
import logging
import wave
from pathlib import Path
from typing import Iterable

import yaml
from rapidfuzz import fuzz
from rapidfuzz.utils import default_process

from evaluation.models import Classification, ExperimentInfo, LabelledSuggestion, SuggestionLog
from experiments.utils import REPO_ROOT
from overhearing_agents.utils import read_jsonl

CONFIG_PATH = Path(__file__).parent / "config"
EXPERIMENT_LOG_PATH = Path(__file__).parents[1] / "experiments/logs"
ANNOTATIONS_PATH = Path(__file__).parent / "annotations"

log = logging.getLogger(__name__)


# ==== data loading ====
def get_annotator_assignments() -> dict[str, list[str]]:
    """Return a mapping of annotator IDs to experiment IDs."""
    with open(CONFIG_PATH / "annotator-assignments.yaml") as f:
        return yaml.safe_load(f)


def get_experiment_infos() -> list[ExperimentInfo]:
    """Return a list of all experiment infos."""
    with open(CONFIG_PATH / "experiments.yaml") as f:
        data = yaml.safe_load(f)
    return [ExperimentInfo.model_validate(d) for d in data]


def get_classifications() -> list[Classification]:
    """Read the list of classifications that can be applied to a suggestion."""
    with open(CONFIG_PATH / "classifications.yaml") as f:
        data = yaml.safe_load(f)
    return [Classification.model_validate(c) for c in data]


def get_experiment_by_id(experiment_id: str) -> ExperimentInfo:
    all_experiments = get_experiment_infos()
    try:
        experiment_info = next(e for e in all_experiments if e.id == experiment_id)
    except StopIteration:
        raise KeyError(experiment_id) from None
    return experiment_info


@functools.cache
def get_all_suggestions(experiment_id: str) -> list[SuggestionLog]:
    """Get all suggestions proposed by every model for a given experiment ID."""
    seen_suggestions = []
    experiment = get_experiment_by_id(experiment_id)

    for subdir in (REPO_ROOT / Path(experiment.log_dir)).iterdir():
        if not subdir.is_dir():
            continue
        jsonl_fp = subdir / "suggestions.jsonl"
        if not jsonl_fp.exists():
            log.warning(f"Could not find suggestions file: {jsonl_fp}")

        # parse the jsonl
        for suggestion_data in read_jsonl(jsonl_fp):
            suggestion_data["model_key"] = subdir.name.split("__")[0]
            suggestion_data["experiment_info"] = experiment
            seen_suggestions.append(SuggestionLog.model_validate(suggestion_data))

    return sorted(seen_suggestions, key=lambda s: s.end)


def get_annotations(experiment_id: str) -> Iterable[LabelledSuggestion]:
    fp = ANNOTATIONS_PATH / f"{experiment_id}.jsonl"
    if fp.exists():
        for data in read_jsonl(fp):
            # if "test" in data["who"]:
            #     continue
            yield LabelledSuggestion.model_validate(data)


def get_user_annotations(experiment_id: str, username: str) -> list[LabelledSuggestion]:
    """Get all of the annotations that the user has submitted for this experiment."""
    out = []
    for annotation in get_annotations(experiment_id):
        if annotation.who == username:
            out.append(annotation)
    return out


def get_transcript_for_span(transcript_fp: Path, start: float, end: float) -> str:
    """Return the text span(s) that includes the interval (start, end)."""
    assert end >= start
    with open(transcript_fp) as f:
        transcript_data = json.load(f)
    spans = []
    for segment in transcript_data["segments"]:
        if segment["start"] >= end:
            break
        # if segment (start, end) has any overlap with (start, end) log it
        if (
            segment["start"] <= start <= segment["end"]
            or segment["start"] <= end <= segment["end"]
            or (start <= segment["start"] and segment["end"] <= end)
        ):
            spans.append(segment["text"].strip())
    return "\n".join(spans)


def get_audio_for_span(pcm_fp: Path, start: float, end: float) -> io.BytesIO:
    """Return WAV audio for the given span."""
    assert end >= start
    # read the span of PCM data
    start_byte = int(start * 48000)
    start_byte -= start_byte % 2
    duration = end - start
    duration_bytes = int(duration * 48000)
    duration_bytes -= duration_bytes % 2
    with open(pcm_fp, "rb") as f:
        f.seek(start_byte)
        data_bytes = f.read(duration_bytes)

    # pack it to WAV
    out_bytes = io.BytesIO()
    with wave.open(out_bytes, "wb") as wave_data:
        wave_data.setnchannels(1)
        wave_data.setsampwidth(2)
        wave_data.setframerate(24000)
        wave_data.setnframes(len(data_bytes) // 2)
        wave_data.writeframesraw(data_bytes)

    out_bytes.seek(0)
    return out_bytes


def save_annotation(experiment_id: str, annotation: LabelledSuggestion):
    with open(ANNOTATIONS_PATH / f"{experiment_id}.jsonl", "a") as f:
        f.write(annotation.model_dump_json())
        f.write("\n")


# ==== utils ====
def count_suggestions_by_model_and_type(experiment_id):
    """Get a mapping model_key -> suggestion type -> count of all suggestions in the experiment."""
    counts = collections.defaultdict(collections.Counter)
    for suggestion in get_all_suggestions(experiment_id):
        counts[suggestion.model_key][suggestion.suggestion["suggest_type"]] += 1
    return counts


def suggestions_are_same(
    earlier: SuggestionLog,
    later: SuggestionLog,
    *,
    tolerance=30,
    match_npc_name_only=False,
    strict_match_improvised_npc=False,
    npc_speech_similarity_ratio=fuzz.ratio,
    npc_speech_similarity_threshold=80,
):
    """
    Whether two suggestions are the same.

    Suggestions are the same when they take the same action (see below), and the later suggestion
    occurs less than *tolerance* seconds after the earlier (default 30).

    If *match_npc_name_only* is True, all Foundry events will match only on the NPC name.

    * Gamedata: suggests the same entity
    * Foundry (add_npc_to_stage, remove_npc_from_stage): the same action with the same NPC
    * Foundry (send_npc_speech): the same NPC, text match >70%
    * Improvised NPC: all of them match, unless *strict_match_improvised_npc* is True
    """
    if later.end < earlier.start:
        return False
    if not (abs(later.end - earlier.end) <= tolerance):
        return False
    if earlier.suggestion["suggest_type"] != later.suggestion["suggest_type"]:
        return False
    suggest_type = earlier.suggestion["suggest_type"]

    if suggest_type == "gamedata":
        # * Gamedata: suggests the same entity
        return earlier.suggestion["entity"] == later.suggestion["entity"]
    elif suggest_type == "improvised_npc":
        # * Improvised NPC: all of them match, unless *strict_match_improvised_npc* is True
        if strict_match_improvised_npc:
            return all(earlier.suggestion[f] == later.suggestion[f] for f in ("race", "background", "culture"))
        return True
    elif suggest_type == "foundry":
        # If *match_npc_name_only* is True, all Foundry events will match only on the NPC name.
        if match_npc_name_only:
            return earlier.suggestion["action"]["npc_name"] == later.suggestion["action"]["npc_name"]

        # make sure they have the same action
        if earlier.suggestion["action"]["type"] != later.suggestion["action"]["type"]:
            return False
        foundry_action_type = earlier.suggestion["action"]["type"]
        # * Foundry (send_npc_speech): the same NPC, text match >80%
        if foundry_action_type == "send_npc_speech":
            return (earlier.suggestion["action"]["npc_name"] == later.suggestion["action"]["npc_name"]) and (
                npc_speech_similarity_ratio(
                    earlier.suggestion["action"]["text"],
                    later.suggestion["action"]["text"],
                    processor=default_process,
                )
                > npc_speech_similarity_threshold
            )
        # * Foundry (add_npc_to_stage, remove_npc_from_stage): the same action with the same NPC
        else:
            # action type is matched earlier
            return earlier.suggestion["action"]["npc_name"] == later.suggestion["action"]["npc_name"]

    log.warning(f"Unhandled suggestion type in suggestions_are_same: {suggest_type}")
    return False
