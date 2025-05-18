<script setup lang="ts">
import Drawer from "@/components/Drawer.vue";
import type { EvalClient } from "@/ts/client";
import { Notifications } from "@/ts/notifications";
import { inject, onMounted } from "vue";
import { useRoute, useRouter } from "vue-router";

const router = useRouter();
const route = useRoute();
const client = inject<EvalClient>("client")!;

// hooks
onMounted(async () => {
  if (!client.isLoggedIn()) {
    Notifications.error("You must log in first.");
    router.push({ name: "login" });
    return;
  }
});
</script>

<template>
  <div class="main-container">
    <div>
      <Drawer />
    </div>
    <div class="is-flex-grow-1 viewport" id="eval-viewport">
      <router-view :key="route.fullPath" />
    </div>
  </div>
</template>

<style scoped lang="scss">
@import "@/global.scss";

.main-container {
  display: flex;
}

.viewport {
  max-height: 100vh;
  overflow: scroll;
}
</style>
