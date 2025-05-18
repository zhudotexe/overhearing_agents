<script setup lang="ts">
defineProps<{
  suggestion: any;
}>();
</script>

<template>
  <div class="is-flex">
    <span>
      <strong>Show NPC Speech:</strong>
      {{ suggestion.action.npc_name }}
    </span>
  </div>
</template>

<style scoped lang="scss"></style>
