import asyncio

from experiments.models import OverhearingKaniRealtime
from experiments.prompts import read_prompt
from overhearing_agents.session import OverhearingAgentsSession

AGENT_INSTRUCTIONS = read_prompt("realtime_tom_0shot_audio.md")

# engine = OpenAIAudioEngine(model="gpt-4o-audio-preview", modalities=["text"])
# ai = OverhearingKani(engine, system_prompt=AGENT_INSTRUCTIONS)
ai = OverhearingKaniRealtime()  # the realtime API is like 80% cheaper


async def main():
    app = OverhearingAgentsSession(ai)
    await ai.connect(instructions=AGENT_INSTRUCTIONS, modalities=["text"])
    await app.chat_in_terminal()


if __name__ == "__main__":
    # logging.basicConfig(level=logging.DEBUG)
    asyncio.run(main())
