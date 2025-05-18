<script setup lang="ts">
import type { EvalClient } from "@/ts/client";
import { inject, ref } from "vue";
import { useRouter } from "vue-router";

const router = useRouter();
const client = inject<EvalClient>("client")!;

const isOpen = ref<boolean>(true);

function logout() {
  client.logout();
  router.push({ name: "login" });
}
</script>

<template>
  <aside class="menu drawer" :class="{ closed: !isOpen, open: isOpen }">
    <div class="is-clipped">
      <div class="fixed-drawer is-flex is-flex-direction-column">
        <h1 class="title">PA Eval</h1>

        <p class="menu-label">Your Assignments</p>
        <ul class="menu-list">
          <li v-for="assignment in client.assignments" :key="assignment.id">
            <RouterLink :to="{ name: 'annotate', params: { experimentId: assignment.id } }" active-class="is-active">
              {{ assignment.name }}
            </RouterLink>
          </li>
        </ul>

        <!-- spacer -->
        <div class="is-flex-grow-1"></div>

        <!-- user info -->
        <p class="menu-label">User Info</p>
        <ul class="menu-list">
          <li>
            <a> Logged in as: {{ client.username }} </a>
          </li>
          <li>
            <a @click="logout"> Log out </a>
          </li>
        </ul>
      </div>
    </div>

    <div class="drawer-handle has-text-weight-bold has-text-centered is-unselectable" @click="isOpen = !isOpen">
      {{ isOpen ? "&lt;" : "&gt;" }}
    </div>
  </aside>
</template>

<style scoped lang="scss">
@import "@/global";

$drawer-width: 16rem;
$drawer-padding: 1rem;
$handle-width: 0.75rem;
$handle-height: 3rem;

.drawer {
  position: relative;
  background-color: rgba($beige-light, 0.4);
  transition: width 300ms;
}

.open {
  width: $drawer-width;
}

.closed {
  width: 0;
}

.drawer-handle {
  position: absolute;
  right: -$handle-width;
  top: 50%;
  width: $handle-width;
  height: $handle-height;
  line-height: $handle-height;
  vertical-align: middle;
  border-radius: 0 4px 4px 0;
  background-color: rgba($beige-light, 0.5);
}

.drawer-handle:hover {
  background-color: rgba($beige-light, 1);
}

.fixed-drawer {
  width: $drawer-width;
  height: 100vh;
  padding: $drawer-padding;
  overflow: hidden;
}
</style>
