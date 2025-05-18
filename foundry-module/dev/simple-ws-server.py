"""
A simple websocket server to mock the full AI system.
Randomly sends an event every 5-10 seconds.

Installation: pip install "fastapi[all]" uvicorn
Usage: python simple-ws-server.py
"""

import asyncio
import random
import traceback

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

# === these are the events that the server can send to foundry ===
# list all NPCs in the configured actor folder
# send a WS event back with {"type": "foundry_result",  "data": NPCs..., "action_id": same action ID}
LIST_ALL_NPCS = {"type": "foundry_action", "timestamp": 0, "action": {"type": "list_all_npcs", "id": "foo"}}
# list all NPCs that are on stage
LIST_STAGE_NPCS = {"type": "foundry_action", "timestamp": 0, "action": {"type": "list_stage_npcs", "id": "foo"}}
# show an NPC on the stage (do nothing if already on stage)
ADD_NPC_TO_STAGE = {
    "type": "foundry_action",
    "timestamp": 0,
    "action": {"type": "add_npc_to_stage", "id": "foo", "npc_name": "Ser Gordon"},
}
# remove an NPC from the stage (do nothing if not on stage)
REMOVE_NPC_FROM_STAGE = {
    "type": "foundry_action",
    "timestamp": 0,
    "action": {"type": "remove_npc_from_stage", "id": "foo", "npc_name": "Ser Gordon"},
}
# add the NPC to stage if not already on stage, and have them say this speech (TODO: with the given effect/emoji)
SEND_NPC_SPEECH = {
    "type": "foundry_action",
    "timestamp": 0,
    "action": {"type": "send_npc_speech", "id": "foo", "npc_name": "Ser Gordon", "text": "Hello I'm Ser Gordon"},
}
# you're going to receive a bunch of unrelated events over the WS so make sure you can handle them
DUMMY_RANDOM_EVENT = {"type": "dummy"}

ALL_EVENTS = [
    LIST_ALL_NPCS,
    LIST_STAGE_NPCS,
    ADD_NPC_TO_STAGE,
    REMOVE_NPC_FROM_STAGE,
    SEND_NPC_SPEECH,
    DUMMY_RANDOM_EVENT,
]

# === WS boilerplate ===
app = FastAPI()
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"]
)


async def _print_ws_data(ws: WebSocket):
    while True:
        try:
            data = await ws.receive_text()
            print(f"Got data from WS:")
            print(data)
        except WebSocketDisconnect:
            return
        except asyncio.CancelledError:
            raise
        except Exception:
            traceback.print_exc()


@app.websocket("/api/ws/random")
async def ws_random(websocket: WebSocket):
    await websocket.accept()
    printer_task = asyncio.create_task(_print_ws_data(websocket))
    while True:
        try:
            await asyncio.sleep(random.randint(5, 10))
            event = random.choice(ALL_EVENTS)
            await websocket.send_json(event)
        except (WebSocketDisconnect, RuntimeError):
            printer_task.cancel()
            return
        except Exception:
            traceback.print_exc()


@app.websocket("/api/ws/ordered")
async def ws_ordered(websocket: WebSocket):
    await websocket.accept()
    printer_task = asyncio.create_task(_print_ws_data(websocket))
    for event in [
        LIST_ALL_NPCS,
        LIST_STAGE_NPCS,
        ADD_NPC_TO_STAGE,
        SEND_NPC_SPEECH,
        DUMMY_RANDOM_EVENT,
        SEND_NPC_SPEECH,
        REMOVE_NPC_FROM_STAGE,
    ]:
        try:
            await asyncio.sleep(random.randint(5, 10))
            await websocket.send_json(event)
        except (WebSocketDisconnect, RuntimeError):
            printer_task.cancel()
            return
        except Exception:
            traceback.print_exc()
    printer_task.cancel()
    await websocket.close()


if __name__ == "__main__":
    uvicorn.run(app)
