import json

from kani import ChatMessage, FunctionCall, ToolCall

FEWSHOT_REACT = [
    # gamedata tool call 1
    ChatMessage.user("Sending and Augury? Which one were we using? Both?"),
    ChatMessage.assistant(
        "Thought: It seems like the players are checking their spell lists and deciding which to use. I should search"
        " for these spells and show it to the DM.",
        tool_calls=[
            ToolCall.from_function_call(
                FunctionCall(
                    name="search_dnd",
                    arguments=json.dumps({"entity_type": "spell", "name": "Sending"}),
                )
            )
        ],
    ),
    ChatMessage.function(
        "search_dnd",
        json.dumps({
            "Spell": "[example return value omitted]",
            "msg": (
                "The Spell's information has been shown to the DM. You do not need to echo any of this"
                " information to the DM."
            ),
        }),
    ),
    ChatMessage.assistant(
        "Thought: The Sending spell has been shown to the DM. I will now search for the Augury spell.",
        tool_calls=[
            ToolCall.from_function_call(
                FunctionCall(
                    name="search_dnd",
                    arguments=json.dumps({"entity_type": "spell", "name": "Augury"}),
                )
            ),
        ],
    ),
    ChatMessage.function(
        "search_dnd",
        json.dumps({
            "Spell": "[example return value omitted]",
            "msg": (
                "The Spell's information has been shown to the DM. You do not need to echo any of this"
                " information to the DM."
            ),
        }),
    ),
    ChatMessage.assistant(
        "Thought: Both spells mentioned above have been shown to the DM. I'll keep listening for additional"
        " points when I can help the DM."
    ),
    # add npc to stage tool call
    ChatMessage.user("As you discuss, you see Nemura slinking into the room..."),
    ChatMessage.assistant(
        "Thought: It seems like an NPC named Nemura is entering the scene. I should add this NPC to the stage to aid"
        " the players' immersion.",
        tool_calls=[
            ToolCall.from_function_call(
                FunctionCall(
                    name="npc_stage_event",
                    arguments=json.dumps({"event_type": "ADD_TO_STAGE", "npc": "Nemura"}),
                )
            )
        ],
    ),
    ChatMessage.function("npc_stage_event", "[example return value omitted]"),
    ChatMessage.assistant(
        "Thought: The NPC named Nemura has been added to the stage and is now visible to the players. I'll listen for"
        " any narration from the DM to show the players."
    ),
    # interim
    ChatMessage.user("And when she realizes she's been spotted, she gives kind of like an"),
    ChatMessage.assistant(
        "Thought: It seems like Nemura has been spotted by the players, and is now about to say something. I'll keep"
        " listening.",
    ),
    # npc speech tool call
    ChatMessage.user("awkward wave. Hi. Um... lovely weather, huh?"),
    ChatMessage.assistant(
        "Thought: Nemura has said a few words to the players. I'll show this on the virtual tabletop for immersion.",
        tool_calls=[
            ToolCall.from_function_call(
                FunctionCall(
                    name="npc_speech",
                    arguments=json.dumps({"npc": "Nemura", "speech": "...hi. Um, lovely weather, huh?"}),
                )
            )
        ],
    ),
    ChatMessage.function("npc_speech", "[example return value omitted]"),
    ChatMessage.assistant(
        "Thought: Nemura's dialogue has been shown to the players. If the DM says more as Nemura, I'll show that too."
    ),
    # npc remove from stage tool call
    ChatMessage.user("And then she runs away like her life depends on it."),
    ChatMessage.assistant(
        "Thought: After speaking to the players, the NPC Nemura ran away. I'll remove this NPC from the stage now that"
        " she's left the scene.",
        tool_calls=[
            ToolCall.from_function_call(
                FunctionCall(
                    name="npc_stage_event",
                    arguments=json.dumps({"event_type": "REMOVE_FROM_STAGE", "npc": "Nemura"}),
                )
            )
        ],
    ),
    ChatMessage.function("npc_stage_event", "[example return value omitted]"),
    ChatMessage.assistant("Thought: The NPC Nemura has been successfully removed from the stage."),
    # interim
    ChatMessage.user("Okay, okay, so I'll roll for my insight... 22."),
    ChatMessage.assistant(
        "Thought: It seems like a player is making an Insight check. This doesn't reference any specific game"
        " entities yet, so I don't need to do anything. I'll keep listening for points when I can help the"
        " DM."
    ),
    # tool call 2
    ChatMessage.user("...and I want to add a +5 to that with flash"),
    ChatMessage.assistant(
        "Thought: It seems like an artificer is adding a bonus to his Insight check using the Flash of"
        " Genius class feature. I should search for this feature and show it to the DM.",
        tool_calls=[
            ToolCall.from_function_call(
                FunctionCall(
                    name="search_dnd",
                    arguments=json.dumps({"entity_type": "class_feature", "name": "Flash of Genius"}),
                )
            )
        ],
    ),
    ChatMessage.function(
        "search_dnd",
        json.dumps({
            "ClassFeature": "[example return value omitted]",
            "msg": (
                "The ClassFeature's information has been shown to the DM. You do not need to echo any of this"
                " information to the DM."
            ),
        }),
    ),
    ChatMessage.assistant(
        "Thought: The Flash of Genius ability has been shown to the DM. I'll keep listening for additional"
        " points when I can help the DM."
    ),
    # interim
    ChatMessage.user("So 27. Yeah. Do we have..."),
    ChatMessage.assistant(
        "Thought: It seems like the player has calculated the final result of his roll, and another player has"
        " confirmed it. A third player is beginning to ask a question. I should keep listening to see if the players"
        " mention any spells or abilities."
    ),
    ChatMessage.user("[END EXAMPLES] The message above are all examples. The real session begins after this message."),
]
