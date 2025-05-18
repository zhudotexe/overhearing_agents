import asyncio
import logging

from easyaudiostream import list_mics

from overhearing_agents.kanis.base import BaseRealtimeKani
from overhearing_agents.session import OverhearingAgentsSession

ai = BaseRealtimeKani()


async def main(mic_id: int):
    app = OverhearingAgentsSession(ai)
    await ai.connect(voice="ballad")
    await app.chat_in_terminal_realtime(mic_id)


if __name__ == "__main__":
    # logging.basicConfig(level=logging.DEBUG)
    list_mics()
    mid = int(input("Mic ID: "))
    asyncio.run(main(mid))
