r"""
much of these are generated!
Use this command to generate them:
datamodel-codegen \
    --base-class GamedataBase \
    --use-standard-collections \
    --use-union-operator \
    --snake-case-field \
    --no-alias \
    --input overhearing_agents/kanis/dnd/data/....json
"""

import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from overhearing_agents.config import GAMEDATA_BASE_URL


def partial_urlencode(s):
    return s.replace(" ", "%20").replace("+", "%2b").replace(";", "%3b")


def slugify(s):
    return re.sub(r"[^a-zA-Z ]", "", s).replace(" ", "-").lower()


class GamedataBase(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, extra="allow")


class GamedataEntity(GamedataBase):
    name: str
    source: str

    @property
    def qualified_name(self):
        return self.name

    def get_embed_url(self) -> str:
        """Return a URL that embeds this entity in an iframe."""
        return "http://example.com"

    def get_glance_info(self) -> str | None:
        """Return a short amount of text for glancing."""
        return None

    def exclude_from_compendium(self):
        """Return True if this entity shouldn't be included in compendium."""
        return False


# =============================
# backgrounds
class Background(GamedataEntity):
    name: str
    source: str
    page: int
    srd: bool | None = None
    basic_rules: bool | None = None
    skill_proficiencies: list | None = None
    language_proficiencies: list | None = None
    starting_equipment: list | None = None
    entries: list | None = None
    has_fluff: bool | None = None
    tool_proficiencies: list | None = None
    feats: list | None = None
    from_feature: dict | None = None
    has_fluff_images: bool | None = None
    field_copy: dict | None = None
    additional_spells: list | None = None
    additional_sources: list | None = None
    prerequisite: list | None = None
    skill_tool_language_proficiencies: list | None = None
    other_sources: list | None = None
    weapon_proficiencies: list | None = None

    def get_embed_url(self) -> str:
        name_enc = partial_urlencode(self.name)
        return f"{GAMEDATA_BASE_URL}/backgrounds.html#{name_enc}_{self.source.lower()}"


# books
class Book(GamedataEntity):
    name: str
    id: str
    source: str
    group: str
    cover: Any
    published: str
    author: str
    contents: list
    alias: list | None = None

    def get_embed_url(self) -> str:
        return f"{GAMEDATA_BASE_URL}/book.html#{self.source.lower()}"


# feats
class Feat(GamedataEntity):
    name: str
    source: str
    page: int | None = None
    prerequisite: list | None = None
    ability: list | None = None
    additional_spells: list | None = None
    entries: list
    has_fluff_images: bool | None = None
    tool_proficiencies: list | None = None
    optionalfeature_progression: list | None = None
    resist: list | None = None
    language_proficiencies: list | None = None
    srd: bool | None = None
    weapon_proficiencies: list | None = None
    armor_proficiencies: list | None = None
    bonus_senses: list | None = None
    trait_tags: list[str] | None = None
    skill_proficiencies: list | None = None
    saving_throw_proficiencies: list | None = None
    expertise: list | None = None
    skill_tool_language_proficiencies: list | None = None
    additional_sources: list | None = None

    def get_embed_url(self) -> str:
        name_enc = partial_urlencode(self.name)
        return f"{GAMEDATA_BASE_URL}/feats.html#{name_enc}_{self.source.lower()}"


# items
class Item(GamedataEntity):
    name: str
    source: str
    page: int | None = None
    rarity: str | None = None
    req_attune: bool | str | None = None
    req_attune_tags: list | None = None
    wondrous: bool | None = None
    bonus_spell_attack: str | None = None
    bonus_spell_save_dc: str | None = None
    focus: bool | list[str] | None = None
    entries: list | None = None
    weight: float | None = None
    has_fluff_images: bool | None = None
    base_item: str | None = None
    type: str | None = None
    weapon_category: str | None = None
    property: list[str] | None = None
    dmg1: str | None = None
    dmg_type: str | None = None
    bonus_weapon: str | None = None
    tier: str | None = None
    loot_tables: list[str] | None = None
    srd: bool | str | None = None
    field_copy: dict | None = None
    bonus_ac: str | None = None
    bonus_saving_throw: str | None = None
    optionalfeatures: list[str] | None = None
    resist: list[str] | None = None
    ac: int | None = None
    basic_rules: bool | None = None
    value: float | None = None
    recharge: str | None = None
    recharge_amount: int | str | None = None
    charges: int | str | None = None
    misc_tags: list[str] | None = None
    detail1: str | None = None
    tattoo: bool | None = None
    has_refs: bool | None = None
    attached_spells: list[str] | None = None
    crew: int | None = None
    veh_ac: int | None = None
    veh_hp: int | None = None
    veh_speed: float | None = None
    cap_passenger: int | None = None
    cap_cargo: float | None = None
    condition_immune: list[str] | None = None
    dmg2: str | None = None
    grants_proficiency: bool | None = None
    additional_sources: list | None = None
    additional_entries: list | None = None
    light: list | None = None
    modify_speed: dict | None = None
    scf_type: str | None = None
    curse: bool | None = None
    ability: dict | None = None
    see_also_vehicle: list[str] | None = None
    range: str | None = None
    strength: str | None = None
    stealth: bool | None = None
    immune: list[str] | None = None
    vulnerable: list[str] | None = None
    poison: bool | None = None
    poison_types: list[str] | None = None
    sentient: bool | None = None
    container_capacity: dict | None = None
    pack_contents: list | None = None
    atomic_pack_contents: bool | None = None
    bonus_weapon_attack: str | None = None
    other_sources: list | None = None
    grants_language: bool | None = None
    staff: bool | None = None
    age: str | None = None
    veh_dmg_thresh: int | None = None
    bonus_weapon_damage: str | None = None
    crit_threshold: int | None = None
    carrying_capacity: int | None = None
    speed: int | None = None
    ammo_type: str | None = None
    alias: list[str] | None = None
    see_also_deck: list[str] | None = None
    reprinted_as: list[str] | None = None
    has_fluff: bool | None = None
    req_attune_alt: str | None = None
    reach: int | None = None
    bonus_proficiency_bonus: str | None = None
    firearm: bool | None = None
    bonus_saving_throw_concentration: str | None = None
    type_alt: str | None = None
    dexterity_max: None = None
    crew_min: int | None = None
    crew_max: int | None = None
    travel_cost: int | None = None
    shipping_cost: int | None = None
    spell_scroll_level: int | None = None
    bonus_ability_check: str | None = None
    weight_note: str | None = None

    def get_embed_url(self) -> str:
        name_enc = slugify(self.name)
        return f"{GAMEDATA_BASE_URL}/items/{name_enc}-{self.source.lower()}.html"

    def get_glance_info(self) -> str | None:
        out = []
        if self.value:
            out.append(f"{self.value/100} gp")
        if self.weight:
            out.append(f"{self.weight} lbs")
        if self.req_attune:
            out.append("(attun.)")
        if self.rarity and self.rarity != "none":
            out.append(self.rarity)

        if out:
            return "\t".join(out)
        return None


class ItemGroup(GamedataEntity):
    name: str
    source: str
    page: int
    rarity: str
    req_attune: bool | str | None = None
    wondrous: bool | None = None
    tattoo: bool | None = None
    entries: list | None = None
    items: list[str]
    base_item: str | None = None
    type: str | None = None
    req_attune_tags: list | None = None
    weight: float | None = None
    weapon_category: str | None = None
    property: list[str] | None = None
    dmg1: str | None = None
    dmg_type: str | None = None
    bonus_weapon: str | None = None
    has_fluff_images: bool | None = None
    scf_type: str | None = None
    focus: list[str] | None = None
    tier: str | None = None
    immune: list[str] | None = None
    resist: list[str] | None = None
    condition_immune: list[str] | None = None
    ac: int | None = None
    bonus_ac: str | None = None
    stealth: bool | None = None
    attached_spells: list[str] | None = None
    curse: bool | None = None
    strength: str | None = None
    loot_tables: list[str] | None = None
    srd: bool | None = None
    basic_rules: bool | None = None
    recharge: str | None = None
    sentient: bool | None = None
    range: str | None = None
    charges: int | None = None
    ammo_type: str | None = None
    bonus_saving_throw: str | None = None
    misc_tags: list[str] | None = None
    ability: dict | None = None
    dmg2: str | None = None
    has_fluff: bool | None = None
    grants_proficiency: bool | None = None
    bonus_weapon_attack: str | None = None
    recharge_amount: str | None = None
    modify_speed: dict | None = None
    other_sources: list | None = None
    bonus_spell_attack: str | None = None
    bonus_spell_save_dc: str | None = None
    staff: bool | None = None

    def get_embed_url(self) -> str:
        name_enc = slugify(self.name)
        return f"{GAMEDATA_BASE_URL}/items/{name_enc}-{self.source.lower()}.html"

    def get_glance_info(self) -> str | None:
        out = []
        if self.weight:
            out.append(f"{self.weight} lbs")
        if self.req_attune:
            out.append("(attun.)")
        if self.rarity != "none":
            out.append(self.rarity)

        if out:
            return "\t".join(out)
        return None


# items-base
class BaseItem(GamedataEntity):
    name: str
    source: str
    page: int
    type: str
    rarity: str
    weight: float | None = None
    weapon_category: str | None = None
    age: str | None = None
    property: list[str] | None = None
    range: str | None = None
    reload: int | None = None
    dmg1: str | None = None
    dmg_type: str | None = None
    firearm: bool | None = None
    weapon: bool | None = None
    ammo_type: str | None = None
    srd: bool | None = None
    basic_rules: bool | None = None
    value: float | None = None
    arrow: bool | None = None
    pack_contents: list | None = None
    dmg2: str | None = None
    axe: bool | None = None
    entries: list | None = None
    needle_blowgun: bool | None = None
    ac: int | None = None
    armor: bool | None = None
    strength: str | None = None
    stealth: bool | None = None
    club: bool | None = None
    bolt: bool | None = None
    scf_type: str | None = None
    dagger: bool | None = None
    sword: bool | None = None
    has_fluff: bool | None = None
    cell_energy: bool | None = None
    misc_tags: list[str] | None = None
    polearm: bool | None = None
    crossbow: bool | None = None
    has_fluff_images: bool | None = None
    spear: bool | None = None
    lance: bool | None = None
    hammer: bool | None = None
    bow: bool | None = None
    mace: bool | None = None
    bullet_firearm: bool | None = None
    net: bool | None = None
    rapier: bool | None = None
    bullet_sling: bool | None = None
    staff: bool | None = None

    def get_embed_url(self) -> str:
        name_enc = slugify(self.name)
        return f"{GAMEDATA_BASE_URL}/items/{name_enc}-{self.source.lower()}.html"

    def get_glance_info(self) -> str | None:
        out = []
        if self.value:
            out.append(f"{self.value/100} gp")
        if self.weight:
            out.append(f"{self.weight} lbs")
        if self.rarity and self.rarity != "none":
            out.append(self.rarity)

        if out:
            return "\t".join(out)
        return None


# races
class Race(GamedataEntity):
    name: str
    source: str
    page: int
    size: list[str] | None = None
    speed: int | dict | None = None
    ability: list | None = None
    trait_tags: list[str] | None = None
    language_proficiencies: list | None = None
    entries: list | None = None
    other_sources: list | None = None
    reprinted_as: list[str] | None = None
    age: dict | None = None
    sound_clip: dict | None = None
    has_fluff: bool | None = None
    has_fluff_images: bool | None = None
    lineage: bool | str | None = None
    additional_spells: list | None = None
    darkvision: int | None = None
    resist: list | None = None
    field_versions: list | None = None
    height_and_weight: dict | None = None
    skill_proficiencies: list | None = None
    creature_types: list[str] | None = None
    creature_type_tags: list[str] | None = None
    tool_proficiencies: list | None = None
    condition_immune: list[str] | None = None
    field_copy: dict | None = None
    feats: list | None = None
    srd: bool | None = None
    basic_rules: bool | None = None
    weapon_proficiencies: list | None = None
    additional_sources: list | None = None
    blindsight: int | None = None
    immune: list[str] | None = None
    armor_proficiencies: list | None = None
    vulnerable: list[str] | None = None

    def get_embed_url(self) -> str:
        name_enc = partial_urlencode(self.name)
        return f"{GAMEDATA_BASE_URL}/races.html#{name_enc}_{self.source.lower()}"


class Subrace(GamedataEntity):
    name: str | None = None
    source: str
    race_name: str
    race_source: str
    page: int
    reprinted_as: list[str] | None = None
    ability: list | None = None
    entries: list | None = None
    has_fluff: bool | None = None
    has_fluff_images: bool | None = None
    skill_proficiencies: list | None = None
    srd: bool | None = None
    field_versions: list | None = None
    darkvision: int | None = None
    resist: list[str] | None = None
    overwrite: dict | None = None
    other_sources: list | None = None
    trait_tags: list[str] | None = None
    language_proficiencies: list | None = None
    additional_spells: list | None = None
    basic_rules: bool | None = None
    height_and_weight: dict | None = None
    armor_proficiencies: list | None = None
    alias: list[str] | None = None
    weapon_proficiencies: list | None = None
    speed: int | dict | None = None
    skill_tool_language_proficiencies: list | None = None
    age: dict | None = None
    tool_proficiencies: list | None = None
    sound_clip: dict | None = None
    feats: list | None = None

    @property
    def qualified_name(self):
        return f"{self.name} {self.race_name}"

    def get_embed_url(self) -> str:
        race_name_enc = partial_urlencode(self.race_name)
        subrace_name_enc = partial_urlencode(self.name)
        return f"{GAMEDATA_BASE_URL}/races.html#{race_name_enc}%20({subrace_name_enc})_{self.source.lower()}"

    def exclude_from_compendium(self):
        return self.name is None


# tables
class Table(GamedataEntity):
    name: str
    source: str
    page: int
    caption: str | None = None
    col_labels: list[str] | None = None
    col_styles: list[str]
    rows: list
    other_sources: list | None = None
    srd: bool | None = None
    basic_rules: bool | None = None


# bestiary
class Monster(GamedataEntity):
    name: str
    source: str
    page: int | None = None
    size: list[str] | None = None
    type: str | dict | None = None
    alignment: list | None = None
    alignment_prefix: str | None = None
    ac: list | None = None
    hp: dict | None = None
    speed: dict | None = None
    strength: int = Field(alias="str")
    dexterity: int = Field(alias="dex")
    constitution: int = Field(alias="con")
    intelligence: int = Field(alias="int")
    wisdom: int = Field(alias="wis")
    charisma: int = Field(alias="cha")
    senses: list[str] | None = None
    passive: int | str | None = None
    immune: list | None = None
    condition_immune: list | None = None
    languages: list[str] | None = None
    cr: str | dict | None = None
    trait: list[dict] | None = None
    action: list[dict] | None = None
    trait_tags: list[str] | None = None
    sense_tags: list[str] | None = None
    action_tags: list[str] | None = None
    language_tags: list[str] | None = None
    damage_tags: list[str] | None = None
    misc_tags: list[str] | None = None
    saving_throw_forced: list[str] | None = None
    has_token: bool
    has_fluff: bool | None = None
    skill: dict | None = None
    attached_items: list[str] | None = None
    has_fluff_images: bool | None = None
    is_npc: bool | None = None
    is_named_creature: bool | None = None
    group: list[str] | None = None
    srd: bool | None = None
    other_sources: list[dict] | None = None
    save: dict | None = None
    legendary: list[dict] | None = None
    legendary_group: dict | None = None
    variant: list[dict] | None = None
    environment: list[str] | None = None
    dragon_casting_color: str | None = None
    dragon_age: str | None = None
    sound_clip: dict | None = None
    damage_tags_legendary: list[str] | None = None
    condition_inflict: list[str] | None = None
    condition_inflict_legendary: list[str] | None = None
    saving_throw_forced_legendary: list[str] | None = None
    bonus: list[dict] | None = None
    reaction_header: list[str] | None = None
    reaction: list[dict] | None = None
    resist: list | None = None
    spellcasting: list[dict] | None = None
    damage_tags_spell: list[str] | None = None
    spellcasting_tags: list[str] | None = None
    condition_inflict_spell: list[str] | None = None
    saving_throw_forced_spell: list[str] | None = None
    initiative: dict | None = None
    vulnerable: list | None = None
    mythic_header: list[str] | None = None
    mythic: list[dict] | None = None
    field_versions: list[dict] | None = None
    basic_rules: bool | None = None
    alias: list[str] | None = None
    familiar: bool | None = None
    reprinted_as: list[str] | None = None
    alt_art: list[dict] | None = None
    legendary_header: list[str] | None = None
    legendary_actions: int | None = None
    token_credit: str | None = None
    pb_note: str | None = None
    summoned_by_spell: str | None = None
    summoned_by_spell_level: int | None = None
    level: int | None = None
    short_name: bool | str | None = None
    summoned_by_class: str | None = None
    size_note: str | None = None
    action_note: str | None = None
    field_copy: dict | None = None

    def get_embed_url(self) -> str:
        name_enc = slugify(self.name)
        return f"{GAMEDATA_BASE_URL}/bestiary/{name_enc}-{self.source.lower()}.html"

    def exclude_from_compendium(self):
        return self.is_npc


# class
class Class(GamedataEntity):
    name: str
    source: str
    page: int
    other_sources: list | None = None
    hd: dict | None = None
    proficiency: list[str] | None = None
    spellcasting_ability: str | None = None
    caster_progression: str | None = None
    prepared_spells: str | None = None
    prepared_spells_change: str | None = None
    cantrip_progression: list[int] | None = None
    optionalfeature_progression: list | None = None
    starting_proficiencies: dict | None = None
    starting_equipment: dict | None = None
    multiclassing: dict | None = None
    class_table_groups: list[dict] | None = None
    class_features: list[str | dict]
    subclass_title: str | None = None
    has_fluff: bool
    has_fluff_images: bool | None = None
    srd: bool | None = None
    basic_rules: bool | None = None
    is_sidekick: bool | None = None
    spells_known_progression: list[int] | None = None
    additional_spells: list[dict] | None = None
    spells_known_progression_fixed: list[int] | None = None
    spells_known_progression_fixed_allow_lower_level: bool | None = None
    spells_known_progression_fixed_by_level: dict | None = None

    def get_embed_url(self) -> str:
        name_enc = partial_urlencode(self.name)
        return f"{GAMEDATA_BASE_URL}/classes.html#{name_enc}_{self.source.lower()}"


class Subclass(GamedataEntity):
    name: str
    short_name: str
    source: str
    class_name: str
    class_source: str
    page: int
    other_sources: list | None = None
    additional_spells: list | None = None
    subclass_features: list[str]
    has_fluff_images: bool | None = None
    srd: bool | None = None
    basic_rules: bool | None = None
    is_reprinted: bool | None = None
    spellcasting_ability: str | None = None
    optionalfeature_progression: list | None = None
    caster_progression: str | None = None
    cantrip_progression: list[int] | None = None
    spells_known_progression: list[int] | None = None
    subclass_table_groups: list | None = None

    def get_embed_url(self) -> str:
        class_name_enc = partial_urlencode(self.class_name)
        name_enc = partial_urlencode(self.name)
        return f"{GAMEDATA_BASE_URL}/classes.html#{class_name_enc}_{self.class_source.lower()},state:sub_{name_enc}_{self.source.lower()}=b1"


class ClassFeature(GamedataEntity):
    name: str
    source: str
    page: int
    other_sources: list | None = None
    class_name: str
    class_source: str
    level: int
    entries: list
    header: int | None = None
    srd: bool | None = None
    basic_rules: bool | None = None
    is_class_feature_variant: bool | None = None
    consumes: dict | None = None
    type: str | None = None

    def get_embed_url(self) -> str:
        class_name_enc = partial_urlencode(self.class_name)
        return f"{GAMEDATA_BASE_URL}/classes.html#{class_name_enc}_{self.class_source.lower()},state:feature=s{self.level-1}-0"


class SubclassFeature(GamedataEntity):
    name: str
    source: str
    page: int
    other_sources: list | None = None
    class_name: str
    class_source: str
    subclass_short_name: str
    subclass_source: str
    level: int
    entries: list
    header: int | None = None
    type: str | None = None
    consumes: dict | None = None
    is_class_feature_variant: bool | None = None
    srd: bool | None = None
    basic_rules: bool | None = None

    def get_embed_url(self) -> str:
        class_name_enc = partial_urlencode(self.class_name)
        subclass_name_enc = partial_urlencode(self.subclass_short_name)
        return f"{GAMEDATA_BASE_URL}/classes.html#{class_name_enc}_{self.class_source.lower()},state:sub_{subclass_name_enc}_{self.subclass_source.lower()}=b1~feature=s{self.level-1}-0"


class OptionalFeature(GamedataEntity):
    name: str
    source: str
    page: int
    srd: bool | None = None
    feature_type: list[str]
    prerequisite: list[dict] | None = None
    entries: list
    is_class_feature_variant: bool | None = None
    consumes: dict | None = None
    other_sources: list[dict] | None = None
    additional_spells: list[dict] | None = None
    skill_proficiencies: list[dict] | None = None
    senses: list[dict] | None = None
    has_fluff_images: bool | None = None
    optionalfeature_progression: list[dict] | None = None

    def get_embed_url(self) -> str:
        name_enc = partial_urlencode(self.name)
        return f"{GAMEDATA_BASE_URL}/optionalfeatures.html#{name_enc}_{self.source.lower()}"


# spells
class SpellTime(GamedataBase):
    number: int
    unit: str
    condition: str | None = None

    def get_glance_info(self) -> str:
        if self.number == 1 and "action" in self.unit:
            return self.unit.split(" ")[0]
        return f"{self.number} {self.unit}"


class SpellDistance(GamedataBase):
    type: str
    amount: int | None = None

    def get_glance_info(self) -> str:
        if not self.amount:
            return self.type
        return f"{self.amount} {self.type}"


class SpellRange(GamedataBase):
    type: str
    distance: SpellDistance | None = None

    def get_glance_info(self) -> str:
        if not self.distance:
            return "no rng"
        if self.type != "point":
            return self.distance.get_glance_info() + self.type
        return self.distance.get_glance_info()


class SpellMaterial(GamedataBase):
    text: str
    cost: int | None = None
    consume: bool | str | None = None


class SpellComponents(GamedataBase):
    v: bool | None = None
    s: bool | None = None
    m: SpellMaterial | str | None = None


class SpellMeta(GamedataBase):
    ritual: bool


class Spell(GamedataEntity):
    name: str
    source: str
    page: int | None = None
    srd: bool | str | None = None
    basic_rules: bool | None = None
    level: int
    school: str
    time: list[SpellTime]
    range: SpellRange
    components: SpellComponents
    duration: list
    entries: list
    scaling_level_dice: dict | list | None = None
    damage_inflict: list[str] | None = None
    saving_throw: list[str] | None = None
    misc_tags: list[str] | None = None
    area_tags: list[str] | None = None
    other_sources: list | None = None
    entries_higher_level: list | None = None
    meta: SpellMeta | None = None
    condition_inflict: list[str] | None = None
    affects_creature_type: list[str] | None = None
    damage_resist: list[str] | None = None
    has_fluff_images: bool | None = None
    spell_attack: list[str] | None = None
    ability_check: list[str] | None = None
    alias: list[str] | None = None
    condition_immune: list[str] | None = None
    damage_vulnerable: list[str] | None = None
    damage_immune: list[str] | None = None

    def get_embed_url(self) -> str:
        name_enc = slugify(self.name)
        return f"{GAMEDATA_BASE_URL}/spells/{name_enc}-{self.source.lower()}.html"

    # def get_embed_url(self) -> str:
    #     name_enc = partial_urlencode(self.name)
    #     return f"{GAMEDATA_BASE_URL}/spells.html#{name_enc}_{self.source.lower()}"

    def get_glance_info(self) -> str | None:
        time = "Special" if len(self.time) != 1 else self.time[0].get_glance_info()
        conc = "(conc.)" if any("concentration" in t and t["concentration"] for t in self.duration) else ""
        out = [f"L{self.level}", time, self.school, conc, self.range.get_glance_info()]
        return "\t".join(out)


# actions
# generated/bookref-quick (for rules)
