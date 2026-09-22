/*
 * One match candidate's row in the online-tagging review dialog.
 *
 * Reported in #854: two candidates read "Fight Club 3 #1 (2019)" at 92%
 * and 84% with nothing else on screen, so the choice was blind. The row
 * now carries the cover, a link to the source's page, and what the
 * blended score is made of.
 *
 * The thumbnail contract matters as much as the display: the src is the
 * raw cover url, loaded straight from the CDN under codex's img-src
 * allowance. No proxy route, no encoding, and no crossorigin attribute —
 * that would switch the load to CORS mode, which neither CDN supports.
 *
 * The hover-to-enlarge affordance appears only when the source offers a
 * larger tier. Metron sets coverUrlFull equal to coverUrl on purpose, so
 * the gate is truthiness, not difference.
 */
import { mount } from "@vue/test-utils";
import { beforeAll, describe, expect, test } from "vitest";

import CandidateRow from "@/components/online-tag/candidate-row.vue";
import vuetify from "@/plugins/vuetify";

const COVER_URL =
  "https://comicvine.gamespot.com/a/uploads/scale_avatar/12/1234/5678-9.jpg";
const COVER_URL_FULL =
  "https://comicvine.gamespot.com/a/uploads/original/12/1234/5678-9.jpg";

beforeAll(() => {
  // VOverlay's location strategy reads the bare global; happy-dom has
  // no visual viewport. Same shim as filter-by-select.test.js.
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

function candidate(overrides = {}) {
  const { summary, ...rest } = overrides;
  return {
    source: "comicvine",
    issueId: 42,
    summary: {
      series: "Fight Club 3",
      issue: "1",
      year: 2019,
      publisher: "Dark Horse",
      coverUrl: COVER_URL,
      altSeries: [],
      volume: null,
      ...summary,
    },
    score: 0.92,
    metadataScore: 1,
    coverScore: 0.6,
    coverHashAttempted: true,
    url: "https://comicvine.gamespot.com/issue/4000-1/",
    volumeId: null,
    ...rest,
  };
}

function mountRow(overrides = {}) {
  return mount(CandidateRow, {
    attachTo: document.body,
    props: { candidate: candidate(overrides) },
    global: { plugins: [vuetify] },
  });
}

describe("CandidateRow cover", () => {
  test("loads the raw cover url straight from the CDN", () => {
    const img = mountRow().find("img");

    expect(img.exists()).toBe(true);
    expect(img.attributes("src")).toBe(COVER_URL);
    // No proxy route and no encoding: the policy is the enforcement.
    expect(img.attributes("src")).not.toContain("/api/");
    expect(img.attributes("src")).not.toContain("%3A");
  });

  test("sets the attributes the direct load needs", () => {
    const img = mountRow().find("img");

    expect(img.attributes("loading")).toBe("lazy");
    expect(img.attributes("referrerpolicy")).toBe("no-referrer");
    // crossorigin would switch to CORS mode and fail every thumbnail.
    expect(img.attributes("crossorigin")).toBeUndefined();
  });

  test("renders a placeholder instead when there is no cover", () => {
    const wrapper = mountRow({ summary: { coverUrl: "" } });

    expect(wrapper.find("img").exists()).toBe(false);
    expect(wrapper.find(".candidateCoverPlaceholder").exists()).toBe(true);
  });

  test("falls back to the placeholder when the image fails", async () => {
    const wrapper = mountRow();

    await wrapper.find("img").trigger("error");

    expect(wrapper.find("img").exists()).toBe(false);
    expect(wrapper.find(".candidateCoverPlaceholder").exists()).toBe(true);
  });

  test("the thumbnail is sized by props, not by a scoped class", () => {
    // CoverPopup's popup branch is a VMenu fragment, which a parent's
    // scoped class cannot reach.
    const img = mountRow({ summary: { coverUrlFull: COVER_URL_FULL } }).find(
      "img",
    );

    expect(img.attributes("style")).toContain("width: 48px");
    expect(img.attributes("style")).toContain("height: 72px");
  });
});

describe("CandidateRow hover affordance", () => {
  test("a larger tier makes the cover openable", () => {
    const wrapper = mountRow({ summary: { coverUrlFull: COVER_URL_FULL } });
    const img = wrapper.find("img");

    expect(img.attributes("role")).toBe("button");
    expect(img.attributes("tabindex")).toBe("0");
    expect(img.attributes("aria-label")).toBe("Show full-size cover");
    // The thumbnail is still the thumbnail; only the popup is larger.
    expect(img.attributes("src")).toBe(COVER_URL);
  });

  test("without a larger tier there is no affordance", () => {
    // A prompt cached before the field existed looks exactly like this.
    const wrapper = mountRow();

    expect(wrapper.find('[role="button"]').exists()).toBe(false);
    expect(wrapper.findComponent({ name: "VMenu" }).exists()).toBe(false);
  });

  test("the popup never falls back to the thumbnail url", async () => {
    const wrapper = mountRow({ summary: { coverUrlFull: COVER_URL_FULL } });

    await wrapper.find("img").trigger("click");

    const full = document.querySelector(".v-overlay__content img");
    expect(full.getAttribute("src")).toBe(COVER_URL_FULL);
    wrapper.unmount();
  });
});

describe("CandidateRow score detail", () => {
  test("names both components when the cover was compared", () => {
    const wrapper = mountRow();

    // The reporter's 92 vs 84: the cover comparison is the whole
    // difference, and the row now says so.
    expect(wrapper.find(".candidateScoreDetail").text()).toBe(
      "Match 100% · Cover 60%",
    );
    expect(wrapper.find(".candidateScoreDetail").attributes("title")).toContain(
      "80% metadata",
    );
  });

  test("says the cover was not compared, without repeating the headline", () => {
    const wrapper = mountRow({ coverScore: null, coverHashAttempted: false });

    const detail = wrapper.find(".candidateScoreDetail");
    expect(detail.text()).toBe("Cover not compared");
    expect(detail.attributes("title")).toContain("metadata only");
  });

  test("shows no detail line for a prompt cached before the fields existed", () => {
    const stale = candidate();
    delete stale.metadataScore;
    delete stale.coverScore;
    delete stale.coverHashAttempted;

    const wrapper = mount(CandidateRow, {
      props: { candidate: stale },
      global: { plugins: [vuetify] },
    });

    expect(wrapper.find(".candidateScoreDetail").exists()).toBe(false);
    // The headline percentage still renders.
    expect(wrapper.text()).toContain("92%");
  });
});

describe("CandidateRow details", () => {
  test("links to the source's own page, labelled by source", () => {
    const link = mountRow().find(".candidateSourceLink");

    expect(link.attributes("href")).toBe(
      "https://comicvine.gamespot.com/issue/4000-1/",
    );
    expect(link.attributes("target")).toBe("_blank");
    expect(link.attributes("rel")).toContain("noopener");
    expect(link.text()).toContain("Comic Vine");
  });

  test("omits the link when the candidate carries no url", () => {
    const wrapper = mountRow({ url: "" });

    expect(wrapper.find(".candidateSourceLink").exists()).toBe(false);
  });

  test("shows the volume ordinal when the source supplies one", () => {
    expect(mountRow({ summary: { volume: 2 } }).text()).toContain("Vol. 2");
    expect(mountRow().find(".candidateVolume").exists()).toBe(false);
  });

  test("emits pick", async () => {
    const wrapper = mountRow();

    await wrapper.find("button").trigger("click");

    expect(wrapper.emitted("pick")).toHaveLength(1);
  });
});
