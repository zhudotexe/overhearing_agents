# Overhearing Agents

Much work has been done on conversational LLM agents which directly assist human users with tasks. We present an
alternative paradigm of interacting with LLM agents, which we call overhearing agents. Overhearing agents do not
actively participate in conversation--instead, they "listen in" to human-human conversations and perform background
actions or provide suggestions to assist the user. In this work, we explore the overhearing agents paradigm through the
lens of Dungeons & Dragons gameplay. We present an in-depth study using large multimodal audio-language models as
overhearing agents to assist a Dungeon Master. We perform a human evaluation to examine the helpfulness of such agents
and find that some large audio-language models have the emergent ability to use implicit audio cues to perform the
overhearing task.

## Setup

Requires Python 3.10 or higher (I used 3.12 but I'm pretty sure it should work).

```shell
$ pip install -r requirements.txt
```

You will also need to export an OpenAI API key:

```shell
$ export OPENAI_API_KEY="sk-proj-your-key-here..."
```

### Running Open-Weight Models

Since various open-weight models require extra heavyweight dependencies, their requirements are listed separately.

Use one of the following requirements files instead:

```shell
# Phi-4-multimodal, ultravox-0.5
$ pip install -r requirements-hf.txt
# Qwen-2.5-omni
$ pip install -r requirements-qwen.txt
# Step-Audio
# NOTE: Requires Python 3.10 exactly!
$ pip install -r requirements-step.txt
```

Additionally, some HF models might require/recommend Flash Attention, which must be installed with a GPU attached:

```shell
$ pip install flash-attn --no-build-isolation
```

## Running

**Full Webserver**

1. First, you must build the web UI. Run:

```shell
$ cd viz
$ npm i
$ npm run build
```

Alternatively, you can run `npm run dev` to automatically rebuild the web UI when you make any changes.

2. Then, run (from the repo root):

```shell
$ python server.py
```

The web UI will be at http://127.0.0.1:8000. (Or a different port if you're using dev)

**Test on File**

To run the system on a given input file, first run the steps below in *Batch Process/Preprocessing*.

Then run:

```shell
$ python sandbox/fromfile_demo.py
```

This will load a random input file, seek to a random position in it, and run the system as if it had received that
data over the mic.

**Chat in Terminal**

A good way to test function implementations without having to use audio. Run:

```shell
$ python sandbox/terminal_chat.py
```

## Adding New Tasks

Overhearing agents are implemented
using [Kani's function calling capability](https://kani.readthedocs.io/en/latest/function_calling.html). In order to add
new tasks to the overhearing agent, all you need to do is define a class that extends `BaseKani`
(`from overhearing_agents.kanis.base import BaseKani`). In this class, define one or more `@ai_function`s -- these are
the tasks that your agent will be able to do. These functions can have any implementation!

To launch the overhearing agents server, see the example below! This example defines a function to return a new agent
instance for each session, then passes that factory function to the server.

```python
from overhearing_agents.kanis.base import BaseKani
from overhearing_agents.server import VizServer
from overhearing_agents.session import OverhearingAgentsSession


class MyAgentClass(BaseKani):


# ...

async def create_session():
    ai = MyAgentClass()
    return OverhearingAgentsSession(ai)


server = VizServer(create_session)
server.serve()
```

Example agents (e.g. the D&D agent used in the Overhearing Agents paper) can be found in `overhearing_agents/kanis`.

## Batch Process

### Preprocessing

Preprocessing the data will take a lot of storage space (>250GB)!

1. Data goes in `/data/<src>/*.[m4a|mp3|...]`
    1. To download the Critical Role datasets, run `download-cr.sh` and `download-cr2.sh`
2. Run `/data/mux.sh` and `/data/transcribe.sh`
    1. This will create `muxed` and `transcribed` dirs in each datasrc dir
    2. Muxed PCM files are signed 16bit PCM mono @ 24kHz
    3. Transcript files are JSON

### Running Experiments

1. Make sure the requisite engine is configured in `experiments/models.py`
2. Run `python experiments/main.py`:

```
usage: main.py [-h] --model-key ... [--force-rerun] audio_file [audio_file ...]

positional arguments:
  audio_file

options:
  -h, --help            show this help message and exit
  --model-key ...       use a model key in experiments/models.py
  --force-rerun         force a model to rerun even if its logs exist in the index
```

Each experiment run will record its state in `experiments/logs/index.json`.

Each experiment's logs will be saved to `experiments/logs/<filename>/<system-key>`.

> [!NOTE]
> If an experiment crashes partway through, it will record how much it was successfully able to process in the index.
> Later runs of the same experiment will start from the point where the previous run crashed.
> The log directory for the previous crashed run will be renamed
> to `experiments/logs/<filename>/<system-key>__until-<crashed-duration>`.

> [!WARNING]
> To force an experiment to rerun, either run with `--force-rerun` or delete the corresponding entry
> in `experiments/logs/index.json`.
> This will overwrite any existing log directory for that experiment!

#### Models used

**Text**

- gpt-4o-2024-11-20
- gpt-4o-mini-2024-07-18
- microsoft/Phi-4-multimodal-instruct (5.6B)
- Qwen/Qwen2.5-Omni-7B (7B)
- meta-llama/Llama-3.3-70B-Instruct (70B)

**Audio**

- gpt-4o-realtime-preview-2024-12-17
- gpt-4o-mini-realtime-preview-2024-12-17
- microsoft/Phi-4-multimodal-instruct (5.6B, audio embeddings)
- Qwen/Qwen2.5-Omni-7B (7B, audio embeddings)
- fixie-ai/ultravox-v0_5-llama-3_3-70b (70B, audio embeddings based off whisper encoder)

### Evaluating Outputs

See `evaluation/README.md`.

## Foundry Module

### Setup

1. Install Theatre Inserts (Foundry main menu -> Add-on Modules -> Install Module -> search "Theatre Inserts" as package
   name)

2. Install the (foundry-module/dev) pa folder to .../FoundryVTT/Data/Modules (right click foundry on taskbar -> Browse
   User Data for quick access) (TODO(Evan): add support for manifest or package search)

3. Within a foundry game session, enable the modules (Passive Agents, Theatre Inserts, and dependencies libWrapper and
   socketlib) from Game Settings -> Manage Modules. Follow the foundry prompts to relaunch.

### Functionality

The PA module connects to the web socket specified at \scripts\main.js and executes the received foundry requests,
supporting the following types:

**list_all_npcs**

Returns an array containing the npcs (foundry actors by name) within the foundry actor folder "npcs"

**list_stage_npcs**

Returns an array containing all staged npcs (that is, all npcs currently displayed on screen with pop-ups, not to be
confused with the npcs in
the [TI](https://github.com/League-of-Foundry-Developers/fvtt-module-theatre/blob/master/wiki/instructions/home/introduction_to_theater.md)
NavBar that's just above the text chatting window, which is also refered to as a stage by TI docs)

**add_npc_to_stage**

Stages the passed npc (also adds it to the NavBar)

**remove_npc_from_stage**

Unstages the passed npc (does not remove it from the NavBar)

**send_npc_speech**

Stages the passed npc who says the passed dialogue (also adds npc to NavBar)

## Development Tips

### Code Style

For _Python_, use [PEP-8](https://peps.python.org/pep-0008/) compliant code styling with a width of 120
characters. I recommend using [Black](https://black.readthedocs.io/en/stable/)
and [isort](https://pycqa.github.io/isort/) to automatically format your code after major changes. The projectfile
(`pyproject.toml`) will automatically configure these tools.

```shell
$ black .
$ isort .
```

For _JavaScript_ and _TypeScript_, use [Prettier](https://prettier.io/) to format your code with the code format found
in `viz/.prettierrc.json`.

### Repository Layout

- `data`: Directory containing the raw input data for experiments. Mostly gitignored aside from the scripts.
    - `data/<datasrc>`: For each data source, contains the m4a files, as well as their muxed and transcribed versions.
- `evaluation`: Python module containing everything related to evaluating the logs generated by experiments.
- `experiments`: Python module containing model definitions and prompts for offline experiments.
    - `experiments/logs`: For each input data file, contains logs for each model/prompt system run on it.
- `foundry-module`: Directory containing the source code of the Foundry module for integrating PA with Foundry VTT.
- `logs` (gitignored): Default directory containing the logs of the interactive server.
- `overhearing_agents`: The main Python module for the project. Contains all the business logic. Should *not* have any
  dependencies to the `experiments` or `evaluation` modules.
- `sandbox`: A Python module containing throwaway/one-off scripts. Should not be depended upon by anything.
- `viz`: Contains the full frontend project (a Vue 3 + TS frontend).

## Acknowledgements

Much of the logging and visualization code is based off of ReDel (Zhu et al., 2024)'s codebase, under the MIT license.

Additional acknowledgements will be added here after the anonymity period. 
