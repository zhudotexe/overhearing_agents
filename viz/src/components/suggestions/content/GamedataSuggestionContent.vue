<script setup lang="ts">
import type { DNDSuggestEntity } from "@/ts/dnd";

defineProps<{
  suggestion: DNDSuggestEntity;
}>();
</script>

<template>
  <iframe :src="suggestion.url" class="gamedata-iframe"></iframe>
</template>

<style scoped lang="scss">
.gamedata-iframe {
  width: 100%;
  height: calc(100% - 7px); // weird scrolling thing
  border: 0 none;
}
</style>
