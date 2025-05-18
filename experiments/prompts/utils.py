import re
from pathlib import Path

parent_dir = Path(__file__).parent


def read_prompt(name: str):
    """Read a prompt from this dir and return its contents."""
    data = (parent_dir / name).read_text()
    # do the markdown thing, and replace single line breaks that aren't followed by
    # - other whitespace with normal space
    # - a list or header
    data = re.sub(r"(?<![ \n])\n(?!\s*\n|[\-#*])", " ", data)
    return data.strip()
