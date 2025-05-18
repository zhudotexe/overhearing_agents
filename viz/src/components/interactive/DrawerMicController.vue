<script setup lang="ts">
import type { InteractiveClient } from "@/ts/interactive";
import { inject } from "vue";

const client = inject<InteractiveClient>("client")!;
</script>

<template>
  <p class="menu-label">Controls</p>
  <!-- TODO: pause/play, wavesurfer -->
  <ul class="menu-list">
    <li>
      <a v-if="!client.micRecorder.recording" @click="client.startRecording">Unmute Microphone</a>
      <a v-else @click="client.pauseRecording">Mute Microphone</a>
    </li>
  </ul>
</template>

<style scoped lang="scss"></style>
