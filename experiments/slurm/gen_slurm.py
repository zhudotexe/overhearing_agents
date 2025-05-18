import sys
from pathlib import Path

# make sure we can import from models
sys.path.append(str(Path(__file__).parents[1].absolute()))

from models import MODEL_COMPAT_MATRIX

REPO_ROOT = Path(__file__).parents[2]
OUT_PATH = Path(__file__).parent
ALL_M4A = (REPO_ROOT / "data").glob("starless/*.m4a")

DO_FIRST = [
    # "Starless Lands S17",
    # "Starless Lands S18P1",
    # "Starless Lands S18P2",
    # "Starless Lands S19",
    "Starless Lands S20",
    # "Starless Lands S21",
    # "Starless Lands S22",
    # "Starless Lands S23",
]
ALL_M4A = sorted(ALL_M4A, key=lambda p: (p.stem in DO_FIRST, p), reverse=True)

GPUS_1 = "\n#SBATCH --gpus-per-task=1\n#SBATCH --constraint=48GBgpu"
GPUS_4 = "\n#SBATCH --gpus-per-task=4\n#SBATCH --constraint=48GBgpu"
GPUS_8 = "\n#SBATCH --gpus-per-task=8\n#SBATCH --constraint=48GBgpu"

MODEL_RESOURCES = {
    # --- gpt-4o ---
    "openai": {"ntasks": 2, "cpus": 4, "mem": "4G", "gpus": "", "venv": "venv"},
    # --- gpt-4o-mini ---
    "openai-mini": {"ntasks": 2, "cpus": 4, "mem": "4G", "gpus": "", "venv": "venv"},
    # --- phi-4-multimodal-instruct ---
    "phi-4": {"ntasks": 8, "cpus": 4, "mem": "16G", "gpus": GPUS_1, "venv": "venv"},
    # --- qwen-2.5-omni ---
    "qwen-25": {"ntasks": 8, "cpus": 4, "mem": "16G", "gpus": GPUS_1, "venv": "venv-qwen"},
    # --- ultravox-0.5-llama-3.3-70b ---
    "ultravox": {"ntasks": 2, "cpus": 16, "mem": "16G", "gpus": GPUS_4, "venv": "venv"},
    # --- ultravox-0.5-llama-3.2-1b ---
    "ultravox-tiny": {"ntasks": 8, "cpus": 4, "mem": "16G", "gpus": GPUS_1, "venv": "venv"},
    # --- step-audio-chat ---
    "step-audio-chat": {"ntasks": 1, "cpus": 16, "mem": "24G", "gpus": GPUS_8, "venv": "venv10"},
    # --- text only ---
    "text": {"ntasks": 8, "cpus": 2, "mem": "8G", "gpus": "", "venv": "venv"},
}

HEADER = """\
#!/bin/bash
#
#SBATCH --partition=p_nlp
#SBATCH --job-name=pa_{model_key}
#
#SBATCH --output=/nlpgpu/data/andrz/logs/%j.%x.log
#SBATCH --error=/nlpgpu/data/andrz/logs/%j.%x.log
#SBATCH --time=14-0
#SBATCH --ntasks={ntasks}
#SBATCH --cpus-per-task={cpus}
#SBATCH --mem-per-cpu={mem}{gpus}
#SBATCH --mail-user=andrz@seas.upenn.edu
#SBATCH --mail-type=END,FAIL

source experiments/slurm/_slurm_env.sh
source {venv}/bin/activate
"""

for model, exptypes in MODEL_COMPAT_MATRIX:
    idx = 0
    with open(OUT_PATH / f"{model}-all.sh", "w") as f:
        f.write(HEADER.format(**MODEL_RESOURCES[model], model_key=model))
        for data_fp in ALL_M4A:
            for exptype in exptypes:
                f.write(
                    "srun -n1 -N1 --exclusive python experiments/main.py --model-key"
                    f' {model}.{exptype} "{data_fp.relative_to(REPO_ROOT)}" &>'
                    f'"/nlpgpu/data/andrz/logs/pa-{model}.{exptype}.{data_fp.stem}.log" &\n'
                )
                idx += 1
        f.write("wait\n")

# just the ones to do first (with human annotations)
for model, exptypes in MODEL_COMPAT_MATRIX:
    idx = 0
    with open(OUT_PATH / f"{model}-first.sh", "w") as f:
        f.write(HEADER.format(**MODEL_RESOURCES[model], model_key=model))
        for data_fp in ALL_M4A:
            if data_fp.stem not in DO_FIRST:
                continue
            for exptype in exptypes:
                f.write(
                    "srun -n1 -N1 --exclusive python experiments/main.py --model-key"
                    f' {model}.{exptype} "{data_fp.relative_to(REPO_ROOT)}" &>'
                    f"/nlpgpu/data/andrz/logs/pa-{model}.{exptype}.{idx}.log &\n"
                )
                idx += 1
        f.write("wait\n")
