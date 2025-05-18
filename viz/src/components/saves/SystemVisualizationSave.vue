<script setup lang="ts">
import ChatMessages from "@/components/ChatMessages.vue";
import Tree from "@/components/Tree.vue";
import type { KaniState } from "@/ts/models";
import type { ReDelState } from "@/ts/state";
import { inject, onMounted, ref } from "vue";

const state = inject<ReDelState>("state")!;

const introspectedKani = ref<KaniState | null>(null);
const tree = ref<InstanceType<typeof Tree> | null>(null);

onMounted(() => {
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
          <!-- Chat component, but messagebar replaced by replay controls -->
          <div class="is-flex is-flex-direction-column h-100">
            <div class="is-flex-grow-1"></div>
            <!-- chat history -->
            <ChatMessages :kani="state.rootKani!" v-if="state.rootKani" ref="chatMessages" />
            <!-- replay controls -->
            <div class="box">
              <p class="is-size-7">You are viewing a saved session.</p>
            </div>
          </div>
        </div>
      </div>
      <!-- viz -->
      <div class="column">
        <div class="right-container is-flex is-flex-direction-column">
          <div class="is-flex-shrink-0">
            <Tree
              @node-clicked="(id) => (introspectedKani = state.kaniMap.get(id) ?? null)"
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
