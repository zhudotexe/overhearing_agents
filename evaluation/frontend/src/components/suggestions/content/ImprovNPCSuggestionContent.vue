<script setup lang="ts">
defineProps<{
  suggestion: any;
}>();
</script>

<template>
  <div>
    <p>The model suggested creating a new improvised NPC with the following parameters:</p>
    <p><strong>Race:</strong> {{ suggestion.race }}</p>
    <p><strong>Background:</strong> {{ suggestion.background }}</p>
    <p><strong>Culture:</strong> {{ suggestion.culture }}</p>
    <p>
      <em>
        Note: If creating a new improvised NPC is helpful at all, regardless of the suggested parameters, select "more
        helpful than not".
      </em>
    </p>
  </div>
</template>

<style scoped lang="scss"></style>
