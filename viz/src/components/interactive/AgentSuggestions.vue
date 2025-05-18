<script setup lang="ts">
import SuggestionContent from "@/components/suggestions/content/SuggestionContent.vue";
import SuggestionRow from "@/components/suggestions/rows/SuggestionRow.vue";
import type { ReDelState } from "@/ts/state";
import { computed, inject } from "vue";

const state = inject<ReDelState>("state")!;

const reversedSuggestions = computed(() => [...state.suggestionHistory].reverse());
</script>

<template>
  <div class="main">
    <div class="columns is-gapless h-100">
      <!-- left: suggestion list -->
      <div class="column">
        <div class="left-container">
          <!-- todo: search -->
          <SuggestionRow v-for="suggestion in reversedSuggestions" :suggestion="suggestion" :key="suggestion.id" />
          <div v-if="state.suggestionHistory.length === 0">There are no suggestions yet.</div>
        </div>
      </div>
      <!-- right: pins & content -->
      <div class="column">
        <div class="right-container is-flex is-flex-direction-column">
          <!-- top: pins -->
          <div class="pins-container is-flex-shrink-0">TODO: pins</div>
          <!-- bottom: content -->
          <hr />
          <div class="content-container is-flex-grow-1">
            <SuggestionContent v-if="state.activeSuggestion" :suggestion="state.activeSuggestion" />
            <div v-else>Click on a suggestion to see its content.</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
@import "@/global";

.main {
  height: 100vh;
}

.left-container {
  height: 100%;
  padding: 3rem 3rem 0 3rem;
  background-color: rgba($beige-light, 0.2);
  min-height: 0;
  overflow-y: auto;
}

.right-container {
  height: 100%;
}

.pins-container {
  padding: 2rem 2rem;
  min-height: 0;
  overflow-y: auto;
}

.content-container {
  padding: 0 2rem;
  min-height: 0;
  overflow-y: auto;
}
</style>
