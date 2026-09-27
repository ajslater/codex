/*
 * ReaderSettingsControls' standalone mode, used by the admin Defaults tab.
 *
 * The reader store keeps the last book after the reader unmounts. With a
 * vertical PDF book still there, standalone controls must follow the draft
 * they edit, not the book, and hide the book-only PDF radio and Clear button.
 */
import { createTestingPinia } from "@pinia/testing";
import { mount } from "@vue/test-utils";
import { describe, expect, test } from "vitest";

import ReaderSettingsControls from "@/components/reader/drawer/reader-settings-controls.vue";
import vuetify from "@/plugins/vuetify";

const SETTINGS = Object.freeze({
  fitTo: "W",
  readingDirection: "ltr",
  twoPages: false,
  pageTransition: true,
  cacheBook: false,
});

function mountControls(props) {
  const pinia = createTestingPinia({
    initialState: {
      reader: {
        // A vertical PDF left behind by the last book read.
        books: { current: { pk: 1, fileType: "PDF", settings: {} } },
        bookSettings: { 1: { isVertical: true } },
      },
    },
  });
  return mount(ReaderSettingsControls, {
    props: { settings: SETTINGS, showClear: true, ...props },
    global: { plugins: [pinia, vuetify] },
  });
}

describe("ReaderSettingsControls — standalone", () => {
  test("follows the draft's reading direction, not the book", async () => {
    const wrapper = mountControls({ standalone: true });
    expect(wrapper.vm.isVertical).toBe(false);
    expect(wrapper.vm.disableTwoPages).toBe(false);
    await wrapper.setProps({
      settings: { ...SETTINGS, readingDirection: "btt" },
    });
    expect(wrapper.vm.isVertical).toBe(true);
    expect(wrapper.vm.disableTwoPages).toBe(true);
  });

  test("hides the PDF radio and the Clear button", () => {
    const wrapper = mountControls({ standalone: true });
    expect(wrapper.text()).not.toContain("PDF Rendering");
    expect(wrapper.find("#clearSettingsButton").exists()).toBe(false);
  });

  test("offers every fit and direction choice from the JSON", () => {
    const wrapper = mountControls({ standalone: true });
    expect(wrapper.vm.fitToChoices.map((c) => c.value)).toEqual([
      "S",
      "W",
      "H",
      "O",
    ]);
    expect(wrapper.vm.readingDirectionChoices).toHaveLength(4);
  });

  test("live mode still reads the book", () => {
    const wrapper = mountControls({});
    expect(wrapper.text()).toContain("PDF Rendering");
    expect(wrapper.find("#clearSettingsButton").exists()).toBe(true);
  });
});

export default {};
