<script setup lang="ts">
import type { EvalClient } from "@/ts/client";
import { computed, inject, onMounted, ref } from "vue";

const props = defineProps<{
  experimentId: string;
}>();
const client = inject<EvalClient>("client")!;

// read-only data
const transcript = ref<string | null>(null);
const audioDataSrc = ref<string | null>(null);
const contextMidpoint = ref<number>(0);

const contextStart = computed(() => Math.max(0, contextMidpoint.value - 10));
const contextEnd = computed(() => contextMidpoint.value + 20);

// annotation
async function refreshData() {
  const transcriptResp = await client.getExperimentTranscript(props.experimentId, contextStart.value, contextEnd.value);
  audioDataSrc.value = client.getExperimentAudioSrc(props.experimentId, contextStart.value, contextEnd.value);
  transcript.value = transcriptResp.transcript;
}

async function setAudioMidpoint(dur: number) {
  contextMidpoint.value = dur;
  await refreshData();
  document.getElementById("eval-viewport")!.scrollTop = 0;
}

// hooks
onMounted(async () => {
  await refreshData();
});
</script>

<template>
  <div class="main container mb-4">
    <section class="block mt-4">
      <div class="box">
        <div class="block">
          <h2 class="title">Context</h2>
          <p><strong>Audio</strong></p>
          <audio controls autoplay :src="audioDataSrc" v-if="audioDataSrc" />
          <p><strong>Transcript</strong></p>
          <pre class="transcript">{{ transcript }}</pre>
          <p>
            <em>
              Note: The transcript often differs from or is slightly misaligned with the audio. It is intended as an
              annotation aid. Make sure to use the audio as the source of truth for your annotations.
            </em>
          </p>
        </div>
        <div class="level">
          <!-- Left side -->
          <div class="level-left">
            <div class="level-item">
              <button class="button" :disabled="contextStart == 0" @click="setAudioMidpoint(contextMidpoint - 10)">
                RWD
              </button>
            </div>
            <div class="level-item">
              <input
                class="input"
                type="number"
                placeholder="0"
                v-model="contextMidpoint"
                @change="setAudioMidpoint(contextMidpoint)"
              />
            </div>
            <div class="level-item">
              <button class="button" @click="setAudioMidpoint(contextMidpoint + 10)">
                FWD
              </button>
            </div>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped lang="scss">
.transcript {
  white-space: pre-line;
}

// from https://stackoverflow.com/questions/50400219/bulma-progress-text-in-middle
.progress-wrapper {
  position: relative;
}

.progress-value {
  position: absolute;
  top: 0;
  left: 50%;
  transform: translateX(-50%);
  font-size: calc(1rem / 1.5);
  line-height: 1rem;
}

.progress.is-large + .progress-value {
  font-size: calc(1.5rem / 1.5);
  line-height: 1.5rem;
}
</style>
