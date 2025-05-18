#!/bin/bash
# Download the Critical Role Campaign 1 dataset.

yt-dlp \
  -o "cr/%(playlist_index)s__%(title)s.%(ext)s" --restrict-filenames \
  -N 4 \
  -f ba \
  -x --audio-format m4a --audio-quality 2 \
  "https://www.youtube.com/watch?v=i-p9lWIhcLQ&list=PL7atuZxmT954bCkC062rKwXTvJtcqFB8i"
