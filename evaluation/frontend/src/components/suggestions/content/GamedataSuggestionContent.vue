<script setup lang="ts">
defineProps<{
  suggestion: any;
}>();
</script>

<template>
  <iframe :src="suggestion.url" class="gamedata-iframe"></iframe>
</template>

<style scoped lang="scss">
.gamedata-iframe {
  width: 100%;
  height: 750px;
  border: 0 none;
}
</style>
