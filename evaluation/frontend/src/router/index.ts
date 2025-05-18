import AdminViewSession from "@/components/AdminViewSession.vue";
import AnnotationInterface from "@/components/AnnotationInterface.vue";
import { IS_DEV } from "@/ts/constants";
import Admin from "@/views/Admin.vue";
import Evaluation from "@/views/Evaluation.vue";
import Home from "@/views/Home.vue";
import NotFound from "@/views/NotFound.vue";
import { nextTick } from "vue";
import { createRouter, createWebHistory } from "vue-router";

const DEFAULT_TITLE = "Passive Agents Evaluation";

const routes = [
  { path: "/", name: "login", component: Home },
  {
    path: "/eval",
    name: "evaluation",
    component: Evaluation,
    children: [{ path: ":experimentId", name: "annotate", component: AnnotationInterface, props: true }],
  },
  ...(IS_DEV
    ? [
        {
          path: "/admin",
          name: "admin",
          component: Admin,
          children: [{ path: ":experimentId", name: "admin-view-session", component: AdminViewSession, props: true }],
        },
      ]
    : []),
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
