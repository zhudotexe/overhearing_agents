<script setup lang="ts">
import AdminDrawer from "@/components/AdminDrawer.vue";
import { useRoute } from "vue-router";

const route = useRoute();
</script>

<template>
  <div class="main-container">
    <div>
      <AdminDrawer />
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
