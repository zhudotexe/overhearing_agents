<script setup lang="ts">
defineProps<{
  suggestion: any;
}>();
</script>

<template>
  <div class="is-flex">
    <span>
      <strong>{{ suggestion.entity.name }}</strong>
    </span>
    <span class="ml-2">
      {{ suggestion.glance_info }}
    </span>
    <span class="is-flex-grow-1"></span>
    <span>{{ suggestion.entity.source }} {{ suggestion.entity_type }}</span>
  </div>
</template>

<style scoped lang="scss"></style>
