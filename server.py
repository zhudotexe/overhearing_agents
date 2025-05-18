"""
Example server for the web interface.
"""

import logging

from experiments.models import OverhearingKaniRealtime
from experiments.prompts import read_prompt
from overhearing_agents.server import VizServer
from overhearing_agents.session import OverhearingAgentsSession

AGENT_INSTRUCTIONS = read_prompt("realtime_tom_0shot_audio.md")


async def create_session():
    ai = OverhearingKaniRealtime()
    await ai.connect(instructions=AGENT_INSTRUCTIONS, modalities=["text"])
    return OverhearingAgentsSession(ai)


# configure and start the server
server = VizServer(create_session)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    server.serve()
