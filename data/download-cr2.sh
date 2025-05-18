#!/bin/bash
# Download the Critical Role Campaign 2 dataset.

yt-dlp \
  -o "cr2/%(playlist_index)s__%(title)s.%(ext)s" --restrict-filenames \
  -N 4 \
  -f ba \
  -x --audio-format m4a --audio-quality 2 \
  "https://www.youtube.com/watch?v=byva0hOj8CU&list=PL1tiwbzkOjQxD0jjAE7PsWoaCrs0EkBH2"
