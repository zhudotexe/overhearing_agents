import asyncio
import logging

from kani.engines.openai import OpenAIEngine

from overhearing_agents.kanis.base import BaseKani
from overhearing_agents.session import OverhearingAgentsSession

engine = OpenAIEngine(model="gpt-4o-mini")
ai = BaseKani(engine)


async def main():
    app = OverhearingAgentsSession(ai)
    await app.chat_in_terminal()


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    asyncio.run(main())
