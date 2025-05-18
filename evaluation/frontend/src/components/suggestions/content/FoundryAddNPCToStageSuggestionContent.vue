<script setup lang="ts">
defineProps<{
  suggestion: any;
}>();
</script>

<template>
  <div class="is-flex">
    <figure class="image">
      <img class="npc-image" :src="`/npc_imgs/${suggestion.action.npc_name}.png`" />
    </figure>
    <p class="ml-2">
      <strong>{{ suggestion.action.npc_name }}</strong> will be added to the stage and shown to the players.
    </p>
  </div>
</template>

<style scoped lang="scss">
.npc-image {
  width: 128px;
  object-fit: cover;
  object-position: top center;
}
</style>
