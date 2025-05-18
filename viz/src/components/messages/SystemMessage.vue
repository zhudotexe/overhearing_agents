<script setup lang="ts">
import type { ChatMessage } from "@/ts/models";
import MessageContent from "@/components/messages/MessageContent.vue";

const props = defineProps<{
  message: ChatMessage;
}>();
</script>

<template>
  <div class="system-message">
    <div class="box has-text-centered mx-4 p-2">
      <div class="content allow-wrap-anywhere">
        <MessageContent :content="props.message.content" />
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
@import "./messages.scss";

.system-message {
  padding: 8px;
}
</style>
