"""
Helpers to extract mentioned entities from text.
🍵
"""

import asyncio
import logging
import re
from typing import NamedTuple

from overhearing_agents.kanis.dnd import gamedata
from overhearing_agents.kanis.dnd.ai import ALL_NPCS

log = logging.getLogger(__name__)


class EntityMatch(NamedTuple):
    entity: gamedata.GamedataT
    match: re.Match


class NPCMatch(NamedTuple):
    npc: str
    match: re.Match


async def extract_gamedata_entities(text, case_sensitive=False, normalize=False) -> list[EntityMatch]:
    """
    Given a string possibly containing monster names, returns a list of pairs (monster, positions)
    where `positions` are the indexes of `text` where the monster name was found.
    Sorted by length of monster name, descending.

    :param case_sensitive: Whether to match lowercase names.
    :param normalize: Whether to normalize all input text and regexes (remove punctuation). Might make match spans
        misaligned with the input text.
    """
    # make sure the gamedata compendium is loaded
    if not gamedata.compendium.is_loaded:
        await gamedata.compendium.load()

    if normalize:
        text = do_normalize(text)

    log.debug(f"Finding matches for text {text!r}")
    matches = []

    potential_matches = find_potential_gamedata_matches(text, case_sensitive=case_sensitive, normalize=normalize)
    if not potential_matches:
        log.debug(f"No matches found for {text!r}")
    while potential_matches:
        best_match = potential_matches.pop(0)
        matches.append(best_match)
        re_match = best_match.match
        log.debug(f"\tMatch: {re_match[0]!r}")

        # replace matches with empty space to keep pos
        match_len = len(re_match[0])
        text = text[: re_match.start()] + " " * match_len + text[re_match.start() + match_len :]

        log.debug(f"\tNext iteration: {text!r}")
        # remove the matches that no longer match
        for other_match in reversed(potential_matches):
            # if it overlaps, check if it still matches
            # we only need to check for contain since they are in descending length
            if (
                re_match.start() <= other_match.match.start() <= re_match.end()
                or re_match.start() <= other_match.match.end() <= re_match.end()
            ) and not re.match(
                get_gamedata_name_re(other_match.entity, normalize=normalize), text[other_match.match.start() :]
            ):
                potential_matches.remove(other_match)

    return matches


def find_potential_gamedata_matches(query: str, case_sensitive=False, normalize=False) -> list[EntityMatch]:
    """
    Find all potential monsters mentioned in `query`
    Returns a list of MonsterMatches sorted by match length descending
    """
    flags = re.NOFLAG if case_sensitive else re.IGNORECASE
    matches = []
    for entity in gamedata.compendium.all:
        for entity_match in re.finditer(get_gamedata_name_re(entity, normalize=normalize), query, flags=flags):
            matches.append(EntityMatch(entity, entity_match))
    return sorted(matches, key=lambda m: len(m.match[0]), reverse=True)


def get_gamedata_name_re(entity: gamedata.GamedataT, normalize=False) -> str:
    if normalize:
        return rf"\b{re.escape(do_normalize(entity.qualified_name))}\b"
    return rf"\b{re.escape(entity.qualified_name)}\b"


# hacky copy for NPC names
async def extract_npc_entities(text, case_sensitive=False, normalize=False) -> list[NPCMatch]:
    if normalize:
        text = do_normalize(text)

    log.debug(f"Finding matches for text {text!r}")
    matches = []

    potential_matches = find_potential_npc_matches(text, case_sensitive=case_sensitive, normalize=normalize)
    if not potential_matches:
        log.debug(f"No matches found for {text!r}")
    while potential_matches:
        best_match = potential_matches.pop(0)
        matches.append(best_match)
        re_match = best_match.match
        log.debug(f"\tMatch: {re_match[0]!r}")

        # replace matches with empty space to keep pos
        match_len = len(re_match[0])
        text = text[: re_match.start()] + " " * match_len + text[re_match.start() + match_len :]

        log.debug(f"\tNext iteration: {text!r}")
        # remove the matches that no longer match
        for other_match in reversed(potential_matches):
            # if it overlaps, check if it still matches
            # we only need to check for contain since they are in descending length
            if (
                re_match.start() <= other_match.match.start() <= re_match.end()
                or re_match.start() <= other_match.match.end() <= re_match.end()
            ) and not re.match(get_name_re(other_match.npc, normalize=normalize), text[other_match.match.start() :]):
                potential_matches.remove(other_match)

    return matches


def find_potential_npc_matches(query: str, case_sensitive=False, normalize=False) -> list[NPCMatch]:
    flags = re.NOFLAG if case_sensitive else re.IGNORECASE
    matches = []
    for npc in ALL_NPCS:
        for entity_match in re.finditer(get_name_re(npc, normalize=normalize), query, flags=flags):
            matches.append(NPCMatch(npc, entity_match))
    return sorted(matches, key=lambda m: len(m.match[0]), reverse=True)


def get_name_re(name: str, normalize=False) -> str:
    if normalize:
        return rf"\b{re.escape(do_normalize(name))}\b"
    return rf"\b{re.escape(name)}\b"


def do_normalize(text: str) -> str:
    alnum = re.sub(r"[^\w ]", " ", text)
    return re.sub(r"\s+", " ", alnum)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    test_str = "an Ancient Red Dragon (2014) and an Ancient Red Dragon (2024) and 3 Skeletons and a Dire Wolf (2024)"
    # test_str = "{1d4} Snowy Owlbear use Flash of Genius"
    print(test_str)
    referenced_entities = asyncio.run(extract_gamedata_entities(test_str, normalize=True))
    for e, match in referenced_entities:
        print(f"MATCH: {e.name} ({e.get_embed_url()})")

    test_str = "Ser Gordon-K'lcetta walks into the room along with the king"
    print(test_str)
    referenced_entities = asyncio.run(extract_npc_entities(test_str, normalize=True))
    for e, match in referenced_entities:
        print(f"MATCH: {e}")
