console.log("PA | Module loaded");

Hooks.on("ready", function() {
	toySocket = new WebSocket("ws://127.0.0.1:8000/api/ws/ordered");
	toySocket.onopen = function() {console.log("PA | Connected to ws");}

	toySocket.addEventListener("message", (event) => {
		const request = JSON.parse(event.data);

		if (request.type === "foundry_action") {
			console.log("PA | Received: ", request.action);
			if (request.action.npc_name) {var npc = game.actors.getName(request.action.npc_name);}
			let outcome = [], response;
			switch (request.action.type) {

				case "list_all_npcs":
					if (!game.folders.getName("npcs")) {
						Folder.create({
							name : "npcs",
							type : "Actor"
						});
						console.log("PA | Created actor folder \"npcs\"");
					}
					response = ({
						"type": "foundry_result",
						"data": game.folders.getName("npcs").contents,
						"action_id": "foo"
					});
					console.log("PA | Returning: ", response);
					toySocket.send(response);
					break;

				case "list_stage_npcs":
					for (let actor of game.actors) {
						if (Theatre.instance.getInsertById("theatre-" + actor.id)) {
							outcome.push(actor.name);
						}
					}
					response = ({
						"type": "foundry_result",
						"data": outcome,
						"action_id": "foo"
					});
					console.log("PA | Returning: ", response);
					toySocket.send(response);
					break;

				case "add_npc_to_stage":
					outcome = npc.name + " already on stage. No action taken";
					if (!Theatre.isActorStaged(npc)) {
						Theatre.addToNavBar(npc);
					}
					if (!Theatre.instance.getInsertById("theatre-" + npc.id)) {
						Theatre.instance.activateInsertById("theatre-" + npc.id);
						outcome = npc.name + " added to stage";
					}
					response = ({
						"type": "foundry_result",
						"data": outcome,
						"action_id": "foo"
					});
					console.log("PA | Returning: ", response);
					toySocket.send(response);
					break;

				case "remove_npc_from_stage":
					outcome = npc.name + " not on stage. No action taken";
					if (Theatre.instance.getInsertById("theatre-" + npc.id)) {
						Theatre.instance.removeInsertById("theatre-" + npc.id);
						outcome = npc.name + " removed from stage";
					}
					response = ({
						"type": "foundry_result",
						"data": outcome,
						"action_id": "foo"
					});
					console.log("PA | Returning: ", response)
					toySocket.send(response);
					break;

				case "send_npc_speech":
					if (!Theatre.isActorStaged(npc)) {
						Theatre.addToNavBar(npc);
					}
					if (!Theatre.instance.getInsertById("theatre-" + npc.id)) {
						Theatre.instance.activateInsertById("theatre-" + npc.id);
					}

					Theatre.instance.speakingAs = npc;
					Theatre.instance.theatreId = "theatre-" + npc.id;
					Theatre.instance.usersTyping[game.users.activeGM.id] = Theatre.instance;
					ChatMessage.create({content : request.action.text});

					response = ({
						"type": "foundry_result",
						"data": npc.name + " said \"" + request.action.text + "\"",
						"action_id": "foo"
					});
					console.log("PA | Returning: ", response);
					toySocket.send(response);
					break;

				default:
			}
		}
	});
});