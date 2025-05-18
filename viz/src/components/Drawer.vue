<script setup lang="ts">
import DrawerMicController from "@/components/interactive/DrawerMicController.vue";
import { ref } from "vue";

const isOpen = ref<boolean>(true);

defineProps<{
  isViewedSave?: boolean;
}>();
</script>

<template>
  <aside class="menu drawer" :class="{ closed: !isOpen, open: isOpen }">
    <div class="is-clipped">
      <div class="fixed-drawer is-flex is-flex-direction-column">
        <RouterLink class="title" to="/">ReDel</RouterLink>

        <p class="menu-label">Current Session</p>
        <ul class="menu-list">
          <li>
            <RouterLink to="agent" active-class="is-active">Agent Actions</RouterLink>
          </li>
          <li>
            <RouterLink to="chat" active-class="is-active">System Visualization</RouterLink>
          </li>
          <li>
            <RouterLink to="history" active-class="is-active">Event History</RouterLink>
          </li>
          <li>
            <RouterLink to="settings" active-class="is-active">Settings</RouterLink>
          </li>
        </ul>

        <!-- spacer -->
        <div class="is-flex-grow-1"></div>

        <!-- recording utils -->
        <DrawerMicController v-if="!isViewedSave" />
      </div>
    </div>

    <div class="drawer-handle has-text-weight-bold has-text-centered is-unselectable" @click="isOpen = !isOpen">
      {{ isOpen ? "&lt;" : "&gt;" }}
    </div>
  </aside>
</template>

<style scoped lang="scss">
@import "@/global.scss";

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
