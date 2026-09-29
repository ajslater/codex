/*
 * The reader drawer's keyboard shortcuts write reading directions and fit
 * modes. Every value they send must be one the server accepts.
 */
import { createTestingPinia } from "@pinia/testing";
import { mount } from "@vue/test-utils";
import { describe, expect, test } from "vitest";

import READER_CHOICES from "@/choices/reader-choices.json";
import ReaderSettingsScope from "@/components/reader/drawer/reader-settings-scope.vue";
import vuetify from "@/plugins/vuetify";
import { useReaderStore } from "@/stores/reader";

const DIRECTION_KEYS = Object.freeze(["l", "r", "t", "b"]);
const FIT_TO_KEYS = Object.freeze(["w", "h", "s", "o"]);

function pressKeys(keys) {
  const pinia = createTestingPinia();
  const wrapper = mount(ReaderSettingsScope, {
    global: { plugins: [pinia, vuetify] },
  });
  for (const key of keys) {
    wrapper.vm._keyUpListener({ key, stopPropagation() {} });
  }
  return useReaderStore().updateComicSettings.mock.calls.map(
    ([updates]) => updates,
  );
}

describe("ReaderSettingsScope keyboard shortcuts", () => {
  test("direction keys send every reading direction", () => {
    const sent = pressKeys(DIRECTION_KEYS).map(
      ({ readingDirection }) => readingDirection,
    );
    const choices = READER_CHOICES.READING_DIRECTION.map(({ value }) => value);
    expect(sent).toStrictEqual(["ltr", "rtl", "ttb", "btt"]);
    expect(new Set(sent)).toStrictEqual(new Set(choices));
  });

  test("fit keys send every fit mode", () => {
    const sent = pressKeys(FIT_TO_KEYS).map(({ fitTo }) => fitTo);
    const choices = READER_CHOICES.FIT_TO.map(({ value }) => value);
    expect(new Set(sent)).toStrictEqual(new Set(choices));
  });
});

export default {};
