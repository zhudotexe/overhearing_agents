import json

from kani import ChatMessage, FunctionCall, ToolCall

FEWSHOT_REACT_NOREASON = [
    # tool call 1
    ChatMessage.user("Sending and Augury? Which one were we using? Both?"),
    ChatMessage.assistant(
        "",
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
        "",
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
    ChatMessage.assistant(""),
    # add npc to stage tool call
    ChatMessage.user("As you discuss, you see Nemura slinking into the room..."),
    ChatMessage.assistant(
        "",
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
    ChatMessage.assistant(""),
    # interim
    ChatMessage.user("And when she realizes she's been spotted, she gives kind of like an"),
    ChatMessage.assistant(""),
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
    ChatMessage.assistant(""),
    # npc remove from stage tool call
    ChatMessage.user("And then she runs away like her life depends on it."),
    ChatMessage.assistant(
        "",
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
    ChatMessage.assistant(""),
    # interim
    ChatMessage.user("Okay, okay, so I'll roll for my insight... 22."),
    ChatMessage.assistant(""),
    # tool call 2
    ChatMessage.user("...and I want to add a +5 to that with flash"),
    ChatMessage.assistant(
        "",
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
    ChatMessage.assistant(""),
    # interim
    ChatMessage.user("So 27. Yeah. Do we have..."),
    ChatMessage.assistant(""),
    ChatMessage.user("[END EXAMPLES] The message above are all examples. The real session begins after this message."),
]
