<script setup lang="ts">
import FoundryAddNPCToStageSuggestionContent from "@/components/suggestions/content/FoundryAddNPCToStageSuggestionContent.vue";
import FoundryNPCSpeechSuggestionContent from "@/components/suggestions/content/FoundryNPCSpeechSuggestionContent.vue";
import FoundryRemoveNPCFromStageSuggestionContent from "@/components/suggestions/content/FoundryRemoveNPCFromStageSuggestionContent.vue";
import GamedataSuggestionContent from "@/components/suggestions/content/GamedataSuggestionContent.vue";
import ImprovNPCSuggestionContent from "@/components/suggestions/content/ImprovNPCSuggestionContent.vue";

defineProps<{
  suggestion: any;
}>();
</script>

<template>
  <div class="suggestion-content">
    <GamedataSuggestionContent v-if="suggestion.suggest_type === 'gamedata'" :suggestion="suggestion" />
    <FoundryAddNPCToStageSuggestionContent
      v-else-if="suggestion.suggest_type === 'foundry' && suggestion.action.type === 'add_npc_to_stage'"
      :suggestion="suggestion"
    />
    <FoundryRemoveNPCFromStageSuggestionContent
      v-else-if="suggestion.suggest_type === 'foundry' && suggestion.action.type === 'remove_npc_from_stage'"
      :suggestion="suggestion"
    />
    <FoundryNPCSpeechSuggestionContent
      v-else-if="suggestion.suggest_type === 'foundry' && suggestion.action.type === 'send_npc_speech'"
      :suggestion="suggestion"
    />
    <ImprovNPCSuggestionContent v-else-if="suggestion.suggest_type === 'improvised_npc'" :suggestion="suggestion" />
    <div v-else>No content defined: {{ suggestion }}</div>
  </div>
</template>

<style scoped lang="scss"></style>
