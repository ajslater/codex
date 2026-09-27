/*
 * The file's own cover, in its prompt's panel title, to compare with the
 * match candidates' covers.
 *
 * Behavior locked in here:
 *   - The thumbnail is Codex's own ACL-checked comic cover, never a
 *     custom collection cover, and the enlarge is page 0 from the reader.
 *   - The enlarge opens through the same CoverPopup box as a candidate's,
 *     so it shows at the same capped size, never as a full-size page.
 *   - A thumb that is not generated yet is probed rather than guessed at
 *     from an <img> error; a failed or vanished comic shows a placeholder
 *     whose tooltip says why.
 *   - A click on the cover opens the enlarge and stops there, so the panel
 *     title it sits in does not toggle; the placeholder lets clicks through.
 *   - The thumb restarts only when the cover it points at changes, and a
 *     probe dies with the thumb.
 */
import { flushPromises, mount } from "@vue/test-utils";
import {
  afterEach,
  beforeAll,
  beforeEach,
  describe,
  expect,
  test,
  vi,
} from "vitest";

import { COVER_PROBE, probeCover } from "@/api/v4/cover-probe";
import CandidateRow from "@/components/online-tag/candidate-row.vue";
import FileCoverThumb from "@/components/online-tag/file-cover-thumb.vue";
import vuetify from "@/plugins/vuetify";

vi.mock("@/api/v4/cover-probe", async (importOriginal) => ({
  ...(await importOriginal()),
  probeCover: vi.fn(),
}));

const PK = 123;
const MTIME = 1726999999000;
const THUMB_SRC = `/api/v4/covers/comic/${PK}?ts=${MTIME}`;
const FULL_SRC = `/api/v4/comics/${PK}/pages/0?ts=${MTIME}&serve=image`;

beforeAll(() => {
  // VOverlay's location strategy reads the bare global; happy-dom has
  // no visual viewport. Same shim as candidate-row.test.js.
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
let fetchMock;

beforeEach(() => {
  fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  for (const wrapper of wrappers) {
    wrapper.unmount();
  }
  wrappers = [];
  vi.unstubAllGlobals();
  vi.mocked(probeCover).mockReset();
});

function fileCover(overrides = {}) {
  return { pk: PK, mtime: MTIME, status: "ready", ...overrides };
}

function mountThumb(cover) {
  const wrapper = mount(FileCoverThumb, {
    attachTo: document.body,
    props: { fileCover: cover },
    global: { plugins: [vuetify] },
  });
  wrappers.push(wrapper);
  return wrapper;
}

// A probe the test settles by hand, recording the signal it was given.
function deferProbe() {
  const probe = {};
  vi.mocked(probeCover).mockImplementation((src, { signal }) => {
    probe.src = src;
    probe.signal = signal;
    return new Promise((resolve) => {
      probe.resolve = resolve;
    });
  });
  return probe;
}

// The placeholder's tooltip: why there is no cover.
function note(wrapper) {
  return wrapper.find(".fileCoverPlaceholder").attributes("title");
}

async function openEnlarge(wrapper) {
  await wrapper.find("img").trigger("click");
  await flushPromises();
  return document.querySelector(".v-overlay__content .coverPopupBody img");
}

describe("FileCoverThumb ready", () => {
  test("shows the comic's own cover at the candidates' size", () => {
    const wrapper = mountThumb(fileCover());
    const img = wrapper.find("img");

    expect(img.attributes("src")).toBe(THUMB_SRC);
    expect(img.attributes("src")).not.toContain("covers/custom/");
    expect(img.attributes("role")).toBe("button");
    // One per prompt title, so a long queue loads as it scrolls.
    expect(img.attributes("loading")).toBe("lazy");
    expect(img.attributes("style")).toContain("width: 48px");
    expect(img.attributes("style")).toContain("height: 72px");
    expect(wrapper.find(".fileCoverPlaceholder").exists()).toBe(false);
  });

  test("a click on the cover stops at the cover", async () => {
    // The panel title the cover sits in toggles its panel on click.
    const titleClick = vi.fn();
    document.body.addEventListener("click", titleClick);
    try {
      const img = mountThumb(fileCover()).find("img");
      await img.trigger("click"); // opens the enlarge
      await img.trigger("click"); // closes it; Vuetify locks reopening 50 ms
      // Vuetify's activator stops its own clicks, except one inside that
      // lock, which it lets bubble. The cover must stop that one too.
      await img.trigger("click");

      expect(titleClick).not.toHaveBeenCalled();
    } finally {
      document.body.removeEventListener("click", titleClick);
    }
  });

  test("the placeholder lets clicks through to the title", async () => {
    const titleClick = vi.fn();
    document.body.addEventListener("click", titleClick);
    try {
      const wrapper = mountThumb(fileCover({ status: "failed" }));
      await wrapper.find(".fileCoverPlaceholder").trigger("click");

      expect(titleClick).toHaveBeenCalledTimes(1);
    } finally {
      document.body.removeEventListener("click", titleClick);
    }
  });

  test("does not probe a cover that already exists", async () => {
    mountThumb(fileCover());
    await flushPromises();

    expect(probeCover).not.toHaveBeenCalled();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  test("enlarges page 0 from the reader", async () => {
    const full = await openEnlarge(mountThumb(fileCover()));

    expect(full.getAttribute("src")).toBe(FULL_SRC);
  });

  test("enlarges in the candidates' box, at their capped size", async () => {
    /*
     * The cap is CoverPopup's scoped `.coverPopupBody img` rule. Sharing
     * that element and its scope id is what makes page 0 open at the
     * candidates' size; nothing page-specific may resize it.
     */
    const full = await openEnlarge(mountThumb(fileCover()));
    const fileBody = full.parentElement;
    const scopeOf = (el) =>
      el.getAttributeNames().filter((name) => name.startsWith("data-v-"));

    expect(fileBody.classList.contains("coverPopupBody")).toBe(true);
    expect(full.getAttribute("style")).toBeNull();
    expect(full.hasAttribute("width")).toBe(false);
    expect(full.hasAttribute("height")).toBe(false);

    const fileScope = scopeOf(full);
    wrappers.pop().unmount();
    const candidate = mount(CandidateRow, {
      attachTo: document.body,
      props: {
        candidate: {
          source: "comicvine",
          summary: {
            series: "Kapitan",
            coverUrl: "https://example.com/thumb.jpg",
            coverUrlFull: "https://example.com/full.jpg",
          },
          score: 0.9,
        },
      },
      global: { plugins: [vuetify] },
    });
    wrappers.push(candidate);
    const candidateFull = await openEnlarge(candidate);

    expect(candidateFull.getAttribute("src")).toBe(
      "https://example.com/full.jpg",
    );
    expect(fileScope.length).toBeGreaterThan(0);
    expect(scopeOf(candidateFull)).toEqual(fileScope);
  });

  test("falls back to the placeholder when the image fails", async () => {
    const wrapper = mountThumb(fileCover());

    await wrapper.find("img").trigger("error");

    expect(wrapper.find("img").exists()).toBe(false);
    expect(wrapper.find(".fileCoverPlaceholder").exists()).toBe(true);
    expect(note(wrapper)).toBe("No cover available for this file");
  });
});

describe("FileCoverThumb without a cover", () => {
  test("a failed cover shows the placeholder and says so", async () => {
    const wrapper = mountThumb(fileCover({ status: "failed" }));
    await flushPromises();

    expect(wrapper.find("img").exists()).toBe(false);
    expect(wrapper.find(".fileCoverPlaceholder").exists()).toBe(true);
    expect(note(wrapper)).toBe("No cover available for this file");
    expect(probeCover).not.toHaveBeenCalled();
  });

  test("a comic gone from the library says so", async () => {
    const wrapper = mountThumb(null);
    await flushPromises();

    expect(wrapper.find("img").exists()).toBe(false);
    expect(wrapper.find(".fileCoverPlaceholder").exists()).toBe(true);
    expect(note(wrapper)).toBe("This file is no longer in the library");
    expect(probeCover).not.toHaveBeenCalled();
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

describe("FileCoverThumb pending", () => {
  test("probes the thumbnail and says it is loading", () => {
    const probe = deferProbe();
    const wrapper = mountThumb(fileCover({ status: "pending" }));

    expect(probe.src).toBe(THUMB_SRC);
    expect(wrapper.find("img").exists()).toBe(false);
    expect(note(wrapper)).toBe("Loading cover…");
  });

  test("shows the cover once the probe finds it", async () => {
    const probe = deferProbe();
    const wrapper = mountThumb(fileCover({ status: "pending" }));

    probe.resolve(COVER_PROBE.READY);
    await flushPromises();

    expect(wrapper.find("img").attributes("src")).toBe(THUMB_SRC);
    expect(wrapper.find(".fileCoverPlaceholder").exists()).toBe(false);
  });

  test("says it is still generating when the probe gives up", async () => {
    const probe = deferProbe();
    const wrapper = mountThumb(fileCover({ status: "pending" }));

    probe.resolve(COVER_PROBE.PENDING);
    await flushPromises();

    expect(wrapper.find("img").exists()).toBe(false);
    expect(note(wrapper)).toBe("Cover is still being generated");
  });

  for (const outcome of [COVER_PROBE.MISSING, COVER_PROBE.ERROR]) {
    test(`a ${outcome} probe shows the placeholder`, async () => {
      const probe = deferProbe();
      const wrapper = mountThumb(fileCover({ status: "pending" }));

      probe.resolve(outcome);
      await flushPromises();

      expect(wrapper.find(".fileCoverPlaceholder").exists()).toBe(true);
      expect(note(wrapper)).toBe("No cover available for this file");
    });
  }

  test("unmounting aborts the probe", () => {
    const probe = deferProbe();
    const wrapper = mountThumb(fileCover({ status: "pending" }));

    wrapper.unmount();
    wrappers = [];

    expect(probe.signal.aborted).toBe(true);
  });
});

describe("FileCoverThumb restarts", () => {
  test("a new mtime points at the new cover", async () => {
    const wrapper = mountThumb(fileCover());
    await wrapper.find("img").trigger("error");
    const mtime = MTIME + 1000;

    await wrapper.setProps({ fileCover: fileCover({ mtime }) });

    expect(wrapper.find("img").attributes("src")).toBe(
      `/api/v4/covers/comic/${PK}?ts=${mtime}`,
    );
  });

  test("a reload that reports the cover ready shows it", async () => {
    const probe = deferProbe();
    const wrapper = mountThumb(fileCover({ status: "pending" }));
    probe.resolve(COVER_PROBE.PENDING);
    await flushPromises();

    await wrapper.setProps({ fileCover: fileCover({ status: "ready" }) });

    expect(wrapper.find("img").attributes("src")).toBe(THUMB_SRC);
  });

  test("a reload with the same cover does not probe again", async () => {
    const probe = deferProbe();
    const wrapper = mountThumb(fileCover({ status: "pending" }));
    probe.resolve(COVER_PROBE.PENDING);
    await flushPromises();

    // Every prompt reload hands over fresh objects.
    await wrapper.setProps({ fileCover: fileCover({ status: "pending" }) });

    expect(probeCover).toHaveBeenCalledTimes(1);
    expect(note(wrapper)).toBe("Cover is still being generated");
  });

  test("a superseded probe is aborted and ignored", async () => {
    const probe = deferProbe();
    const wrapper = mountThumb(fileCover({ status: "pending" }));
    const { signal, resolve } = probe;

    await wrapper.setProps({ fileCover: fileCover({ status: "failed" }) });
    resolve(COVER_PROBE.READY);
    await flushPromises();

    expect(signal.aborted).toBe(true);
    expect(wrapper.find("img").exists()).toBe(false);
    expect(note(wrapper)).toBe("No cover available for this file");
  });
});

export default {};
