import { createHead, VueHeadMixin } from "@vueuse/head";

export const setupHead = function (app) {
  const head = createHead();
  app.mixin(VueHeadMixin);
  app.use(head);
};

export default {
  setupHead,
};
