// from overhearing_agents/kanis/dnd/ai
import type { Suggestion } from "@/ts/models";

export interface GamedataEntity {
  name: string;
  source: string;
  // and some other properties...
}

export interface DNDSuggestEntity extends Suggestion {
  suggest_type: "gamedata";
  entity_type: string;
  entity: GamedataEntity;
  url: string;
  glance_info: string | null;
}
