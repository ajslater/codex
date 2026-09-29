/*
 * The read state bar under a cover.
 *
 * Behavior locked in here:
 *   - Only a finished comic or an all-read collection gets the check cap;
 *     reading, mixed and unread never do.
 *   - The cap never moves the fill: a comic marked read but never opened is
 *     a bare track and its cap, and a finished comic being re-read keeps its
 *     real position.
 */
import { mount } from "@vue/test-utils";
import { describe, expect, test } from "vitest";

import ReadStateBar from "@/components/read-state-bar.vue";

const comic = (finished, progress) => ({
  collection: "comics",
  finished,
  progress,
});
const folder = (finished, progress) => ({
  collection: "folders",
  finished,
  progress,
});

const mountBar = (item) => mount(ReadStateBar, { props: { item } });
const fillWidth = (wrapper) =>
  wrapper.find(".readStateFill").element.style.width;

describe("ReadStateBar", () => {
  test.each([
    ["a finished comic", comic(true, 100)],
    ["a comic marked read but never opened", comic(true, 0)],
    ["an all-read collection", folder(true, 100)],
  ])("caps %s", (_label, item) => {
    const wrapper = mountBar(item);
    expect(wrapper.classes()).toContain("is-finished");
    expect(wrapper.find(".readStateCap").exists()).toBe(true);
  });

  test.each([
    ["a comic being read", comic(false, 62)],
    ["a comic read to the end but not marked", comic(false, 100)],
    ["a mixed collection", folder(null, 40)],
    ["an unread comic", comic(false, 0)],
  ])("does not cap %s", (_label, item) => {
    expect(mountBar(item).find(".readStateCap").exists()).toBe(false);
  });

  test("leaves a marked-read comic's fill at zero", () => {
    const wrapper = mountBar(comic(true, 0));
    expect(fillWidth(wrapper)).toBe("0%");
  });

  test("keeps a re-read comic's real position beside its cap", () => {
    const wrapper = mountBar(comic(true, 30));
    expect(fillWidth(wrapper)).toBe("30%");
  });

  test("paints nothing for an unread comic", () => {
    const wrapper = mountBar(comic(false, 0));
    expect(wrapper.classes()).toContain("is-unread");
    expect(fillWidth(wrapper)).toBe("0%");
  });
});
