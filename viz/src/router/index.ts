import AgentSuggestions from "@/components/interactive/AgentSuggestions.vue";
import SystemVisualization from "@/components/interactive/SystemVisualization.vue";
import SystemVisualizationSave from "@/components/saves/SystemVisualizationSave.vue";
import Todo from "@/components/Todo.vue";
import Home from "@/views/Home.vue";
import Interactive from "@/views/Interactive.vue";
import NotFound from "@/views/NotFound.vue";
import SaveViewer from "@/views/SaveViewer.vue";
import { nextTick } from "vue";
import { createRouter, createWebHistory } from "vue-router";

const DEFAULT_TITLE = "ReDel Web";

const routes = [
  { path: "/", name: "home", component: Home },
  {
    path: "/interactive/:sessionId",
    component: Interactive,
    props: true,
    children: [
      { path: "agent", name: "interactive-agent", component: AgentSuggestions },
      { path: "chat", name: "interactive-chat", component: SystemVisualization },
      { path: "history", name: "interactive-history", component: Todo },
      { path: "settings", name: "interactive-settings", component: Todo },
    ],
  },
  {
    path: "/save/:saveId",
    component: SaveViewer,
    props: true,
    children: [
      { path: "agent", name: "save-agent", component: AgentSuggestions },
      { path: "chat", name: "save-chat", component: SystemVisualizationSave },
      { path: "history", name: "save-history", component: Todo },
    ],
  },
  {
    path: "/:pathMatch(.*)*",
    name: "notFound",
    component: NotFound,
    meta: { title: "404" },
  },
];

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
});

router.afterEach((to) => {
  nextTick(() => {
    document.title = (to.meta.title as string) || DEFAULT_TITLE;
  });
});

export default router;
