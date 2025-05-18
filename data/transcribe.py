"""
Usage: python transcribe.py [--time]
Dependencies: openai-whisper

For each subdirectory of data, transcribes *.m4a into subdir/transcriptions/*.json.
"""

import json
import subprocess
import sys
import time
from pathlib import Path

IS_TIMING = "--time" in sys.argv

data_dir = Path(__file__).parent
for subdir in data_dir.iterdir():
    if not subdir.is_dir():
        continue

    times = {}
    dest_dir = (subdir / "transcriptions") if not IS_TIMING else (subdir / "transcriptions-timing")
    dest_dir.mkdir(exist_ok=True)
    for audio_fp in subdir.glob("*.m4a"):
        out_fp = dest_dir / f"{audio_fp.stem}.json"
        if out_fp.exists() and not IS_TIMING:
            print(f"Exists: {out_fp}")
            continue

        print(f"Transcribing: {audio_fp}")
        start = time.perf_counter()
        subprocess.run(
            [
                "whisper",
                "--model",
                "turbo",
                "--device",
                "cuda",
                "-o",
                str(dest_dir),
                "--output_format",
                "all",
                "--language",
                "en",
                str(audio_fp),
            ],
            check=True,
        )
        end = time.perf_counter()
        print(f"Done in {end - start}")
        times[audio_fp.stem] = end - start

    if IS_TIMING:
        with open(subdir / "transcription-timing.json", "w") as f:
            json.dump(times, f, indent=2)

print("Done")

# for filename in *.m4a; do
#   out_filename="transcriptions/$(basename "$filename" .m4a).json"
#   if [ -f "$out_filename" ]; then
#     echo "Exists: $out_filename"
#     continue;
#   fi
#   whisper --model turbo --device cuda -o transcriptions --output_format all --language en "$filename"
# done
# echo done;
