import asyncio
import collections
import json
import logging
import shutil
import time
from functools import cached_property
from pathlib import Path

from experiments import models
from experiments.index import ExperimentRunIndex
from experiments.matcha import extract_gamedata_entities, extract_npc_entities
from experiments.utils import REPO_ROOT, audio_chunks_from_file, text_chunks_from_transcript_file
from overhearing_agents import events
from overhearing_agents.eventlogger import AudioLogger
from overhearing_agents.kanis.dnd.ai import (
    DNDSuggestEntity,
    DNDSuggestFoundry,
    FoundryAddNPCToStage,
    FoundryRemoveNPCFromStage,
)
from overhearing_agents.session import OverhearingAgentsSession
from overhearing_agents.state import Suggestion
from overhearing_agents.utils import print_event

LOG_DIR = Path(__file__).parent / "logs"


# ===== experiment entrypoints =====
class Experiment:
    """A run on a single input file for a given model."""

    def __init__(self, model_key: str, pcm_fp: Path, transcript_fp: Path):
        if model_key not in models.ALL_MODELS:
            raise ValueError(f"{model_key!r} is not a valid model (must be one of {models.ALL_MODELS})")

        self.model_key = model_key
        self.pcm_fp = pcm_fp
        self.transcript_fp = transcript_fp

        self.name = pcm_fp.stem
        self.log_dir = LOG_DIR / self.name / self.model_key
        self.run_key = f"{self.name}/{self.model_key}"  # for the run index
        self.run_index = ExperimentRunIndex(LOG_DIR / "index.json")

    # ==== data util ====
    @classmethod
    def from_audio_file(cls, model_key: str, audio_fp: str | Path):
        audio_fp = Path(audio_fp)
        pcm_fp = audio_fp.parent / "muxed" / f"{audio_fp.stem}.pcm"
        if not pcm_fp.exists():
            raise FileNotFoundError(f"Could not find {pcm_fp}, did you run mux.sh?")
        transcript_fp = audio_fp.parent / "transcriptions" / f"{audio_fp.stem}.json"
        if not transcript_fp.exists():
            raise FileNotFoundError(f"Could not find {transcript_fp}, did you run transcribe.sh?")
        return cls(model_key, pcm_fp, transcript_fp)

    # ==== utils ====
    def log_suggestion(
        self,
        f,
        start: float,
        end: float,
        suggestion: Suggestion,
        transcript: str = None,
        audio: bytes = None,
        audio_logger: AudioLogger = None,
    ):
        """
        Log that a suggestion was made at a given duration to the open file.

        If *transcript* is given, include the text span that caused this suggestion.
        If *audio* is given, include the path to the audio file that caused this suggestion. *audio_logger* must also be
        given.
        """
        # if isinstance(suggestion, DNDSuggestEntity):
        #     print("=" * (len(suggestion.entity_type) + len(suggestion.entity.qualified_name) + 6))
        #     print(f"| {suggestion.entity_type.upper()}: {suggestion.entity.qualified_name} |")
        #     print("=" * (len(suggestion.entity_type) + len(suggestion.entity.qualified_name) + 6))
        # else:
        #     print(suggestion.model_dump_json(exclude_unset=True))
        data = {"start": start, "end": end}
        if transcript:
            data["transcript"] = transcript
        if audio:
            fp = audio_logger.save_audio(
                audio,
                dir_path=self.log_dir / f"suggestion-clips",
                name_factory=lambda audio_hash: f"{int(end * 1000)}-{audio_hash[:8]}.mp3",
            )
            data["audio_fp"] = str(fp)
        data["suggestion"] = suggestion.model_dump(mode="json")
        f.write(json.dumps(data))
        f.write("\n")
        print(data)
        return data

    @cached_property
    def transcript_data(self):
        with self.transcript_fp.open() as f:
            return json.load(f)

    def get_transcript_at(self, start: float, end: float = None) -> str | None:
        """Return the text span(s) that includes the interval (start, end)."""
        if end is None:
            end = start
        assert end >= start
        spans = []
        for segment in self.transcript_data["segments"]:
            if segment["start"] >= end:
                break
            # if segment (start, end) has any overlap with (start, end) log it
            if (
                segment["start"] <= start <= segment["end"]
                or segment["start"] <= end <= segment["end"]
                or (start <= segment["start"] and segment["end"] <= end)
            ):
                spans.append(segment["text"].strip())
        if not spans:
            return None
        return "\n".join(spans)

    # def cleanup_empty_dirs(self):
    #     """Remove empty dirs owned by this run."""
    #     for root, dirs, files in os.walk(self.log_dir, topdown=False):
    #         if os.path.isdir(root) and not os.listdir(root):
    #             os.rmdir(root)

    # ==== main ====
    async def run(self, *, force_rerun=False):
        # lock the index and run the experiments
        with self.run_index:
            if force_rerun or not self.run_index.is_done_or_running(self.run_key):
                # if we're not being forced to rerun, check for a partial completion
                if force_rerun:
                    partial_completion = 0
                else:
                    # if an older run crashed partway through rename the dir and start with a partial seek
                    # (we do lose prior context but that's probably ok)
                    partial_completion = float(self.run_index.is_partially_complete(self.run_key))
                    if partial_completion and self.log_dir.exists():
                        shutil.move(
                            self.log_dir, LOG_DIR / self.name / f"{self.model_key}__until-{int(partial_completion)}"
                        )
                # back up any existing log dir and clear it
                if self.log_dir.exists():
                    shutil.make_archive(
                        f"{self.log_dir}.bak", "gztar", root_dir=LOG_DIR / self.name, base_dir=self.model_key
                    )
                    shutil.rmtree(self.log_dir)
                self.log_dir.mkdir(parents=True, exist_ok=True)
                # drop the metadata file in the parent dir if not exists
                if not (LOG_DIR / self.name / "meta.json").exists():
                    with open(LOG_DIR / self.name / "meta.json", "w") as f:
                        metadata = {
                            "name": self.name,
                            "pcm_fp": str(self.pcm_fp.absolute().relative_to(REPO_ROOT)),
                            "transcript_fp": str(self.transcript_fp.absolute().relative_to(REPO_ROOT)),
                        }
                        json.dump(metadata, f, indent=2)

                print("=" * 25)
                print(f"Running {self.model_key} on {self.name}...")
                print(f"Starting position: {partial_completion}")
                print(f"PCM: {self.pcm_fp}")
                print(f"Transcript: {self.transcript_fp}")
                print(f"Audio length: {self.pcm_fp.stat().st_size / 48000:.2f} sec")
                print("=" * 25)

                # get the kani impl and run it
                config = await models.config_for_key(self.model_key)
                with self.run_index.running(self.run_key, fp=self.log_dir / "suggestions.jsonl"):
                    if config.modality == "audio":
                        await self.run_audio(config.ai, seek_to=partial_completion, yield_every=config.yield_every)
                    if config.modality == "text":
                        await self.run_text(config.ai, seek_to=partial_completion, yield_every=config.yield_every)
                    if config.modality == "text-span":
                        await self.run_text_span_search(seek_to=partial_completion, yield_every=config.yield_every)
            else:
                print(f"{self.run_key} already is done, skipping")

    async def run_audio(self, ai, *, yield_every: float, seek_to: float = None):
        out_fp = self.log_dir / f"suggestions.jsonl"
        app = OverhearingAgentsSession(ai, log_dir=self.log_dir, max_function_rounds=4)
        with out_fp.open("w") as out_f:
            async with app.chat_session() as s:
                async for audio_chunk, start, end in audio_chunks_from_file(
                    self.pcm_fp, yield_every=yield_every, seek_to=seek_to
                ):
                    print(f"[{start} -> {end}]")
                    async for event in s.query_audio(audio_chunk, only_loggable=False):
                        print_event(event)
                        if isinstance(event, events.SuggestionEvent):
                            self.log_suggestion(
                                out_f,
                                start=start,
                                end=end,
                                suggestion=event.suggestion,
                                audio=audio_chunk,
                                audio_logger=app.logger._audio_logger,
                                transcript=self.get_transcript_at(start, end),
                            )
                    self.run_index.update_last_seen(self.run_key, end)
        return out_fp

    async def run_text(self, ai, *, yield_every: float, seek_to: float = None):
        out_fp = self.log_dir / "suggestions.jsonl"
        app = OverhearingAgentsSession(ai, log_dir=self.log_dir, max_function_rounds=4)
        with out_fp.open("w") as out_f:
            async with app.chat_session() as s:
                for text_chunk, start, end in text_chunks_from_transcript_file(
                    self.transcript_fp, yield_every=yield_every, seek_to=seek_to
                ):
                    print(f"[{start} -> {end}]")
                    print(text_chunk)
                    async for event in s.query(text_chunk, only_loggable=False):
                        print_event(event)
                        if isinstance(event, events.SuggestionEvent):
                            self.log_suggestion(
                                out_f,
                                start=start,
                                end=end,
                                suggestion=event.suggestion,
                                transcript=text_chunk,
                            )
                    self.run_index.update_last_seen(self.run_key, end)
        return out_fp

    async def run_text_span_search(self, *, yield_every: float, seek_to: float = None):
        # we want some simple tracking to prevent annotators from being overwhelmed
        # don't suggest the same thing twice in a row nor twice in the same span nor twice within 5 minutes
        last_suggestion = None
        suggestion_seen_at = collections.defaultdict(lambda: -9999.9)  # (type, name) -> duration
        suggestion_debounce = 300
        staged_npcs = set()

        # fp should be the path to the transcript json file
        out_fp = self.log_dir / "suggestions.jsonl"
        events_fp = self.log_dir / "events.jsonl"
        with out_fp.open("w") as out_f, events_fp.open("w") as events_f:
            events_f.write(json.dumps({"type": "start", "timestamp": time.time()}))
            events_f.write("\n")
            for text_chunk, start, end in text_chunks_from_transcript_file(
                self.transcript_fp, yield_every=yield_every, seek_to=seek_to
            ):
                print(f"[{start} -> {end}]")
                print(text_chunk)
                # gamedata entities
                entity_matches = await extract_gamedata_entities(text_chunk, case_sensitive=False, normalize=True)
                seen_this_span = set()
                suggestion_tuples = []
                for entity, re_match in entity_matches:
                    entity_type = type(entity).__name__
                    suggestion = DNDSuggestEntity(
                        entity_type=entity_type,
                        entity=entity,
                        url=entity.get_embed_url(),
                        glance_info=entity.get_glance_info(),
                    )
                    suggestion_tuples.append((entity_type, entity.name, suggestion))
                # npc matches
                npc_matches = await extract_npc_entities(text_chunk, case_sensitive=False, normalize=True)
                for npc_name, re_match in npc_matches:
                    if npc_name not in staged_npcs:
                        suggestion_type = "stage_npc"
                        suggestion = DNDSuggestFoundry(action=FoundryAddNPCToStage(npc_name=npc_name))
                        staged_npcs.add(npc_name)
                    else:
                        suggestion_type = "unstage_npc"
                        suggestion = DNDSuggestFoundry(action=FoundryRemoveNPCFromStage(npc_name=npc_name))
                        staged_npcs.remove(npc_name)
                    suggestion_tuples.append((suggestion_type, npc_name, suggestion))

                # suggest every entity found in transcript up to once per span
                for suggestion_type, suggestion_name, suggestion in suggestion_tuples:
                    # once per span
                    if (suggestion_type, suggestion_name) in seen_this_span:
                        continue
                    # not twice in a row
                    if last_suggestion == (suggestion_type, suggestion_name):
                        continue
                    # not within the last 5 minutes
                    if end - suggestion_seen_at[(suggestion_type, suggestion_name)] <= suggestion_debounce:
                        continue

                    # commit suggestion
                    seen_this_span.add((suggestion_type, suggestion_name))
                    last_suggestion = (suggestion_type, suggestion_name)
                    suggestion_seen_at[(suggestion_type, suggestion_name)] = end
                    logged_suggestion = self.log_suggestion(
                        out_f, start=start, end=end, suggestion=suggestion, transcript=text_chunk
                    )
                    events_f.write(
                        json.dumps({"type": "suggestion", "timestamp": time.time(), "suggestion": logged_suggestion})
                    )
                    events_f.write("\n")
                self.run_index.update_last_seen(self.run_key, end)
            events_f.write(json.dumps({"type": "end", "timestamp": time.time()}))
            events_f.write("\n")
        return out_fp


async def starless():
    for audio_fp in (REPO_ROOT / f"data/starless").glob("*.m4a"):
        for model_key in models.ALL_MODELS:
            e = Experiment.from_audio_file(model_key, audio_fp)
            await e.run()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # run on one model/file
    e = Experiment.from_audio_file(models.TEXT_SPAN_KEY, REPO_ROOT / f"data/starless/StarlessTest.m4a")
    asyncio.run(e.run(force_rerun=True))
