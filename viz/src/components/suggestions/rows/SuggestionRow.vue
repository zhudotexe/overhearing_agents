<script setup lang="ts">
import GamedataSuggestionRow from "@/components/suggestions/rows/GamedataSuggestionRow.vue";
import type { DNDSuggestEntity } from "@/ts/dnd";
import type { InteractiveClient } from "@/ts/interactive";
import type { Suggestion } from "@/ts/models";
import type { ReDelState } from "@/ts/state";
import { inject } from "vue";

// optionally inject the client - emit logging events when we are in interactive mode but do nothing in replay
const client = inject<InteractiveClient>("client");
const state = inject<ReDelState>("state")!;

defineProps<{
  suggestion: Suggestion;
}>();

function onSuggestionClicked(suggestion: Suggestion) {
  client?.logEvent("suggestion_clicked", { suggestion });
  state.activeSuggestion = suggestion;
}
</script>

<template>
  <div
    class="suggestion-row"
    :class="{ 'is-active': state.activeSuggestion?.id === suggestion.id }"
    @click="onSuggestionClicked(suggestion)"
  >
    <GamedataSuggestionRow v-if="suggestion.suggest_type === 'gamedata'" :suggestion="suggestion as DNDSuggestEntity" />
    <div v-else>{{ suggestion }}</div>
  </div>
</template>

<style scoped lang="scss">
.suggestion-row {
  border-color: rgba(0, 0, 0, 0.3);
  border-style: solid;
  border-width: 0 0 1px 0;
  cursor: pointer;
}

.suggestion-row:first-of-type {
  border-top-width: 1px;
}

.suggestion-row:hover,
.is-active {
  background-color: rgba(0, 0, 0, 0.025);
}
</style>
