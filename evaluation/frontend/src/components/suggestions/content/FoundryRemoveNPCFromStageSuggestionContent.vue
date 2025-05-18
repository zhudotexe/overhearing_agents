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
    <p class="mt-auto ml-2">
      <strong>{{ suggestion.action.npc_name }}</strong> will be removed from the stage (assuming that they are currently
      on stage). They will no longer be visible to the players.
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
