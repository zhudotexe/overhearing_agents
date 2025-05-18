import json
import random
from pathlib import Path
from typing import AsyncIterable, Iterable

from pydub import AudioSegment

DATA_DIR = Path(__file__).parents[1] / "data"
REPO_ROOT = Path(__file__).parents[1]


# ==== audio ====
def load_audio(fp: Path) -> bytes:
    """Load the test audio, resample to 24kHz PCM"""
    if fp.suffix == ".pcm":
        return load_raw_audio(fp)
    audio = AudioSegment.from_file(fp)
    return audio.set_frame_rate(24000).set_channels(1).set_sample_width(2).raw_data


def load_raw_audio(fp: Path) -> bytes:
    """Load the test audio, which should already be 24kHz PCM"""
    return fp.read_bytes()


async def audio_chunks_from_file(
    fp: Path, *, yield_every: float = 5, random_seek=False, seek_to: float = None
) -> AsyncIterable[tuple[bytes, float, float]]:
    """
    Get an audio stream from the specified audio file that yields chunks of PCM16 that are N seconds long.

    If random_seek is True, randomly seek to a point in the file (up to 90% through) before yielding.
    Elif seek_to is a positive number, seek to that many seconds through the file.
    """
    audio = load_audio(fp)
    audio_len = len(audio)
    if random_seek:
        start = random.randrange(0, audio_len - (audio_len // 10), 2)
    elif seek_to:
        start = int(48000 * seek_to)
        start -= start % 2  # make sure we are frame-aligned
    else:
        start = 0
    # 16b, 24kHz = 48kB/sec
    bytes_per_sec = 48000
    chunk_size = int(bytes_per_sec * yield_every)
    for sec in range(start, audio_len, chunk_size):
        start_time = sec / bytes_per_sec
        end_time = (sec + chunk_size) / bytes_per_sec
        yield audio[sec : sec + chunk_size], start_time, end_time


# ==== text ====
def text_chunks_from_transcript_file(
    fp: Path, *, yield_every: float = 5, random_seek=False, seek_to: float = None
) -> Iterable[tuple[str, float, float]]:
    """
    Get a text stream from the specified transcript file that yields chunks of text that are N seconds long.

    Yields (text, start, end) tuples.

    If random_seek is True, randomly seek to a point in the file (up to 90% through) before yielding.
    Elif seek_to is a positive number, seek to that many seconds through the file.
    """
    with fp.open() as f:
        data = json.load(f)
    segments = data["segments"]
    segment_len = max(seg["end"] for seg in segments)

    # find the starting segment idx
    if random_seek:
        start = random.randrange(0, segment_len - (segment_len // 10), 2)
    elif seek_to:
        start = seek_to
    else:
        start = 0
    if start > segment_len:
        raise ValueError("Provided starting value is past total duration.")
    start_idx = 0
    while start > segments[start_idx]["end"]:
        start_idx += 1

    # buffer until the saved duration is longer than yield_every, then yield
    buffer = []
    buffer_start = segments[start_idx]["start"]
    buffer_span_len = 0
    last_end = segments[start_idx]["start"]
    last_text = None
    for idx in range(start_idx, len(segments)):
        segment = segments[idx]
        duration = segment["end"] - segment["start"]
        text = segment["text"].strip()
        buffer_span_len += duration
        # if the buffer text is identical to the last text, and it starts right after the last segment, discard it
        # it is probably a Whisper hallucination
        if text == last_text and segment["start"] == last_end:
            last_end = segment["end"]
            continue
        # otherwise add the segment to the buffer
        last_text = text
        buffer.append(text)

        # add any silence time between the end of the last segment and the start of this segment to the buffer
        buffer_span_len += segment["start"] - last_end
        last_end = segment["end"]

        # yield the buffer if it's long enough
        if buffer_span_len >= yield_every:
            yield "\n".join(buffer), buffer_start, last_end
            buffer.clear()
            buffer_span_len = 0
            buffer_start = last_end

    # flush the buffer at the end
    if buffer:
        yield "\n".join(buffer), buffer_start, last_end
