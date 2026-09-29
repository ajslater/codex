/*
 * The admin Defaults tab: explicit Save / Revert per section, the Factory
 * button, the table-column list, and the Save-time catch-up confirmation.
 *
 * Behavior locked in here:
 *   - Nothing saves on change; each section tracks its own changes.
 *   - Revert restores the server values; Factory fills the draft from the
 *     GET's factory block, whose orderBy is "" (the automatic sort).
 *   - The catch-up checkbox starts off. With it on, Save asks first and the
 *     dialog lists only the fields the draft changes, with their summed reach.
 *   - Clearing a collection's columns, or saving an empty picker list,
 *     removes its key so it shows "Factory".
 */
import { createTestingPinia } from "@pinia/testing";
import { mount } from "@vue/test-utils";
import { describe, expect, test } from "vitest";

import DefaultsTab, {
  changedReachKeys,
} from "@/components/admin/tabs/defaults-tab.vue";
import vuetify from "@/plugins/vuetify";
import { useAdminStore } from "@/stores/admin";

const FACTORY = Object.freeze({
  browser: {
    topCollection: "publishers",
    showPublishers: true,
    showImprints: false,
    showSeries: true,
    showVolumes: false,
    orderBy: "",
    orderReverse: false,
    viewMode: "cover",
    twentyFourHourTime: false,
    alwaysShowFilename: false,
    bookmark: "",
    tableColumns: {},
  },
  reader: {
    fitTo: "W",
    readingDirection: "ltr",
    twoPages: false,
    pageTransition: true,
    cacheBook: false,
  },
});

const SERVER = Object.freeze({
  browser: {
    ...FACTORY.browser,
    orderBy: "created_at",
    bookmark: "UNREAD",
    tableColumns: { folders: ["cover", "name"] },
  },
  reader: { ...FACTORY.reader, fitTo: "H" },
  factory: FACTORY,
});

function mountTab() {
  const pinia = createTestingPinia({
    initialState: {
      auth: { user: { id: 1, username: "admin", isStaff: true } },
      admin: {
        settingsDefaults: structuredClone(SERVER),
        flags: [{ key: "FV", on: true }],
      },
    },
  });
  const wrapper = mount(DefaultsTab, {
    global: { plugins: [pinia, vuetify], stubs: { VDialog: true } },
  });
  return { wrapper, vm: wrapper.vm, store: useAdminStore() };
}

describe("AdminDefaultsTab — drafts", () => {
  test("changes are per section and Revert restores the server values", async () => {
    const { vm } = mountTab();
    expect(vm.hasBrowserChanges).toBe(false);
    expect(vm.hasReaderChanges).toBe(false);

    vm.draft.browser.viewMode = "table";
    await vm.$nextTick();
    expect(vm.hasBrowserChanges).toBe(true);
    expect(vm.hasReaderChanges).toBe(false);

    vm.revert("browser");
    await vm.$nextTick();
    expect(vm.hasBrowserChanges).toBe(false);
    expect(vm.draft.browser.viewMode).toBe("cover");
  });

  test("Factory fills the draft, orderBy automatic, and still needs Save", async () => {
    const { wrapper, vm, store } = mountTab();
    const factoryButton = wrapper
      .findAll("button")
      .find((button) => button.text() === "Factory defaults");
    await factoryButton.trigger("click");
    expect(vm.draft.browser).toEqual(FACTORY.browser);
    expect(vm.draft.browser.orderBy).toBe("");
    expect(vm.hasBrowserChanges).toBe(true);
    expect(store.updateSettingsDefaults).not.toHaveBeenCalled();
  });

  test("the top collection's show box is locked", async () => {
    const { vm } = mountTab();
    expect(vm.lockedShowKey).toBe("showPublishers");
    vm.draft.browser.topCollection = "comics";
    await vm.$nextTick();
    expect(vm.lockedShowKey).toBeUndefined();
  });

  test("a locked show box explains itself in the card footer", async () => {
    const { wrapper, vm } = mountTab();
    const hint = () =>
      wrapper
        .findAll(".adminHint")
        .find((node) => node.text().includes("Top Collection"));
    expect(hint().text()).toBe(
      "Publishers is the Top Collection, so it must stay shown. Choose another Top Collection to hide Publishers.",
    );

    vm.draft.browser.topCollection = "series";
    await vm.$nextTick();
    expect(hint().text()).toContain("Series is the Top Collection");

    // Nothing is locked when the top collection has no show box.
    vm.draft.browser.topCollection = "comics";
    await vm.$nextTick();
    expect(hint()).toBeUndefined();
  });

  test("a hidden collection is disabled with a reason", () => {
    const { vm } = mountTab();
    expect(vm.topCollectionItemProps({ value: "imprints" })).toEqual({
      disabled: true,
      subtitle: "Its Show Collections box is off",
    });
    expect(vm.topCollectionItemProps({ value: "series" }).disabled).toBe(false);
  });

  test("clearing columns or saving an empty list removes the key", async () => {
    const { vm } = mountTab();
    expect(vm.tableColumnRows.find((r) => r.collection === "folders")).toEqual(
      expect.objectContaining({ factory: false, summary: "2 columns" }),
    );
    vm.clearColumns("folders");
    expect(vm.draft.browser.tableColumns).toEqual({});

    vm.openPicker("comics");
    vm.onColumnsSaved(["cover", "issue"]);
    expect(vm.draft.browser.tableColumns).toEqual({
      comics: ["cover", "issue"],
    });
    vm.openPicker("comics");
    vm.onColumnsSaved([]);
    expect(vm.draft.browser.tableColumns).toEqual({});
  });

  test("a vertical reading direction turns two pages off", () => {
    const { vm } = mountTab();
    vm.updateReader({ twoPages: true });
    expect(vm.draft.reader.twoPages).toBe(true);
    vm.updateReader({ readingDirection: "ttb" });
    expect(vm.draft.reader.twoPages).toBe(false);
  });
});

describe("AdminDefaultsTab — Save and the catch-up", () => {
  test("the catch-up checkbox starts off and Save puts without it", async () => {
    const { vm, store } = mountTab();
    expect(vm.applyToAnonymous).toEqual({ browser: false, reader: false });
    vm.draft.browser.viewMode = "table";
    await vm.save("browser");
    expect(store.loadSettingsDefaultsReach).not.toHaveBeenCalled();
    expect(store.updateSettingsDefaults).toHaveBeenCalledWith(
      { browser: expect.objectContaining({ viewMode: "table" }) },
      { applyToAnonymous: false },
    );
  });

  test("the dialog sums the reach of the changed fields only", async () => {
    const { vm, store } = mountTab();
    store.loadSettingsDefaultsReach.mockResolvedValue({
      viewMode: 5,
      show: 7,
      orderBy: 100,
      bookmark: 40,
    });
    store.updateSettingsDefaults.mockResolvedValue({ viewMode: 5, show: 7 });
    vm.applyToAnonymous.browser = true;
    vm.draft.browser.viewMode = "table";
    vm.draft.browser.showImprints = true;
    vm.draft.browser.tableColumns = {};
    await vm.save("browser");

    expect(vm.confirm.open).toBe(true);
    expect(vm.confirm.lines.map((line) => line.key)).toEqual([
      "show",
      "viewMode",
    ]);
    expect(vm.confirm.total).toBe(12);
    expect(store.updateSettingsDefaults).not.toHaveBeenCalled();

    await vm.confirmApply();
    expect(store.updateSettingsDefaults).toHaveBeenCalledWith(
      { browser: expect.objectContaining({ viewMode: "table" }) },
      { applyToAnonymous: true },
    );
    // Per Save: the box resets once the save lands.
    expect(vm.applyToAnonymous.browser).toBe(false);
    expect(vm.appliedMessage).toContain("12");
  });

  test("changedReachKeys skips fields with no catch-up", () => {
    const draft = { ...FACTORY.browser, tableColumns: { comics: ["cover"] } };
    expect(changedReachKeys(draft, FACTORY.browser)).toEqual([]);
    expect(
      changedReachKeys({ ...FACTORY.reader, fitTo: "S" }, FACTORY.reader),
    ).toEqual(["fitTo"]);
  });
});

export default {};
