import {
  type BaseEvent,
  type ChatMessage,
  ChatRole,
  type KaniMessage,
  type KaniSpawn,
  type KaniState,
  type KaniStateChange,
  type OutputAudioDelta,
  type RootMessage,
  type SessionMeta,
  type SessionState,
  type StreamDelta,
  type Suggestion,
  type SuggestionEvent,
} from "@/ts/models";
import { base64ToInt16Array } from "@/ts/utils";
import { WavStreamPlayer } from "wavtools";

export class ReDelState {
  rootMessages: ChatMessage[] = [];
  rootKani?: KaniState;
  meta?: SessionMeta;
  kaniMap: Map<string, KaniState> = new Map<string, KaniState>();
  streamMap: Map<string, string> = new Map<string, string>();

  // suggestions & content
  suggestionHistory: Suggestion[] = [];
  pinnedSuggestions: Suggestion[] = [];
  activeSuggestion: Suggestion | null = null;

  player: WavStreamPlayer = new WavStreamPlayer({ sampleRate: 24000 });

  constructor(state?: SessionState) {
    if (state) {
      this.loadSessionState(state);
    }
    this.player.connect();
  }

  public loadSessionState(data: SessionState) {
    this.kaniMap.clear();
    this.meta = data;
    // hydrate the app state
    for (const kani of data.state) {
      this.kaniMap.set(kani.id, kani);
      // also set up the root chat state
      if (kani.parent === null) {
        this.rootKani = kani;
        // ensure it is a copy
        this.rootMessages = [...kani.chat_history];
      }
    }
    this.suggestionHistory = data.suggestion_history;
  }

  // ==== event handlers ====
  public handleEvent(data: BaseEvent) {
    switch (data.type) {
      case "kani_spawn":
        this.onKaniSpawn(data as KaniSpawn);
        break;
      case "kani_state_change":
        this.onKaniStateChange(data as KaniStateChange);
        break;
      case "kani_message":
        this.onKaniMessage(data as KaniMessage);
        break;
      case "root_message":
        this.onRootMessage(data as RootMessage);
        break;
      case "stream_delta":
        this.onStreamDelta(data as StreamDelta);
        break;
      case "output_audio_delta":
        this.onOutputAudioDelta(data as OutputAudioDelta);
        break;
      case "suggestion":
        this.onSuggestion(data as SuggestionEvent);
        break;
      default:
        console.debug("Unknown event:", data);
    }
  }

  onKaniSpawn(data: KaniSpawn) {
    this.kaniMap.set(data.state.id, data.state);
    // set up the root iff it's null
    if (data.state.parent === null) {
      if (!this.rootKani) {
        this.rootKani = data.state;
        this.rootMessages = [...data.state.chat_history];
      }
      return;
    }
    const parent = this.kaniMap.get(data.state.parent);
    if (!parent) {
      console.warn("Got kani_spawn event but parent kani does not exist!");
      return;
    }
    if (parent.children.includes(data.state.id)) return;
    parent.children.push(data.state.id);
  }

  onKaniStateChange(data: KaniStateChange) {
    const kani = this.kaniMap.get(data.id);
    if (!kani) {
      console.warn("Got kani_state_change event for nonexistent kani!");
      return;
    }
    kani.state = data.state;
  }

  onKaniMessage(data: KaniMessage) {
    const kani = this.kaniMap.get(data.id);
    if (!kani) {
      console.warn("Got kani_message event for nonexistent kani!");
      return;
    }
    kani.chat_history.push(data.msg);
    // also reset the stream buffer for that kani
    this.streamMap.delete(data.id);
  }

  onRootMessage(data: RootMessage) {
    this.rootMessages.push(data.msg);
  }

  onStreamDelta(data: StreamDelta) {
    // only for assistant messages
    if (data.role != ChatRole.assistant) return;
    const buf = this.streamMap.get(data.id);
    if (!buf) {
      this.streamMap.set(data.id, data.delta);
      return;
    }
    this.streamMap.set(data.id, buf + data.delta);
  }

  onOutputAudioDelta(data: OutputAudioDelta) {
    this.player.add16BitPCM(base64ToInt16Array(data.delta));
  }

  onSuggestion(data: SuggestionEvent) {
    this.suggestionHistory.push(data.suggestion);
  }
}
