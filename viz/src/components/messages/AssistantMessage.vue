<script setup lang="ts">
import AssistantFunctionCall from "@/components/messages/AssistantFunctionCall.vue";
import type { ChatMessage } from "@/ts/models";
import MessageContent from "@/components/messages/MessageContent.vue";

const props = defineProps<{
  message: ChatMessage;
}>();
</script>

<template>
  <div class="media">
    <figure class="media-left">
      <p class="image is-32x32">
        <img src="@/assets/twemoji/1f916.svg" alt="Assistant" />
      </p>
    </figure>
    <div class="media-content">
      <div class="content allow-wrap-anywhere" v-if="message.content">
        <MessageContent :content="props.message.content" />
      </div>
      <!-- function call -->
      <div v-if="message.tool_calls">
        <AssistantFunctionCall :function-call="tc.function" v-for="tc in message.tool_calls" />
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
@import "./messages.scss";
</style>
