import sys
from pathlib import Path

# hacky fix to make funasr_detach a top-level import
sys.path.append(str(Path(__file__).parent))

from .engine import StepAudioChatEngine
