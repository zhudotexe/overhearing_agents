"""
Main experiment entrypoint.

Usage:
python experiments/main.py --model-key openai-audio-mini data/starless/StarlessTest.m4a
"""

import argparse
import asyncio
import logging
import pathlib

from experiments import models
from experiments.experiment import Experiment

parser = argparse.ArgumentParser()
parser.add_argument("--model-key", required=True, choices=[*models.ALL_MODELS, "all"])
parser.add_argument("--force-rerun", action="store_true")
parser.add_argument("--debug-loggers", action="append", default=[])
parser.add_argument("audio_file", type=pathlib.Path, nargs="+")


async def main():
    args = parser.parse_args()

    # enable debug level for the loggers passed by --debug-loggers
    for logger_name in args.debug_loggers:
        logging.getLogger(logger_name).setLevel(logging.DEBUG)

    for audio_fp in args.audio_file:
        if args.model_key == "all":
            for model_key in models.ALL_MODELS:
                e = Experiment.from_audio_file(model_key, audio_fp=audio_fp)
                await e.run(force_rerun=args.force_rerun)
        else:
            e = Experiment.from_audio_file(args.model_key, audio_fp=audio_fp)
            await e.run(force_rerun=args.force_rerun)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
