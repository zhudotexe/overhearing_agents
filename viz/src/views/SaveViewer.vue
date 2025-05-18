<script setup lang="ts">
import Drawer from "@/components/Drawer.vue";
import { API } from "@/ts/api";
import { type BaseEvent } from "@/ts/models";
import { ReDelState } from "@/ts/state";
import { onMounted, provide, reactive, ref } from "vue";

const props = defineProps<{
  saveId: string;
}>();

const state = reactive<ReDelState>(new ReDelState());
const events = ref<BaseEvent[]>([]);

provide("state", state);

// hooks
onMounted(async () => {
  // get state, update tree
  const _sessionState = await API.getSaveState(props.saveId);
  events.value = await API.getSaveEvents(props.saveId);
  state.loadSessionState(_sessionState);
});
</script>

<!-- similar to Interactive, but the Chat component is replaced with the replay controller -->
<template>
  <div class="main-container">
    <div>
      <Drawer is-viewed-save />
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
