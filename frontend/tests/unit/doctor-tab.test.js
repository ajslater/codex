/*
 * Tests for the admin Doctor tab.
 *
 * The tab is what an administrator sees of the doctor report, so behavior
 * locked in here:
 *   - Every status the doctor can report wears the chip colour the
 *     component's own map says, so a status the backend adds without a
 *     colour fails here rather than rendering grey by accident.
 *   - comicbox's rows and codex's own sit under their own headings; a
 *     section header renders once among comicbox's rows, ahead of its
 *     first row, and the rows stay in report order.
 *   - The heading is the verdict, counting the problems in plain words and
 *     coloured by it; the hint carries the host line.
 *   - A fix is a shell command or a setting path, so it renders as code.
 *   - A report already in the store shows at once without a refetch; an
 *     empty store fetches on mount; Re-check always fetches.
 */
import { createTestingPinia } from "@pinia/testing";
import { mount } from "@vue/test-utils";
import { describe, expect, test } from "vitest";

import DoctorTab from "@/components/admin/tabs/doctor-tab.vue";
import { STATUS_COLORS } from "@/components/admin/tabs/doctor-table.vue";
import vuetify from "@/plugins/vuetify";
import { useAdminStore } from "@/stores/admin";

const HEADER = ["comicbox 5.3.0", "Python 3.14.4", "Linux-6.1", "Docker"];
const PDF_FIX = "pip install --force-reinstall 'comicbox-pdffile~=1.0'";

const COMICBOX_RESULTS = [
  {
    section: "Archives",
    name: "CBR",
    status: "OK",
    found: "rarfile 4.5",
    detail: "via unrar · probe read OK · crypto: cryptography",
    fix: "",
  },
  {
    section: "Archives",
    name: "PDF",
    status: "MISCONFIGURED",
    found: "comicbox-pdffile 1.0.0",
    detail: "pdffile fails to import: ImportError(...)",
    fix: PDF_FIX,
  },
  {
    section: "Images (online cover matching)",
    name: "Pillow",
    status: "OK",
    found: "Pillow 12.3.0",
    detail: "jpeg webp png gif · no jxl codec",
    fix: "",
  },
  {
    section: "Config",
    name: "user config",
    status: "OK",
    found: "~/.config/comicbox/config.yaml",
    detail: "parsed",
    fix: "",
  },
  {
    section: "Config",
    name: "unknown key",
    status: "WARN",
    found: "~/.config/comicbox/config.yaml",
    detail: "general.loglevl is ignored",
    fix: "did you mean general.loglevel?",
  },
];
const CODEX_RESULTS = [
  {
    section: "Codex",
    name: "library",
    status: "OK",
    found: "/comics",
    detail: "readable · writable",
    fix: "",
  },
  {
    section: "Codex",
    name: "library",
    status: "WARN",
    found: "/comics-empty",
    detail: "readable · read only · empty: suspect unmounted",
    fix: "mount it, or add comics",
  },
];
const RESULTS = [...COMICBOX_RESULTS, ...CODEX_RESULTS];

const REPORT = {
  header: HEADER,
  comicbox: COMICBOX_RESULTS,
  codex: CODEX_RESULTS,
  problems: 1,
};

// One row per status the component knows, so the chip test enumerates the
// vocabulary from the component instead of keeping a second copy here.
const EVERY_STATUS_REPORT = {
  header: HEADER,
  comicbox: Object.keys(STATUS_COLORS).map((status) => ({
    section: "Statuses",
    name: status.toLowerCase(),
    status,
    found: "",
    detail: "",
    fix: "",
  })),
  codex: [],
  problems: 4,
};

const COLOR_CLASSES = new Set(
  Object.values(STATUS_COLORS)
    .filter(Boolean)
    .map((color) => `text-${color}`),
);

function mountTab(doctor) {
  const pinia = createTestingPinia({ initialState: { admin: { doctor } } });
  const wrapper = mount(DoctorTab, {
    global: { plugins: [pinia, vuetify] },
  });
  return { wrapper, store: useAdminStore() };
}

describe("AdminDoctorTab", () => {
  test("every status wears its chip colour", () => {
    const chips = mountTab(EVERY_STATUS_REPORT).wrapper.findAll(".v-chip");
    expect(chips).toHaveLength(Object.keys(STATUS_COLORS).length);
    for (const chip of chips) {
      const status = chip.text();
      const color = STATUS_COLORS[status];
      const colorClasses = chip
        .classes()
        .filter((cls) => COLOR_CLASSES.has(cls));
      // A tonal chip carries exactly its colour as text-<colour>; an
      // uncoloured one carries none, which is the default grey.
      expect(colorClasses).toStrictEqual(color ? [`text-${color}`] : []);
    }
  });

  test("comicbox and codex rows sit under their own headings", () => {
    const { wrapper } = mountTab(REPORT);
    const headings = wrapper.findAll("h4").map((el) => el.text());
    expect(headings).toStrictEqual(["comicbox", "Codex"]);
    const tables = wrapper.findAll(".doctorTable");
    expect(tables).toHaveLength(2);
    // comicbox's rows are grouped by section, each header once, ahead of
    // its first row.
    const [comicbox, codex] = tables;
    expect(
      comicbox.findAll(".doctorSectionRow").map((row) => row.text()),
    ).toStrictEqual(["Archives", "Images (online cover matching)", "Config"]);
    expect(comicbox.find("tbody tr").classes()).toContain("doctorSectionRow");
    // Codex's rows run flat under their heading: no "Codex" row repeating it.
    expect(codex.findAll(".doctorSectionRow")).toHaveLength(0);
    // Rows stay in report order, repeated names included.
    const names = wrapper.findAll(".doctorName").map((cell) => cell.text());
    expect(names).toStrictEqual(RESULTS.map((result) => result.name));
  });

  test.each([
    { problems: 0, verdict: "No problems", cls: "doctorOk" },
    { problems: 1, verdict: "1 problem", cls: "doctorProblems" },
    { problems: 3, verdict: "3 problems", cls: "doctorProblems" },
  ])(
    "the heading is the verdict for $problems problems",
    ({ problems, verdict, cls }) => {
      const { wrapper } = mountTab({ ...REPORT, problems });
      expect(wrapper.find("h3").text()).toBe(verdict);
      expect(wrapper.find(".adminGroup").classes()).toContain(cls);
    },
  );

  test("the hint is the host line, not the verdict", () => {
    const hint = mountTab(REPORT).wrapper.find(".adminHint").text();
    expect(hint).toBe(HEADER.join(" · "));
  });

  test("renders a fix as code and an empty fix as nothing", () => {
    const { wrapper } = mountTab(REPORT);
    const fixes = wrapper.findAll(".doctorFix");
    expect(fixes).toHaveLength(RESULTS.length);
    const codes = wrapper.findAll(".doctorFix code").map((el) => el.text());
    expect(codes).toStrictEqual([
      PDF_FIX,
      "did you mean general.loglevel?",
      "mount it, or add comics",
    ]);
    expect(fixes[0].find("code").exists()).toBe(false);
    expect(fixes[0].text()).toBe("");
  });

  test("renders found and detail", () => {
    const text = mountTab(REPORT).wrapper.text();
    expect(text).toContain("rarfile 4.5");
    expect(text).toContain("general.loglevl is ignored");
    expect(text).toContain("/comics-empty");
  });

  test("shows Checking… and no table before the report arrives", () => {
    const { wrapper } = mountTab();
    expect(wrapper.find("h3").text()).toBe("Checking…");
    expect(wrapper.find(".adminGroup").classes()).not.toContain("doctorOk");
    expect(wrapper.find(".adminHint").exists()).toBe(false);
    expect(wrapper.find(".doctorTable").exists()).toBe(false);
    expect(wrapper.find("h4").exists()).toBe(false);
    expect(wrapper.find(".v-btn").exists()).toBe(true);
  });

  test("fetches on mount only when the store is empty", () => {
    expect(mountTab(REPORT).store.loadDoctor).not.toHaveBeenCalled();
    expect(mountTab().store.loadDoctor).toHaveBeenCalledTimes(1);
  });

  test("Re-check always fetches", async () => {
    const { wrapper, store } = mountTab(REPORT);
    await wrapper.find(".v-btn").trigger("click");
    expect(store.loadDoctor).toHaveBeenCalledTimes(1);
  });
});
