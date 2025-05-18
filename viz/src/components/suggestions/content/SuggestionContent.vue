<script setup lang="ts">
import GamedataSuggestionContent from "@/components/suggestions/content/GamedataSuggestionContent.vue";
import type { DNDSuggestEntity } from "@/ts/dnd";
import type { Suggestion } from "@/ts/models";

defineProps<{
  suggestion: Suggestion;
}>();
</script>

<template>
  <div class="suggestion-content">
    <GamedataSuggestionContent
      v-if="suggestion.suggest_type === 'gamedata'"
      :suggestion="suggestion as DNDSuggestEntity"
    />
    <div v-else>No content defined: {{ suggestion }}</div>
  </div>
</template>

<style scoped lang="scss">
.suggestion-content {
  height: 100%;
}
</style>
