<script setup lang="ts">
import { InteractiveClient } from "@/ts/interactive";
import { Notifications } from "@/ts/notifications";
import { onMounted, onUnmounted, provide, reactive } from "vue";
import { useRouter } from "vue-router";
import Drawer from "@/components/Drawer.vue";

const props = defineProps<{
  sessionId: string;
}>();

const router = useRouter();

const client = reactive(new InteractiveClient(props.sessionId));

provide("client", client);
provide("state", client.state);

// hooks
onMounted(async () => {
  // connect ws to backend, get state, update tree
  const resp = await client.getState();
  // if this failed (e.g. user bookmarks a state), notify and redir to save
  if (!resp.success) {
    Notifications.info("This session is no longer active - you are viewing its replay."); // todo instructions to restart it
    router.push({ name: "save-chat", params: { saveId: props.sessionId } });
    return;
  }
  await client.connect();
});
onUnmounted(async () => await client.close());
</script>

<template>
  <div class="main-container">
    <div>
      <Drawer />
    </div>
    <div class="is-flex-grow-1">
      <router-view />
    </div>
  </div>
</template>

<style scoped lang="scss">
@import "@/global.scss";

.main-container {
  display: flex;
}
</style>
