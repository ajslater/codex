/*
 * The file's own cover, shown above the match candidates for comparison.
 *
 * Behavior locked in here:
 *   - The thumbnail is Codex's own ACL-checked comic cover, never a
 *     custom collection cover, and the enlarge is page 0 from the reader.
 *   - The enlarge opens through the same CoverPopup box as a candidate's,
 *     so it shows at the same capped size, never as a full-size page.
 *   - A thumb that is not generated yet is probed rather than guessed at
 *     from an <img> error; a failed or vanished comic shows a placeholder
 *     that says why.
 *   - The row restarts only when the cover it points at changes, and a
 *     probe dies with the row.
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
import FileCoverRow from "@/components/online-tag/file-cover-row.vue";
import vuetify from "@/plugins/vuetify";

vi.mock("@/api/v4/cover-probe", async (importOriginal) => ({
  ...(await importOriginal()),
  probeCover: vi.fn(),
}));

const PK = 123;
const MTIME = 1726999999000;
const THUMB_SRC = `/api/v4/covers/comic/${PK}?ts=${MTIME}`;
const FULL_SRC = `/api/v4/comics/${PK}/pages/0?ts=${MTIME}&serve=image`;
const PATH = "/comics/Kapitan/Kapitan 001.cbz";

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

function mountRow(cover, path = PATH) {
  const wrapper = mount(FileCoverRow, {
    attachTo: document.body,
    props: { fileCover: cover, path },
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

async function openEnlarge(wrapper) {
  await wrapper.find("img").trigger("click");
  await flushPromises();
  return document.querySelector(".v-overlay__content .coverPopupBody img");
}

describe("FileCoverRow ready", () => {
  test("shows the comic's own cover and names the file", () => {
    const wrapper = mountRow(fileCover());
    const img = wrapper.find("img");

    expect(img.attributes("src")).toBe(THUMB_SRC);
    expect(img.attributes("src")).not.toContain("covers/custom/");
    expect(img.attributes("role")).toBe("button");
    expect(img.attributes("loading")).toBe("eager");
    expect(img.attributes("style")).toContain("width: 48px");
    expect(img.attributes("style")).toContain("height: 72px");
    expect(wrapper.text()).toContain("This file");
    expect(wrapper.text()).toContain("Kapitan 001.cbz");
    expect(wrapper.find(".fileCoverNote").exists()).toBe(false);
  });

  test("does not probe a cover that already exists", async () => {
    mountRow(fileCover());
    await flushPromises();

    expect(probeCover).not.toHaveBeenCalled();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  test("enlarges page 0 from the reader", async () => {
    const full = await openEnlarge(mountRow(fileCover()));

    expect(full.getAttribute("src")).toBe(FULL_SRC);
  });

  test("enlarges in the candidates' box, at their capped size", async () => {
    /*
     * The cap is CoverPopup's scoped `.coverPopupBody img` rule. Sharing
     * that element and its scope id is what makes page 0 open at the
     * candidates' size; nothing page-specific may resize it.
     */
    const full = await openEnlarge(mountRow(fileCover()));
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
    const wrapper = mountRow(fileCover());

    await wrapper.find("img").trigger("error");

    expect(wrapper.find("img").exists()).toBe(false);
    expect(wrapper.find(".fileCoverPlaceholder").exists()).toBe(true);
    expect(wrapper.text()).toContain("No cover available for this file");
  });
});

describe("FileCoverRow without a cover", () => {
  test("a failed cover shows the placeholder and says so", async () => {
    const wrapper = mountRow(fileCover({ status: "failed" }));
    await flushPromises();

    expect(wrapper.find("img").exists()).toBe(false);
    expect(wrapper.find(".fileCoverPlaceholder").exists()).toBe(true);
    expect(wrapper.text()).toContain("No cover available for this file");
    expect(probeCover).not.toHaveBeenCalled();
  });

  test("a comic gone from the library says so", async () => {
    const wrapper = mountRow(null);
    await flushPromises();

    expect(wrapper.find("img").exists()).toBe(false);
    expect(wrapper.find(".fileCoverPlaceholder").exists()).toBe(true);
    expect(wrapper.text()).toContain("This file is no longer in the library");
    expect(probeCover).not.toHaveBeenCalled();
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

describe("FileCoverRow pending", () => {
  test("probes the thumbnail and says it is loading", () => {
    const probe = deferProbe();
    const wrapper = mountRow(fileCover({ status: "pending" }));

    expect(probe.src).toBe(THUMB_SRC);
    expect(wrapper.find("img").exists()).toBe(false);
    expect(wrapper.text()).toContain("Loading cover…");
  });

  test("shows the cover once the probe finds it", async () => {
    const probe = deferProbe();
    const wrapper = mountRow(fileCover({ status: "pending" }));

    probe.resolve(COVER_PROBE.READY);
    await flushPromises();

    expect(wrapper.find("img").attributes("src")).toBe(THUMB_SRC);
    expect(wrapper.find(".fileCoverNote").exists()).toBe(false);
  });

  test("says it is still generating when the probe gives up", async () => {
    const probe = deferProbe();
    const wrapper = mountRow(fileCover({ status: "pending" }));

    probe.resolve(COVER_PROBE.PENDING);
    await flushPromises();

    expect(wrapper.find("img").exists()).toBe(false);
    expect(wrapper.text()).toContain("Cover is still being generated");
  });

  for (const outcome of [COVER_PROBE.MISSING, COVER_PROBE.ERROR]) {
    test(`a ${outcome} probe shows the placeholder`, async () => {
      const probe = deferProbe();
      const wrapper = mountRow(fileCover({ status: "pending" }));

      probe.resolve(outcome);
      await flushPromises();

      expect(wrapper.find(".fileCoverPlaceholder").exists()).toBe(true);
      expect(wrapper.text()).toContain("No cover available for this file");
    });
  }

  test("unmounting aborts the probe", () => {
    const probe = deferProbe();
    const wrapper = mountRow(fileCover({ status: "pending" }));

    wrapper.unmount();
    wrappers = [];

    expect(probe.signal.aborted).toBe(true);
  });
});

describe("FileCoverRow restarts", () => {
  test("a new mtime points at the new cover", async () => {
    const wrapper = mountRow(fileCover());
    await wrapper.find("img").trigger("error");
    const mtime = MTIME + 1000;

    await wrapper.setProps({ fileCover: fileCover({ mtime }) });

    expect(wrapper.find("img").attributes("src")).toBe(
      `/api/v4/covers/comic/${PK}?ts=${mtime}`,
    );
  });

  test("a reload that reports the cover ready shows it", async () => {
    const probe = deferProbe();
    const wrapper = mountRow(fileCover({ status: "pending" }));
    probe.resolve(COVER_PROBE.PENDING);
    await flushPromises();

    await wrapper.setProps({ fileCover: fileCover({ status: "ready" }) });

    expect(wrapper.find("img").attributes("src")).toBe(THUMB_SRC);
  });

  test("a reload with the same cover does not probe again", async () => {
    const probe = deferProbe();
    const wrapper = mountRow(fileCover({ status: "pending" }));
    probe.resolve(COVER_PROBE.PENDING);
    await flushPromises();

    // Every prompt reload hands over fresh objects.
    await wrapper.setProps({ fileCover: fileCover({ status: "pending" }) });

    expect(probeCover).toHaveBeenCalledTimes(1);
    expect(wrapper.text()).toContain("Cover is still being generated");
  });

  test("a superseded probe is aborted and ignored", async () => {
    const probe = deferProbe();
    const wrapper = mountRow(fileCover({ status: "pending" }));
    const { signal, resolve } = probe;

    await wrapper.setProps({ fileCover: fileCover({ status: "failed" }) });
    resolve(COVER_PROBE.READY);
    await flushPromises();

    expect(signal.aborted).toBe(true);
    expect(wrapper.find("img").exists()).toBe(false);
    expect(wrapper.text()).toContain("No cover available for this file");
  });
});

export default {};
