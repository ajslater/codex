/*
 * The shared cover thumbnail that opens its full-size image.
 *
 * Behavior locked in here:
 *   - The affordance exists only when `fullSrc` is truthy. A source with
 *     no larger tier gets a plain image: no menu, no role, no promise.
 *   - Click, Enter and Space all open it, so the popup is reachable
 *     without a mouse — which neither legacy popup was.
 *   - The popup shows `fullSrc`, never the thumbnail again.
 *   - Neither image carries `crossorigin`, and both suppress the
 *     referrer: they load straight from the source CDN.
 */
import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, beforeAll, describe, expect, test } from "vitest";

import CoverPopup from "@/components/cover-popup.vue";
import vuetify from "@/plugins/vuetify";

const THUMB = "https://static.metron.cloud/media/issue/thumb.jpg";
const FULL = "https://comicvine.gamespot.com/a/uploads/original/1/2/3.jpg";

beforeAll(() => {
  /*
   * VOverlay's connected location strategy reads the bare global;
   * happy-dom has no visual viewport, so the menu never positions
   * without this. Same shim as filter-by-select.test.js.
   */
  globalThis.visualViewport ??= {
    width: 1024,
    height: 768,
    offsetLeft: 0,
    offsetTop: 0,
    scale: 1,
    addEventListener() {},
    removeEventListener() {},
  };
});

let wrappers = [];

function mountPopup(props = {}, attrs = {}) {
  const wrapper = mount(CoverPopup, {
    attachTo: document.body,
    props: { thumbSrc: THUMB, fullSrc: FULL, ...props },
    attrs,
    global: { plugins: [vuetify] },
  });
  wrappers.push(wrapper);
  return wrapper;
}

const content = () => document.querySelector(".v-overlay__content");

afterEach(() => {
  for (const wrapper of wrappers) {
    wrapper.unmount();
  }
  wrappers = [];
});

describe("CoverPopup", () => {
  test("renders the thumbnail as the activator", () => {
    const img = mountPopup().find("img");
    expect(img.attributes("src")).toBe(THUMB);
    expect(img.attributes("referrerpolicy")).toBe("no-referrer");
    expect(img.attributes("crossorigin")).toBeUndefined();
    expect(img.attributes("loading")).toBe("lazy");
  });

  test("without a full-size source there is no affordance at all", () => {
    const wrapper = mountPopup({ fullSrc: "" });
    const img = wrapper.find("img");

    expect(img.attributes("src")).toBe(THUMB);
    expect(wrapper.find("[role=button]").exists()).toBe(false);
    expect(wrapper.findComponent({ name: "VMenu" }).exists()).toBe(false);
    expect(img.classes()).not.toContain("coverPopupZoomable");
  });

  test("the activator announces itself as a button", () => {
    const img = mountPopup().find("img");
    expect(img.attributes("role")).toBe("button");
    expect(img.attributes("tabindex")).toBe("0");
    expect(img.attributes("aria-label")).toBe("Show full-size cover");
  });

  test("clicking opens the full-size image", async () => {
    const wrapper = mountPopup();
    await wrapper.find("img").trigger("click");
    await flushPromises();

    const full = content().querySelector("img");
    expect(full.getAttribute("src")).toBe(FULL);
    expect(full.getAttribute("referrerpolicy")).toBe("no-referrer");
    expect(full.hasAttribute("crossorigin")).toBe(false);
  });

  for (const key of ["Enter", " "]) {
    test(`${key === " " ? "Space" : key} opens it too`, async () => {
      const wrapper = mountPopup();
      await wrapper.find("img").trigger("keydown", { key });
      await flushPromises();

      expect(content().querySelector("img").getAttribute("src")).toBe(FULL);
    });
  }

  test("the alt and title reach the thumbnail", () => {
    const img = mountPopup({ alt: "Fight Club 3", title: "Fight Club 3" }).find(
      "img",
    );
    expect(img.attributes("alt")).toBe("Fight Club 3");
    expect(img.attributes("title")).toBe("Fight Club 3");
  });

  test("thumb dimensions are inline, since a parent cannot style a fragment", () => {
    const img = mountPopup({ thumbWidth: "60px", thumbHeight: "90px" }).find(
      "img",
    );
    expect(img.attributes("style")).toContain("width: 60px");
    expect(img.attributes("style")).toContain("height: 90px");
  });

  test("a failed thumbnail is reported to the parent", async () => {
    const wrapper = mountPopup();
    await wrapper.find("img").trigger("error");
    expect(wrapper.emitted("error")).toHaveLength(1);
  });

  test("a parent's style object merges with the size props", () => {
    // The two migrated popups carry their crop and radius this way: a
    // scoped parent class cannot reach a VMenu fragment.
    const img = mountPopup(
      { thumbWidth: "60px", thumbHeight: "90px" },
      { style: { objectFit: "cover", borderRadius: "4px" } },
    ).find("img");
    const style = img.attributes("style");

    expect(style).toContain("object-fit: cover");
    expect(style).toContain("border-radius: 4px");
    expect(style).toContain("width: 60px");
    expect(style).toContain("height: 90px");
  });

  test("the thumb and the popup can show different images", () => {
    // The match dialog's case: a small thumbnail, a large popup. The
    // legacy popups pass the same url for both, which still works.
    const wrapper = mountPopup({ thumbSrc: THUMB, fullSrc: FULL });
    expect(wrapper.find("img").attributes("src")).toBe(THUMB);
  });
});

export default {};
