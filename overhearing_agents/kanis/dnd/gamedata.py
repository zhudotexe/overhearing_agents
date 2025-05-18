import itertools
import json
from pathlib import Path
from typing import Iterable, TypeVar

import aiofiles
import pydantic

from .gamedata_models import (
    Background,
    BaseItem,
    Class,
    ClassFeature,
    Feat,
    GamedataEntity,
    Item,
    ItemGroup,
    Monster,
    OptionalFeature,
    Race,
    Spell,
    Subclass,
    SubclassFeature,
    Subrace,
)

GAMEDATA_DIR = Path(__file__).parent / "data"
GAMEDATA_PROCESSING_DIR = Path(__file__).parent / "data_processing"
GamedataT = TypeVar("GamedataT", bound=GamedataEntity)


class Gamedata:
    def __init__(self):
        self.backgrounds: list[Background] = []
        self.feats: list[Feat] = []
        self._items: list[Item] = []
        self._item_groups: list[ItemGroup] = []
        self._base_items: list[BaseItem] = []
        self._races: list[Race] = []
        self._subraces: list[Subrace] = []
        self.creatures: list[Monster] = []
        self._classes: list[Class] = []
        self._subclasses: list[Subclass] = []
        self._class_features: list[ClassFeature] = []
        self._subclass_features: list[SubclassFeature] = []
        self._optional_features: list[OptionalFeature] = []
        self.spells: list[Spell] = []
        self.rules = []  # todo

        self.is_loaded = False

    # derived
    @property
    def items(self):
        return self._items + self._item_groups + self._base_items

    @property
    def races(self):
        return self._races + self._subraces

    @property
    def classes(self):
        return self._classes + self._subclasses

    @property
    def class_features(self):
        return self._class_features + self._subclass_features + self._optional_features

    @property
    def all(self) -> Iterable[GamedataT]:
        # noinspection PyTypeChecker
        return itertools.chain(
            self.backgrounds,
            self.feats,
            self.items,
            self.races,
            self.creatures,
            self.classes,
            self.class_features,
            self.spells,
        )

    # load
    async def load(self, allowed_sources=None):
        # single-files
        self.backgrounds = await self.read_datafile_as(
            GAMEDATA_DIR / "backgrounds.json", Background, allowed_sources=allowed_sources
        )
        self.feats = await self.read_datafile_as(GAMEDATA_DIR / "feats.json", Feat, allowed_sources=allowed_sources)
        self._items = await self.read_datafile_as(GAMEDATA_DIR / "items.json", Item, allowed_sources=allowed_sources)
        self._item_groups = await self.read_datafile_as(
            GAMEDATA_DIR / "items.json", ItemGroup, "itemGroup", allowed_sources=allowed_sources
        )
        self._base_items = await self.read_datafile_as(
            GAMEDATA_DIR / "items-base.json", BaseItem, "baseitem", allowed_sources=allowed_sources
        )
        self._races = await self.read_datafile_as(GAMEDATA_DIR / "races.json", Race, allowed_sources=allowed_sources)
        self._subraces = await self.read_datafile_as(
            GAMEDATA_DIR / "races.json", Subrace, "subrace", allowed_sources=allowed_sources
        )
        self._optional_features = await self.read_datafile_as(
            GAMEDATA_DIR / "optionalfeatures.json", OptionalFeature, allowed_sources=allowed_sources
        )
        # multi-files
        self.creatures = await self.read_datafile_as(
            GAMEDATA_PROCESSING_DIR / "monsters-merged.json", Monster, "monster", allowed_sources=allowed_sources
        )
        self._classes = await self.read_indexed_dir_as(
            GAMEDATA_DIR / "class", Class, "class", allowed_sources=allowed_sources
        )
        self._subclasses = await self.read_indexed_dir_as(
            GAMEDATA_DIR / "class", Subclass, "subclass", allowed_sources=allowed_sources
        )
        self._class_features = await self.read_indexed_dir_as(
            GAMEDATA_DIR / "class", ClassFeature, "classFeature", allowed_sources=allowed_sources
        )
        self._subclass_features = await self.read_indexed_dir_as(
            GAMEDATA_DIR / "class", SubclassFeature, "subclassFeature", allowed_sources=allowed_sources
        )
        self.spells = await self.read_indexed_dir_as(
            GAMEDATA_DIR / "spells", Spell, "spell", allowed_sources=allowed_sources
        )
        self.is_loaded = True

    @staticmethod
    async def read_datafile_raw(fp: Path, key: str = None) -> list[dict]:
        if key is None:
            key = fp.stem.rstrip("s")
        async with aiofiles.open(fp) as f:
            data = json.loads(await f.read())
        if key not in data:
            return []
        return data[key]

    async def read_datafile_as(
        self, fp: Path, t: type[GamedataT], key: str = None, *, allowed_sources=None
    ) -> list[GamedataT]:
        """Load a datafile and return the list of entities under the given key, with source filtering"""
        if allowed_sources is not None:
            allowed_sources = {s.lower() for s in allowed_sources}
        data = await self.read_datafile_raw(fp, key)
        out = []
        for d in data:
            try:
                e = t.model_validate(d)
                if allowed_sources is not None and e.source.lower() not in allowed_sources:
                    continue
                if e.exclude_from_compendium():
                    continue
                out.append(e)
            except pydantic.ValidationError:
                # some monsters don't actually have all the info needed
                # just continue
                continue
        return out

    async def read_indexed_dir_as(
        self, fp: Path, t: type[GamedataT], key: str = None, *, allowed_sources=None
    ) -> list[GamedataT]:
        """Load a dir, merging files by the index.json file in that dir"""
        assert fp.is_dir()
        async with aiofiles.open(fp / "index.json") as f:
            index = json.loads(await f.read())  # src -> datafile name

        out = []
        for df in index.values():
            if key is None:
                key, *_ = fp.stem.split("-")
            out.extend(await self.read_datafile_as(fp / df, t, key, allowed_sources=allowed_sources))
        return out


compendium = Gamedata()
