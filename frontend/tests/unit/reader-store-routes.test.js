import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it } from "vitest";

import { useReaderStore } from "@/stores/reader";

describe("reader store toRoute", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  it("carries the page in the query, not as a bare param", () => {
    // The reader route is /read/:pk with no :page segment, and pager.vue
    // reads route.query.page. A bare { params: {pk, page} } drops the page,
    // so every flip used to land back on the cover.
    const store = useReaderStore();
    expect(store.toRoute({ pk: 5, page: 3 })).toEqual({
      name: "reader",
      params: { pk: 5 },
      query: { page: 3 },
    });
  });

  it("returns an empty object when there is no route", () => {
    const store = useReaderStore();
    expect(store.toRoute(false)).toEqual({});
    expect(store.toRoute(undefined)).toEqual({});
  });
});
