<script setup lang="ts">
import SaveList from "@/components/home/SaveList.vue";
import { API } from "@/ts/api";
import type { SessionMeta } from "@/ts/models";
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";

const router = useRouter();

const interactiveSessions = ref<SessionMeta[]>([]);

async function updateInteractive() {
  interactiveSessions.value = await API.listStatesInteractive();
}

async function startNewInteractive() {
  // request new interactive session, link to interactive
  const newState = await API.createStateInteractive();
  router.push({ name: "interactive-agent", params: { sessionId: newState.id } });
}

// hooks
onMounted(async () => {
  await updateInteractive();
});
</script>

<template>
  <div class="main">
    <section class="hero">
      <div class="hero-body">
        <h1 class="title">Welcome to NAME TBD!</h1>
        <h2 class="subtitle">Tagline here.</h2>
      </div>
    </section>

    <!-- action boxes -->
    <section class="section has-text-centered">
      <h3 class="subtitle">Active Sessions</h3>
      <div class="columns is-mobile is-multiline is-centered">
        <!-- for each active session, option to go to it -->
        <div class="column is-narrow" v-for="interactiveSession in interactiveSessions">
          <RouterLink :to="{ name: 'interactive-agent', params: { sessionId: interactiveSession.id } }">
            <div class="box hover-darken is-clickable">
              <div class="has-text-success">
                <span class="icon">
                  <font-awesome-icon :icon="['fas', 'folder-open']" />
                </span>
              </div>
              <p>{{ interactiveSession.id }}</p>
            </div>
          </RouterLink>
        </div>
        <!-- start a new -->
        <div class="column is-narrow">
          <div class="box hover-darken is-clickable" @click="startNewInteractive">
            <div class="has-text-primary">
              <span class="icon">
                <font-awesome-icon :icon="['fas', 'circle-plus']" />
              </span>
            </div>
            <p>Start a new session</p>
          </div>
        </div>
      </div>
    </section>

    <!-- browse saves -->
    <section class="section">
      <h3 class="subtitle has-text-centered">Previous Sessions</h3>
      <div class="container">
        <SaveList />
      </div>
    </section>
  </div>
</template>

<style scoped>
.hover-darken:hover {
  background-color: rgba(255, 255, 255, 0.7);
}
</style>
