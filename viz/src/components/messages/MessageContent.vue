<script setup lang="ts">
import Markdown from "@/components/Markdown.vue";
import { API_BASE } from "@/ts/api";
import { type AudioPart, AUDIOPART_KEY, type MessageContentType, type TextPart, TEXTPART_KEY } from "@/ts/models";
import type { ReDelState } from "@/ts/state";
import { base64ToInt16Array } from "@/ts/utils";
import { inject } from "vue";
import { WaveFile } from "wavefile";

const props = defineProps<{
  content: MessageContentType;
}>();

const state = inject<ReDelState>("state");

function audioDataSrc(audioB64: string): string {
  let wav = new WaveFile();
  const samples = base64ToInt16Array(audioB64);
  wav.fromScratch(1, 24000, "16", samples);
  return wav.toDataURI();
}
</script>

<template>
  <!-- string content: render it as MD -->
  <Markdown v-if="typeof props.content === 'string'" :content="props.content" />
  <!-- list content: render each part -->
  <div v-else-if="props.content?.length">
    <div v-for="part in props.content">
      <!-- string -->
      <Markdown v-if="typeof part === 'string'" :content="part" />
      <!-- textpart -->
      <div v-else-if="part.__kani_messagepart_type__ === TEXTPART_KEY">
        <Markdown :content="(part as TextPart).text" />
      </div>
      <!-- audiopart -->
      <div v-else-if="part.__kani_messagepart_type__ === AUDIOPART_KEY">
        <audio
          controls
          v-if="(part as AudioPart).audio_file_path && state?.meta"
          :src="`${API_BASE}/saves/${state.meta.id}/static/${(part as AudioPart).audio_file_path}`"
        />
        <audio controls v-else-if="(part as AudioPart).audio_b64" :src="audioDataSrc((part as AudioPart).audio_b64!)" />
        <Markdown v-if="(part as AudioPart).transcript" :content="(part as AudioPart).transcript!" />
      </div>
      <!-- unknown -->
      <div v-else>Error: unknown messagepart type {{ part }}</div>
    </div>
  </div>
  <!-- null content: don't render anything -->
</template>

<style scoped lang="scss"></style>
