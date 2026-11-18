/*
 * Tests for the tag edit panel's metadata format checkboxes.
 *
 * Behavior locked in here:
 *   - The formats are a real VCheckboxGroup (the labs component resolves),
 *     one checkbox per derived write format.
 *   - The last checked format is disabled, and the group says why, so the
 *     selection can never become empty.
 *   - Unchecking one of two formats leaves the other selected.
 *   - comicbox's keep is offered beside the formats, explained in its title,
 *     and with a visible line while checked. It is not a format: the last
 *     named format stays disabled with keep checked too.
 */
import { createTestingPinia } from "@pinia/testing";
import { flushPromises, mount } from "@vue/test-utils";
import { describe, expect, test } from "vitest";

import EditPanel from "@/components/metadata/edit-mode/edit-panel.vue";
import vuetify from "@/plugins/vuetify";

const LAST_FORMAT_HINT = "At least one format must be written";
const KEEP_CHECKED_HINT = "Other tag formats are rewritten, not removed";

function formatGroup(wrapper) {
  return wrapper.findComponent({ name: "VCheckboxGroup" });
}

function formatInput(wrapper, value) {
  return formatGroup(wrapper).find(`input[value="${value}"]`);
}

async function mountPanel(formats) {
  const pinia = createTestingPinia({
    initialState: {
      metadata: { md: {} },
      admin: { taggingDefaults: { defaultFormats: formats } },
      browser: { settings: { twentyFourHourTime: false } },
    },
  });
  const wrapper = mount(EditPanel, {
    props: { book: { pk: 1, collection: "comics", ids: [1] } },
    global: { plugins: [pinia, vuetify] },
  });
  await flushPromises();
  return wrapper;
}

describe("EditPanel — format checkboxes", () => {
  test("renders a checkbox group with one box per format", async () => {
    const wrapper = await mountPanel(["COMIC_INFO"]);
    const group = formatGroup(wrapper);
    expect(group.exists()).toBe(true);
    expect(group.find('[role="group"]').attributes("aria-label")).toBe(
      "Metadata formats",
    );
    expect(formatInput(wrapper, "METRON_INFO").exists()).toBe(true);
    expect(formatInput(wrapper, "COMIC_INFO").exists()).toBe(true);
  });

  test("the last checked format is disabled and explained", async () => {
    const wrapper = await mountPanel(["COMIC_INFO"]);
    expect(formatInput(wrapper, "COMIC_INFO").element.disabled).toBe(true);
    expect(formatInput(wrapper, "METRON_INFO").element.disabled).toBe(false);
    expect(formatGroup(wrapper).text()).toContain(LAST_FORMAT_HINT);
  });

  test("unchecking one of two formats leaves the other", async () => {
    const wrapper = await mountPanel(["METRON_INFO", "COMIC_INFO"]);
    expect(formatInput(wrapper, "COMIC_INFO").element.disabled).toBe(false);
    expect(formatGroup(wrapper).text()).not.toContain(LAST_FORMAT_HINT);

    await formatInput(wrapper, "METRON_INFO").setValue(false);

    expect(wrapper.vm.selectedFormats).toEqual(["COMIC_INFO"]);
    expect(formatInput(wrapper, "COMIC_INFO").element.disabled).toBe(true);
    expect(formatGroup(wrapper).text()).toContain(LAST_FORMAT_HINT);
  });

  test("offers keep with its hint", async () => {
    const wrapper = await mountPanel(["COMIC_INFO"]);
    const keep = formatInput(wrapper, "keep");
    expect(keep.exists()).toBe(true);
    expect(keep.element.disabled).toBe(false);
    expect(keep.element.closest(".v-checkbox").textContent).toContain(
      "Keep other formats",
    );
    // Vuetify puts a checkbox's title on its input, as with Rename file.
    for (const fact of ["comicbox.yaml", "PDF", "can't be parsed"]) {
      expect(keep.attributes("title")).toContain(fact);
    }
    expect(formatGroup(wrapper).text()).not.toContain(KEEP_CHECKED_HINT);

    await keep.setValue(true);

    expect(wrapper.vm.selectedFormats).toEqual(["COMIC_INFO", "keep"]);
    expect(formatGroup(wrapper).text()).toContain(KEEP_CHECKED_HINT);
  });

  test("keep does not count as the format a write must name", async () => {
    const wrapper = await mountPanel(["COMIC_INFO", "keep"]);
    expect(formatInput(wrapper, "COMIC_INFO").element.disabled).toBe(true);
    expect(formatInput(wrapper, "keep").element.disabled).toBe(false);
    expect(formatGroup(wrapper).text()).toContain(LAST_FORMAT_HINT);
    expect(wrapper.vm.enabledFormats).toEqual(["COMIC_INFO", "keep"]);
  });
});

export default {};
