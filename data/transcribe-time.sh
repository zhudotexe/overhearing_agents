#!/bin/bash
#
#SBATCH --partition=p_nlp
#SBATCH --job-name=transcribe
#
#SBATCH --output=/nlpgpu/data/andrz/logs/%j.%x.log
#SBATCH --error=/nlpgpu/data/andrz/logs/%j.%x.log
#SBATCH --time=3-0
#SBATCH --nodes=1
#SBATCH -c 4
#SBATCH --mem=32G
#SBATCH --gpus=1
#SBATCH --constraint=48GBgpu
#SBATCH --mail-user=andrz@seas.upenn.edu
#SBATCH --mail-type=END,FAIL

# ensure the whisper model is on diskcache
cat ~/.cache/whisper/large-v3-turbo.pt > /dev/null
python transcribe.py --time
