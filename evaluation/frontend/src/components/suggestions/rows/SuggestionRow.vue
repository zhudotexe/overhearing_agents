<script setup lang="ts">
import FoundryAddNPCToStageSuggestionRow from "@/components/suggestions/rows/FoundryAddNPCToStageSuggestionRow.vue";
import FoundryNPCSpeechSuggestionRow from "@/components/suggestions/rows/FoundryNPCSpeechSuggestionRow.vue";
import FoundryRemoveNPCFromStageSuggestionRow from "@/components/suggestions/rows/FoundryRemoveNPCFromStageSuggestionRow.vue";
import GamedataSuggestionRow from "@/components/suggestions/rows/GamedataSuggestionRow.vue";
import ImprovNPCSuggestionRow from "@/components/suggestions/rows/ImprovNPCSuggestionRow.vue";

defineProps<{
  suggestion: any;
}>();
</script>

<template>
  <div class="suggestion-row">
    <GamedataSuggestionRow v-if="suggestion.suggest_type === 'gamedata'" :suggestion="suggestion" />
    <FoundryAddNPCToStageSuggestionRow
      v-else-if="suggestion.suggest_type === 'foundry' && suggestion.action.type === 'add_npc_to_stage'"
      :suggestion="suggestion"
    />
    <FoundryRemoveNPCFromStageSuggestionRow
      v-else-if="suggestion.suggest_type === 'foundry' && suggestion.action.type === 'remove_npc_from_stage'"
      :suggestion="suggestion"
    />
    <FoundryNPCSpeechSuggestionRow
      v-else-if="suggestion.suggest_type === 'foundry' && suggestion.action.type === 'send_npc_speech'"
      :suggestion="suggestion"
    />
    <ImprovNPCSuggestionRow v-else-if="suggestion.suggest_type === 'improvised_npc'" :suggestion="suggestion" />
    <div v-else>{{ suggestion }}</div>
  </div>
</template>

<style scoped lang="scss">
.suggestion-row {
  border-color: rgba(0, 0, 0, 0.3);
  border-style: solid;
  border-width: 0 0 1px 0;
}

.suggestion-row:first-of-type {
  border-top-width: 1px;
}
</style>
