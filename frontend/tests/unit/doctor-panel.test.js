/*
 * Tests for the Jobs tab's Doctor panel.
 *
 * The panel is what an administrator sees of comicbox's doctor report, so
 * behavior locked in here:
 *   - Every status the doctor can report wears the chip colour the
 *     component's own map says, so a status the backend adds without a
 *     colour fails here rather than rendering grey by accident.
 *   - A section header renders once, ahead of its first row, and the rows
 *     stay in report order.
 *   - The hint carries the platform header and a verdict that counts the
 *     problems in plain words, red when there are any.
 *   - A fix is a shell command or a setting path, so it renders as code.
 *   - A report already in the store shows at once without a refetch; an
 *     empty store fetches on mount; Re-check always fetches.
 */
import { createTestingPinia } from "@pinia/testing";
import { mount } from "@vue/test-utils";
import { describe, expect, test } from "vitest";

import DoctorPanel, {
  STATUS_COLORS,
} from "@/components/admin/tabs/doctor-panel.vue";
import vuetify from "@/plugins/vuetify";
import { useAdminStore } from "@/stores/admin";

const HEADER = ["comicbox 5.3.0", "Python 3.14.4", "Linux-6.1", "Docker"];
const PDF_FIX = "pip install --force-reinstall 'comicbox-pdffile~=1.0'";

const RESULTS = [
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
  {
    section: "Python packages",
    name: "requirements",
    status: "OK",
    found: "",
    detail: "31 satisfied",
    fix: "",
  },
];

const REPORT = { header: HEADER, results: RESULTS, problems: 1 };

// One row per status the component knows, so the chip test enumerates the
// vocabulary from the component instead of keeping a second copy here.
const EVERY_STATUS_REPORT = {
  header: HEADER,
  results: Object.keys(STATUS_COLORS).map((status) => ({
    section: "Statuses",
    name: status.toLowerCase(),
    status,
    found: "",
    detail: "",
    fix: "",
  })),
  problems: 4,
};

const COLOR_CLASSES = new Set(
  Object.values(STATUS_COLORS)
    .filter(Boolean)
    .map((color) => `text-${color}`),
);

function mountPanel(doctor) {
  const pinia = createTestingPinia({ initialState: { admin: { doctor } } });
  const wrapper = mount(DoctorPanel, {
    global: { plugins: [pinia, vuetify] },
  });
  return { wrapper, store: useAdminStore() };
}

describe("AdminDoctorPanel", () => {
  test("every status wears its chip colour", () => {
    const chips = mountPanel(EVERY_STATUS_REPORT).wrapper.findAll(".v-chip");
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

  test("renders each section header once, ahead of its rows", () => {
    const { wrapper } = mountPanel(REPORT);
    const headers = wrapper
      .findAll(".doctorSectionRow")
      .map((row) => row.text());
    expect(headers).toStrictEqual([
      "Archives",
      "Images (online cover matching)",
      "Config",
      "Python packages",
    ]);
    // Rows stay in report order under their headers.
    const names = wrapper.findAll(".doctorName").map((cell) => cell.text());
    expect(names).toStrictEqual(RESULTS.map((result) => result.name));
    // The first row of the table is a header, not a check.
    expect(wrapper.find("tbody tr").classes()).toContain("doctorSectionRow");
  });

  test.each([
    { problems: 0, verdict: "No problems", cls: "doctorVerdictOk" },
    { problems: 1, verdict: "1 problem", cls: "doctorVerdictProblems" },
    { problems: 3, verdict: "3 problems", cls: "doctorVerdictProblems" },
  ])("verdict for $problems problems", ({ problems, verdict, cls }) => {
    const { wrapper } = mountPanel({ ...REPORT, problems });
    const el = wrapper.find(".doctorVerdict");
    expect(el.text()).toBe(verdict);
    expect(el.classes()).toContain(cls);
  });

  test("renders the header line in the hint", () => {
    const hint = mountPanel(REPORT).wrapper.find(".adminHint").text();
    expect(hint).toContain(HEADER.join(" · "));
    expect(hint).toContain("1 problem");
    // The hint does not restate the section title.
    expect(hint).not.toContain("Doctor");
  });

  test("renders a fix as code and an empty fix as nothing", () => {
    const { wrapper } = mountPanel(REPORT);
    const fixes = wrapper.findAll(".doctorFix");
    expect(fixes).toHaveLength(RESULTS.length);
    const codes = wrapper.findAll(".doctorFix code").map((el) => el.text());
    expect(codes).toStrictEqual([PDF_FIX, "did you mean general.loglevel?"]);
    expect(fixes[0].find("code").exists()).toBe(false);
    expect(fixes[0].text()).toBe("");
  });

  test("renders found and detail", () => {
    const text = mountPanel(REPORT).wrapper.text();
    expect(text).toContain("rarfile 4.5");
    expect(text).toContain("general.loglevl is ignored");
  });

  test("shows Checking… and no table before the report arrives", () => {
    const { wrapper } = mountPanel();
    expect(wrapper.find(".adminHint").text()).toBe("Checking…");
    expect(wrapper.find(".doctorTable").exists()).toBe(false);
    expect(wrapper.find(".v-btn").exists()).toBe(true);
  });

  test("fetches on mount only when the store is empty", () => {
    expect(mountPanel(REPORT).store.loadDoctor).not.toHaveBeenCalled();
    expect(mountPanel().store.loadDoctor).toHaveBeenCalledTimes(1);
  });

  test("Re-check always fetches", async () => {
    const { wrapper, store } = mountPanel(REPORT);
    await wrapper.find(".v-btn").trigger("click");
    expect(store.loadDoctor).toHaveBeenCalledTimes(1);
  });
});
