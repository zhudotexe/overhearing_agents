<script setup lang="ts">
import { inject, onMounted, ref } from "vue";
import type { KaniState } from "@/ts/models";
import Tree from "@/components/Tree.vue";
import Chat from "@/components/interactive/Chat.vue";
import ChatMessages from "@/components/ChatMessages.vue";
import type { InteractiveClient } from "@/ts/interactive";

const client = inject<InteractiveClient>("client")!;

const introspectedKani = ref<KaniState | null>(null);
const tree = ref<InstanceType<typeof Tree> | null>(null);

// hooks
onMounted(async () => {
  // update tree on messages and state changes
  client.events.addEventListener("kani_message", () => tree.value?.update());
  client.events.addEventListener("kani_state_change", () => tree.value?.updateColors());
  await client.waitForReady();
  tree.value?.update();
});
</script>

<template>
  <div class="main">
    <div class="columns is-gapless h-100">
      <!-- root chat -->
      <div class="column is-flex is-flex-direction-column">
        <!--        &lt;!&ndash; toolbar &ndash;&gt;-->
        <!--        <nav class="level is-mobile toolbar">-->
        <!--          <div class="level-left">-->
        <!--            <div class="level-item">-->
        <!--              <p class="subtitle is-5">{{ client.state.meta?.title || "Untitled Session" }}</p>-->
        <!--            </div>-->
        <!--          </div>-->
        <!--        </nav>-->

        <!-- chat -->
        <div class="left-container chat-container is-flex-grow-1">
          <Chat class="mt-auto" />
        </div>
      </div>
      <!-- viz -->
      <div class="column">
        <div class="right-container is-flex is-flex-direction-column">
          <div class="is-flex-shrink-0">
            <Tree
              @node-clicked="(id) => (introspectedKani = client.state.kaniMap.get(id) ?? null)"
              :selected-id="introspectedKani?.id"
              ref="tree"
            />
          </div>
          <p v-if="introspectedKani" class="has-text-centered">
            Selected: {{ introspectedKani.name }}-{{ introspectedKani.depth }}
          </p>
          <div class="introspection-container">
            <ChatMessages :kani="introspectedKani" v-if="introspectedKani" />
            <p v-else>Click on a node on the tree above to view its state.</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
@import "@/global";

.main {
  height: 100vh;
}

.toolbar {
  margin: 0;
  padding: 0.5rem;
  border-bottom: 1px outset rgba($beige-light, 0.5);
}

.left-container {
  height: 100%;
  padding: 3rem 3rem 2rem 3rem;
  background-color: rgba($beige-light, 0.2);
}

.chat-container {
  min-height: 0;
}

.right-container {
  max-height: 100%;
}

.introspection-container {
  padding: 0 2rem;
  min-height: 0;
  overflow-y: auto;
}
</style>
