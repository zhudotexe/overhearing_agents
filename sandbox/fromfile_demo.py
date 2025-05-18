import asyncio
import logging
import random
import time
from pathlib import Path

import easyaudiostream

from experiments.models import OverhearingKaniRealtime
from experiments.prompts import read_prompt
from experiments.utils import audio_chunks_from_file
from overhearing_agents.session import OverhearingAgentsSession
from overhearing_agents.utils import print_event

AGENT_INSTRUCTIONS = read_prompt("realtime_tom_0shot_audio.md")


async def main(fp):
    ai = OverhearingKaniRealtime()
    app = OverhearingAgentsSession(ai)
    await ai.connect(instructions=AGENT_INSTRUCTIONS, modalities=["text"])
    async with app.chat_session() as s:
        async for chunk, start, end in audio_chunks_from_file(fp, yield_every=5):
            print(f"[{start} -> {end}]")
            async for event in s.query_audio(chunk, only_loggable=False):
                print_event(event)


def listen_along_with_server(fp, *, random_seek=False, seek_to=None):
    from overhearing_agents.server import VizServer

    active_tasks = set()

    async def create_session():
        ai = OverhearingKaniRealtime(realtime_reconnect_reupload_secs=180)
        await ai.connect(instructions=AGENT_INSTRUCTIONS, modalities=["text"])
        app = OverhearingAgentsSession(ai)

        async def _sender_task(app):
            # create a task for sending events to the server
            yield_every = 0.5
            send_audio_every = 5

            # hack: play 1s of silence to init the playback, and wait
            easyaudiostream.play_raw_audio(b"\0\0" * 48000)
            await asyncio.sleep(3)

            async def chunk_stream():
                async for chunk, start, end in audio_chunks_from_file(
                    fp, yield_every=yield_every, random_seek=random_seek, seek_to=seek_to
                ):
                    last_yield = time.perf_counter()
                    easyaudiostream.play_raw_audio(chunk)
                    yield chunk
                    await asyncio.sleep(max(last_yield + yield_every - time.perf_counter() - 0.005, 0))

            async for event in app.stream_audio(chunk_stream(), only_loggable=False, send_audio_every=send_audio_every):
                print_event(event)

        task = asyncio.create_task(_sender_task(app))
        active_tasks.add(task)
        task.add_done_callback(active_tasks.discard)
        return app

    # configure and start the server
    server = VizServer(create_session)
    server.serve()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    starless_file = random.choice(list((Path(__file__).parents[1] / "data/starless/muxed").glob("*.pcm")))
    # starless_file = Path(__file__).parents[1] / "data/starless/muxed/Starless Lands S17.pcm"
    print("Input file:", starless_file)
    listen_along_with_server(starless_file, random_seek=True)
    # asyncio.run(main(starless_file))
