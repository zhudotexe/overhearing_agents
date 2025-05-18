<script setup lang="ts">
defineProps<{
  suggestion: any;
}>();
</script>

<template>
  <div class="is-flex">
    <span>
      <strong>Remove From Stage:</strong>
      {{ suggestion.action.npc_name }}
    </span>
  </div>
</template>

<style scoped lang="scss"></style>
