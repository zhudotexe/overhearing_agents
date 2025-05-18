// ===== kani models =====
export enum ChatRole {
  system = "system",
  user = "user",
  assistant = "assistant",
  function = "function",
}

export enum RunState {
  stopped = "stopped",
  running = "running",
  waiting = "waiting",
  errored = "errored",
}

export interface FunctionCall {
  name: string;
  arguments: string;
}

export interface ToolCall {
  id: string;
  type: string;
  function: FunctionCall;
}

// message parts
export interface MessagePart {
  __kani_messagepart_type__: string;
}

export const TEXTPART_KEY = "kani.ext.realtime.interop.TextPart";
export const AUDIOPART_KEY = "kani.ext.realtime.interop.AudioPart";

export interface TextPart extends MessagePart {
  __kani_messagepart_type__: typeof TEXTPART_KEY;
  oai_type: string;
  text: string;
}

export interface AudioPart extends MessagePart {
  __kani_messagepart_type__: typeof AUDIOPART_KEY;
  oai_type: string;
  transcript: string | null;
  audio_b64: string | null;
  // only present in saved sessions, relative to the session dir
  audio_file_path?: string;
}

export type MessagePartType = MessagePart | string;
export type MessageContentType = string | MessagePartType[] | null;

// end message parts

export interface ChatMessage {
  role: ChatRole;
  content: MessageContentType;
  name: string | null;
  tool_call_id: string | null;
  tool_calls: ToolCall[] | null;
}

// from overhearing_agents.state
export interface KaniState {
  id: string;
  depth: number;
  parent: string | null;
  children: string[];
  always_included_messages: ChatMessage[];
  chat_history: ChatMessage[];
  state: RunState;
  name: string;
  engine_type: string;
  engine_repr: string;
  functions: AIFunctionState[];
}

export interface AIFunctionState {
  name: string;
  desc: string;
  auto_retry: boolean;
  auto_truncate: number | null;
  after: ChatRole;
  json_schema: object;
}

// from server.models
export interface SessionMeta {
  id: string;
  created: number;
  last_modified: number;
  n_events: number;
}

export interface SaveMeta extends SessionMeta {
  grouping_prefix: string[];
}

export interface SessionState extends SessionMeta {
  state: KaniState[];
  suggestion_history: Suggestion[];
}

export interface Suggestion {
  id: string;
  suggest_type: string;
}

// ===== overhearing_agents events =====
export interface BaseEvent {
  type: string;
}

// ---- server events ----
export interface WSError extends BaseEvent {
  msg: string;
}

export interface KaniSpawn extends BaseEvent {
  state: KaniState;
}

export interface KaniStateChange extends BaseEvent {
  id: string;
  state: RunState;
}

export interface KaniMessage extends BaseEvent {
  id: string;
  msg: ChatMessage;
}

export interface RootMessage extends BaseEvent {
  msg: ChatMessage;
}

export interface StreamDelta extends BaseEvent {
  id: string;
  delta: string;
  role: ChatRole;
}

export interface OutputAudioDelta extends BaseEvent {
  id: string;
  delta: string;
}

export interface SessionMetaUpdate extends BaseEvent {
  title: string;
}

export interface SuggestionEvent extends BaseEvent {
  type: "suggestion";
  suggestion: Suggestion;
}

// ---- client events ----
export interface SendMessage extends BaseEvent {
  type: "send_message";
  content: string;
}

export interface SendAudioMessage extends BaseEvent {
  type: "send_audio_message";
  data_b64: string;
  text_prefix: string | null;
  text_suffix: string | null;
}

export interface InputAudioDelta extends BaseEvent {
  type: "input_audio_delta";
  data_b64: string;
}

export interface ClientEventLog extends BaseEvent {
  type: "log_client_event";
  key: string;
  data: object;
}
