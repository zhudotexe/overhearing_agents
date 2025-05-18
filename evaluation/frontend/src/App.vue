<script setup lang="ts">
import NotificationsOverlay from "@/components/NotificationsOverlay.vue";
import { EvalClient } from "@/ts/client";
import { provide, reactive } from "vue";

// global client bc I'm lazy
const client = reactive(new EvalClient());
provide("client", client);
</script>

<template>
  <router-view />
  <NotificationsOverlay />
</template>

<style lang="scss"></style>
