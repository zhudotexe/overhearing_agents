<script setup lang="ts">
import type { ChatMessage } from "@/ts/models";
import MessageContent from "@/components/messages/MessageContent.vue";

const props = defineProps<{
  message: ChatMessage;
}>();
</script>

<template>
  <div class="media user-message">
    <figure class="media-left">
      <p class="image is-32x32">
        <img src="@/assets/twemoji/1f9d1-200d-1f4bb.svg" alt="User" />
      </p>
    </figure>
    <div class="media-content">
      <div class="content allow-wrap-anywhere">
        <MessageContent :content="props.message.content" />
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
@import "./messages.scss";

.user-message {
  background: rgba(0, 0, 0, 0.05);
  border-radius: 0.5em;
}
</style>
