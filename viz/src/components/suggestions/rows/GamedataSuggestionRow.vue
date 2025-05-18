<script setup lang="ts">
import type { DNDSuggestEntity } from "@/ts/dnd";

defineProps<{
  suggestion: DNDSuggestEntity;
}>();
</script>

<template>
  <span>
    <strong>{{ suggestion.entity.name }}</strong>
  </span>
  <span>
    {{ suggestion.glance_info }}
  </span>
  <span class="spacer"></span>
  <span>{{ suggestion.entity.source }} {{ suggestion.entity_type }}</span>
</template>

<style scoped lang="scss"></style>
