<script setup lang="ts">
import type { FunctionCall } from "@/ts/models";
import { ref } from "vue";

const props = defineProps<{
  functionCall: FunctionCall;
}>();

const isOpen = ref(true);
</script>

<template>
  <article class="message is-small is-dark">
    <div class="message-header">
      <p>Called {{ props.functionCall.name }}()...</p>
    </div>
    <div class="message-body" v-if="isOpen">
      <kbd class="allow-wrap-anywhere">{{ functionCall.arguments }}</kbd>
    </div>
  </article>
</template>

<style scoped lang="scss">
@import "./messages.scss";
</style>