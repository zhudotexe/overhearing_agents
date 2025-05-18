#!/bin/bash
# Use Whisper to transcribe each dataset audio file.

# ensure the whisper model is on diskcache
cat ~/.cache/whisper/large-v3-turbo.pt > /dev/null
python transcribe.py
