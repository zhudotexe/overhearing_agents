import json
import uuid
from enum import Enum
from typing import Annotated, Callable, Literal

from kani import AIParam, ai_function
from pydantic import BaseModel, Field, SerializeAsAny
from rapidfuzz import process

from overhearing_agents import config, events
from overhearing_agents.kanis.base import BaseKani
from overhearing_agents.state import Suggestion
from overhearing_agents.utils import DynamicSubclassDeser
from . import gamedata
from .gamedata import compendium

# temporary hardcoded stuff
ALL_NPCS = [
    "A'nahn",
    "Admiral Cutter",
    "Akita",
    "Akkar",
    "Amanda Heathertoes",
    "Ara",
    "Charles",
    "Chroma",
    "Clever Song",
    "Eleanor",
    "Frivien",
    "Hanabiko K'lcetta",
    "Ilyana",
    "Julie",
    "Kiai (The Sage)",
    "King Remus",
    "Leokas",
    "Nymeth",
    "Palladia",
    "Prof. Atriaz",
    "Prof. Dekira",
    "Royal Chef Vane",
    "Sear",
    "Ser Gordon",
    "Ser Gordon-K'lcetta",
    "The Big Cheese",
    "The Dread Emperor Seifer",
    "Tastreus Arnauth",
    "Xenia Illmin",
    "Xenia Illmin (Ascendant)",
]


# ==== enums ====
class FoundryStageActionType(Enum):
    list_all_npcs = "LIST_ALL_NPCS"
    list_stage_npcs = "LIST_STAGE_NPCS"
    add_npc_to_stage = "ADD_NPC_TO_STAGE"
    remove_npc_from_stage = "REMOVE_NPC_FROM_STAGE"


class DNDEntityType(Enum):
    any = "any"  # search everything
    background = "background"
    feat = "feat"
    item = "item"  # includes base-items and item groups
    race = "race"  # includes subraces
    creature = "monster"
    class_feature = "class_feature"  # includes subclass features, optional features
    spell = "spell"
    # rule = "rule"


# ==== Foundry payloads ====
class FoundryAction(DynamicSubclassDeser, BaseModel):
    """The base class for all Foundry actions."""

    __discriminator_attr__ = "type"
    type: str
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))


class FoundryListAllNPCs(FoundryAction):
    """List all NPCs in the Foundry game."""

    type: Literal["list_all_npcs"] = "list_all_npcs"


class FoundryListStageNPCs(FoundryAction):
    """List all NPCs who are on stage."""

    type: Literal["list_stage_npcs"] = "list_stage_npcs"


class FoundryAddNPCToStage(FoundryAction):
    """Add an NPC to stage and show them to players."""

    type: Literal["add_npc_to_stage"] = "add_npc_to_stage"
    npc_name: str


class FoundryRemoveNPCFromStage(FoundryAction):
    """Remove an NPC from the stage."""

    type: Literal["remove_npc_from_stage"] = "remove_npc_from_stage"
    npc_name: str


class FoundrySendNPCSpeech(FoundryAction):
    """Send NPC speech to the stage."""

    type: Literal["send_npc_speech"] = "send_npc_speech"
    npc_name: str
    text: str


class FoundryActionEvent(events.UserEvent):
    """The websocket event for communicating with Foundry VTT."""

    type: Literal["foundry_action"] = "foundry_action"
    action: SerializeAsAny[FoundryAction]


# ==== suggestions ====
class DNDSuggestFoundry(Suggestion):
    suggest_type: Literal["foundry"] = "foundry"
    action: SerializeAsAny[FoundryAction]


class DNDSuggestImprovisedNPC(Suggestion):
    suggest_type: Literal["improvised_npc"] = "improvised_npc"
    # todo other properties here... for now just copy whatever the LLM generates
    # personality traits, bonds, flows, etc
    race: str = None
    background: str = None
    culture: str = None


class DNDSuggestEntity(Suggestion):
    suggest_type: Literal["gamedata"] = "gamedata"
    entity_type: str
    entity: gamedata.GamedataEntity
    url: str
    glance_info: str | None = None  # to render in the row


class DNDMixin(BaseKani):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # todo get from foundry on load, this is hardcoded for now
        self.all_npcs = ALL_NPCS
        self.staged_npcs = []

    async def init(self):
        await super().init()
        if not compendium.is_loaded:
            await compendium.load(allowed_sources=config.GAMEDATA_ALLOWED_SOURCES)

    # ==== AI functions ====
    # --- NPCs ---
    @ai_function()
    def npc_stage_event(
        self,
        event_type: Annotated[
            FoundryStageActionType, AIParam(desc="The type of stage event to send to the virtual tabletop.")
        ],
        npc: Annotated[str, AIParam(desc="The name of the npc who is the subject of the event, if any.")] = None,
    ):
        """
        Manage NPCs on the stage of the virtual tabletop that's representing the game.
        You can list all NPCs in the game (LIST_ALL_NPCS), list the NPCs being shown to the players ("on stage", LIST_STAGE_NPCS), add an NPC to the stage (ADD_NPC_TO_STAGE), or remove an NPC from the stage (REMOVE_NPC_FROM_STAGE).
        Call this when a new NPC enters or exits the scene to help the DM visualize the game.
        """
        match event_type:
            case FoundryStageActionType.list_all_npcs:
                # dispatch to foundry
                self.dispatch(FoundryActionEvent(action=FoundryListAllNPCs()))
                return self.all_npcs
            case FoundryStageActionType.list_stage_npcs:
                self.dispatch(FoundryActionEvent(action=FoundryListStageNPCs()))
                return self.staged_npcs
            case FoundryStageActionType.add_npc_to_stage:
                return self._add_npc_to_stage(npc)
            case FoundryStageActionType.remove_npc_from_stage:
                return self._remove_npc_from_stage(npc)
            case _:
                return "Foundry integration is not supported for this event type."

    @ai_function()
    def npc_speech(
        self,
        npc: Annotated[str, AIParam(desc="The name of the npc who is speaking.")],
        speech: Annotated[str, AIParam(desc="The dialogue being said by this NPC.")],
    ):
        """
        Show an NPC speaking to the players on the virtual tabletop representing the game.
        Call this when the DM describes an NPC speaking to the players.
        ONLY call this function with dialog said by the DM, do not come up with your own dialog. Edits for fluency are allowed.
        """
        if npc not in self.all_npcs:
            return (
                f"{npc} is not a configured NPC. The configured NPCs are: {self.all_npcs}. Call this"
                " function again using one of these names exactly to show it to the players."
            )
        if npc not in self.staged_npcs:
            self.staged_npcs.append(npc)
            out = f'{npc} was added to the stage.\n{npc} said: "{speech}"'
        else:
            out = f'{npc} said: "{speech}"'
        # dispatch to frontend
        suggestion = DNDSuggestFoundry(action=FoundrySendNPCSpeech(npc_name=npc, text=speech))
        self.dispatch(events.SuggestionEvent(suggestion=suggestion))
        self.pa_session.suggestion_history.append(suggestion)
        return out

    def _add_npc_to_stage(self, npc_name):
        if npc_name not in self.all_npcs:
            return (
                f"{npc_name} is not a configured NPC. The configured NPCs are: {self.all_npcs}. Call this"
                " function again using one of these names exactly to show it to the players."
            )
        if npc_name in self.staged_npcs:
            return f"{npc_name} is already on stage. No action taken."
        self.staged_npcs.append(npc_name)
        # dispatch to frontend
        suggestion = DNDSuggestFoundry(action=FoundryAddNPCToStage(npc_name=npc_name))
        self.dispatch(events.SuggestionEvent(suggestion=suggestion))
        self.pa_session.suggestion_history.append(suggestion)
        return f"{npc_name} was added to the stage."

    def _remove_npc_from_stage(self, npc_name):
        if npc_name not in self.staged_npcs:
            return (
                f"{npc_name} is not currently on stage. No action taken. The staged NPCs are: {self.staged_npcs}. Call"
                " this function again using one of these names exactly to remove the NPC from stage."
            )
        self.staged_npcs.remove(npc_name)
        # dispatch to frontend
        suggestion = DNDSuggestFoundry(action=FoundryRemoveNPCFromStage(npc_name=npc_name))
        self.dispatch(events.SuggestionEvent(suggestion=suggestion))
        self.pa_session.suggestion_history.append(suggestion)
        return f"{npc_name} was removed from the stage."

    # --- improvised NPCs ---
    # TODO: implement search from 5e tables
    @ai_function()
    def suggest_improvised_npc(self, race: str = None, background: str = None, culture: str = None):
        """
        Generate a new NPC given certain parameters.
        Call this when the DM needs assistance thinking of a new NPC that is not already an existing NPC.
        """
        # dispatch to frontend
        suggestion = DNDSuggestImprovisedNPC(race=race, background=background, culture=culture)
        self.dispatch(events.SuggestionEvent(suggestion=suggestion))
        self.pa_session.suggestion_history.append(suggestion)
        # todo implement - for now, just return a dummy saying that a new NPC was made
        return "A new improvised NPC has been generated and shown to the DM."

    # --- gamedata ---
    @ai_function()
    def search_dnd(
        self,
        entity_type: Annotated[DNDEntityType, AIParam(desc="The type of entity to search for.")],
        name: Annotated[
            str,
            AIParam(
                desc="The name of the entity to search for. If no exact match is found, returns the closest matches."
            ),
        ],
    ):
        """
        Search the D&D sourcebooks for a certain entity (e.g., spell, creature, class feature) and show its information to the DM.
        """
        match entity_type:
            case DNDEntityType.any:
                search_list = list(compendium.all)
            case DNDEntityType.background:
                search_list = compendium.backgrounds
            case DNDEntityType.feat:
                search_list = compendium.feats
            case DNDEntityType.item:
                search_list = compendium.items
            case DNDEntityType.race:
                search_list = compendium.races
            case DNDEntityType.creature:
                search_list = compendium.creatures
            case DNDEntityType.class_feature:
                search_list = compendium.class_features
            case DNDEntityType.spell:
                search_list = compendium.spells
            case _:
                return "Search is not yet implemented for this type."

        result = find_or_search(name, search_list)
        if isinstance(result, list):
            return self._ambiguous(result)
        return self._gamedata_suggestion(result)

    def _gamedata_suggestion(self, entity: gamedata.GamedataT):
        """The model suggests showing this entity to the DM. Show the model what it sent."""
        entity_type = type(entity).__name__
        # dispatch to frontend
        suggestion = DNDSuggestEntity(
            entity_type=entity_type, entity=entity, url=entity.get_embed_url(), glance_info=entity.get_glance_info()
        )
        self.dispatch(events.SuggestionEvent(suggestion=suggestion))
        self.pa_session.suggestion_history.append(suggestion)
        # print it
        print("=" * (len(entity_type) + len(entity.qualified_name) + 6))
        print(f"| {entity_type.upper()}: {entity.qualified_name} |")
        print("=" * (len(entity_type) + len(entity.qualified_name) + 6))
        # send the result to the model too
        entity_data = entity.model_dump(mode="json", exclude_unset=True, exclude_none=True)
        return json.dumps({
            entity_type: entity_data,
            "msg": (
                f"The {entity_type}'s information has been shown to the DM. You do not need to echo any of this"
                " information to the DM."
            ),
        })

    def _ambiguous(self, options):
        """The model's search did not return an exact result. Show the model the options."""
        # with no metadata
        # return json.dumps({
        #     "msg": (
        #         f"There are multiple possible matches, so nothing was shown to the DM. Call this function again with"
        #         f" one of these names exactly to show it to the DM."
        #     ),
        #     "results": [e.qualified_name for e, score in options],
        # })
        # with gamedata metadata
        return json.dumps({
            "msg": (
                f"There are multiple possible matches, so nothing was shown to the DM. Call this function again with"
                f" one of these names exactly to show it to the DM."
            ),
            "results": [
                {
                    "name": e.qualified_name,
                    **e.model_dump(
                        mode="json",
                        exclude_unset=True,
                        exclude_none=True,
                        include=(  # only include basics for reference
                            "source",
                            "type",
                            "rarity",
                            "size",
                            "alignment",
                            "cr",
                            "class_name",
                            "subclass_short_name",
                            "prerequisite",
                            "level",
                            "school",
                            "time",
                            "range",
                            "components",
                        ),
                    ),
                }
                for e, score in options
            ],
        })


def search(
    query: str,
    choices: list[gamedata.GamedataT],
    key: Callable[[gamedata.GamedataT], str] = lambda e: e.qualified_name.lower(),
    **kwargs,
) -> list[tuple[gamedata.GamedataT, float]]:
    """Return a list of (entity, score), sorted by score desc."""
    choice_names = list(map(key, choices))
    result = process.extract(query.lower(), choice_names, **kwargs)
    return [(choices[idx], score) for _, score, idx in result]


def find_or_search(
    query: str,
    choices: list[gamedata.GamedataT],
    key: Callable[[gamedata.GamedataT], str] = lambda e: e.qualified_name.lower(),
    **kwargs,
) -> gamedata.GamedataT | list[tuple[gamedata.GamedataT, float]]:
    """Like search(), but returns only the match if it is a perfect match, otherwise returns search results."""
    results = search(query, choices, key=key, **kwargs)
    if results and results[0][1] == 100:
        return results[0][0]
    return results
