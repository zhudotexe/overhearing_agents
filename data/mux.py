"""
Usage: python mux.py

For each subdirectory of data, muxes *.m4a into subdir/muxed/*.pcm.
"""

import subprocess
from pathlib import Path

data_dir = Path(__file__).parent
for subdir in data_dir.iterdir():
    if not subdir.is_dir():
        continue
    (subdir / "muxed").mkdir(exist_ok=True)
    for audio_fp in subdir.glob("*.m4a"):
        out_fp = subdir / f"muxed/{audio_fp.stem}.pcm"
        if out_fp.exists():
            print(f"Exists: {out_fp}")
            continue
        subprocess.run(
            [
                "ffmpeg",
                "-i",
                str(audio_fp),
                "-f",
                "s16le",
                "-acodec",
                "pcm_s16le",
                "-ac",
                "1",
                "-ar",
                "24000",
                str(out_fp),
            ],
            check=True,
        )
print("Done")

# for dir in */; do
#   for filename in *.m4a; do
#     out_filename="muxed/$(basename "$filename" .m4a).$fmt"
#     if [ -f "$out_filename" ]; then
#       echo "Exists: $out_filename"
#       continue;
#     fi
#     ffmpeg -i "$filename" -f s16le -acodec pcm_s16le -ac 1 -ar 24000 "$out_filename"
#   done
# done
# echo done;
