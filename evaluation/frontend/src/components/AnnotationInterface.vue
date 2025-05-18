<script setup lang="ts">
import SuggestionContent from "@/components/suggestions/content/SuggestionContent.vue";
import SuggestionRow from "@/components/suggestions/rows/SuggestionRow.vue";
import type { EvalClient } from "@/ts/client";
import { inject, onMounted, ref } from "vue";

const props = defineProps<{
  experimentId: string;
}>();
const client = inject<EvalClient>("client")!;

// read-only data
const classifications = ref<any[]>([]);
const suggestion = ref<any>(null);
const transcript = ref<string | null>(null);
const audioDataSrc = ref<string | null>(null);
const contextStart = ref<number | null>(null);
const contextEnd = ref<number | null>(null);

// progress state
const totalToAnnotate = ref(0);
const completedAnnotations = ref(0);

// selections
const selectedTopLabel = ref<any>(null);
const selectedSubLabels = ref([]);
const comments = ref<string>("");
const bulkApplyDuration = ref<number>(99999);
const applyToAll = ref<boolean>(false);
const applyToAllNPC = ref<boolean>(false);
const submitDisabled = ref<boolean>(false);

// annotation
async function refreshWithAnnotation(annotation: any) {
  totalToAnnotate.value = annotation.total;
  completedAnnotations.value = annotation.complete;
  // set the initial context
  suggestion.value = annotation.suggestion;
  const transcriptResp = await client.getExperimentTranscript(
    props.experimentId,
    annotation.context_start,
    annotation.context_end,
  );
  audioDataSrc.value = client.getExperimentAudioSrc(
    props.experimentId,
    annotation.context_start,
    annotation.context_end,
  );
  transcript.value = transcriptResp.transcript;
  contextStart.value = annotation.context_start;
  contextEnd.value = annotation.context_end;
  // clear annotations
  selectedTopLabel.value = null;
  selectedSubLabels.value = [];
  comments.value = "";
  // bulkApplyDuration.value = 99999;
  applyToAll.value = false;
  applyToAllNPC.value = false;
}

async function getMoreContext() {
  if (contextStart.value === 0) return;
  contextStart.value = Math.max(0, (contextStart.value ?? 0) - 10);
  audioDataSrc.value = client.getExperimentAudioSrc(props.experimentId, contextStart.value, contextEnd.value!);
  const transcriptResp = await client.getExperimentTranscript(
    props.experimentId,
    contextStart.value,
    contextEnd.value!,
  );
  transcript.value = transcriptResp.transcript;
}

function selectTopLabel(label: any) {
  selectedTopLabel.value = label;
  selectedSubLabels.value = [];
  applyToAll.value = false;
  applyToAllNPC.value = false;
}

async function submitAndNext() {
  if (!selectedTopLabel.value) return;
  submitDisabled.value = true;
  const nextAnnotation = await client.postAnnotation(
    props.experimentId,
    suggestion.value!.suggestion.id,
    selectedTopLabel.value.score,
    [selectedTopLabel.value.key, ...selectedSubLabels.value],
    contextStart.value ?? 0,
    contextEnd.value ?? 0,
    comments.value,
    applyToAll.value,
    applyToAllNPC.value,
    bulkApplyDuration.value,
  );
  await refreshWithAnnotation(nextAnnotation);
  // re-enable submitting, scroll to top after save
  submitDisabled.value = false;
  document.getElementById("eval-viewport")!.scrollTop = 0;
}

// hooks
onMounted(async () => {
  if (!client.isLoggedIn()) return;
  classifications.value = await client.getClassifications();
  const annotation = await client.getNextIncompleteAnnotation(props.experimentId);
  await refreshWithAnnotation(annotation);
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
              <button class="button" :disabled="contextStart == 0" @click="getMoreContext">Get more context</button>
            </div>
            <div class="level-item">
              Current context: {{ Math.round(((contextEnd ?? 0) - (contextStart ?? 0)) * 100) / 100 }} sec
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- suggestion render -->
    <section class="block">
      <div class="box">
        <h2 class="title">Model Suggestion</h2>
        <div v-if="suggestion?.suggestion">
          <SuggestionRow :suggestion="suggestion.suggestion" />
          <SuggestionContent :suggestion="suggestion.suggestion" />
        </div>
        <!-- <p>{{ suggestion }}</p> -->
      </div>
    </section>

    <hr />

    <section class="block">
      <h2 class="title">Label</h2>
      <!-- top-level label -->
      <div class="buttons">
        <button
          class="button"
          :class="{ 'is-link': selectedTopLabel === label }"
          @click="selectTopLabel(label)"
          v-for="label in classifications"
          :key="label.key"
        >
          <span>{{ label.label }}</span>
        </button>
      </div>
      <!-- sublabels -->
      <template v-if="selectedTopLabel">
        <div class="block">
          <h3 class="subtitle mb-0">Sub-labels</h3>
          <p>Why did you choose this label (if applicable)?</p>
        </div>
        <div class="block">
          <div class="field" v-for="sublabel in selectedTopLabel.sublabels" :key="sublabel.key">
            <div class="control">
              <label class="checkbox">
                <input type="checkbox" :value="sublabel.key" v-model="selectedSubLabels" />
                <span class="ml-1">
                  <strong>{{ sublabel.label }}</strong>
                </span>
                <div v-if="sublabel.examples" class="content pl-4 mt-1">
                  <em>Examples</em>
                  <ul class="mt-1">
                    <li v-for="example in sublabel.examples" :key="example">
                      {{ example }}
                    </li>
                  </ul>
                </div>
              </label>
            </div>
          </div>
        </div>
      </template>
      <!-- comments (optional) -->
      <div class="field">
        <label class="label">Comments (optional)</label>
        <div class="control">
          <textarea class="textarea" placeholder="Your comments here..." v-model="comments"></textarea>
        </div>
      </div>
      <!-- submit -->
      <div class="mb-2" v-if="selectedTopLabel?.score <= -1">
        <h4><strong>Bulk Label Options</strong></h4>
        Bulk apply duration:
        <div class="select is-small">
          <select v-model="bulkApplyDuration">
            <option :value="99999">rest of the session</option>
            <option :value="7200">next 2 hours</option>
            <option :value="3600">next hour</option>
            <option :value="1800">next 30 minutes</option>
            <option :value="600">next 10 minutes</option>
          </select>
        </div>
        <div class="field">
          <div class="control">
            <label class="checkbox">
              <input type="checkbox" v-model="applyToAll" />
              Apply this label to ALL suggestions that are the exact same, for the above duration
              (only use this if you're certain the suggestion won't be correct!)
            </label>
          </div>
        </div>
        <div class="field" v-if="suggestion?.suggestion?.suggest_type === 'foundry'">
          <div class="control">
            <label class="checkbox">
              <input type="checkbox" v-model="applyToAllNPC" />
              Apply this label to ALL suggestions involving this NPC, for the above duration (if this NPC never
              appears during this time)
            </label>
          </div>
        </div>
      </div>
      <button
        class="button is-fullwidth is-success"
        :disabled="!selectedTopLabel || submitDisabled"
        @click="submitAndNext"
      >
        Submit
      </button>
      <!-- progress -->
      <div class="mt-4 progress-wrapper">
        <progress class="progress is-large is-link" :value="completedAnnotations" :max="totalToAnnotate">
          {{ completedAnnotations }} / {{ totalToAnnotate }}
        </progress>
        <p class="progress-value">{{ Math.round((completedAnnotations / totalToAnnotate) * 10000) / 100 }}%</p>
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
