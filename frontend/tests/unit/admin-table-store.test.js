/*
 * Characterization spec for the admin store's generic table engine:
 * loadTable and loadTables with their per-table sticky cache and response
 * ordering, the forced reloads after row writes and pending-delete revival,
 * the in-place librarian-status diff, and the admin gate in front of all of
 * them.
 *
 * The HTTP layer is mocked. Every TABLES entry keeps its real stateField
 * and each of its request functions becomes a vi.fn(), so the table list
 * and the state each table lands in come from the real API module.
 */
import { flushPromises } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { toRaw, watch } from "vue";

vi.mock(import("@/api/v4/admin"), async (importOriginal) => {
  const actual = await importOriginal();
  const tables = Object.entries(actual.TABLES).map(([name, table]) => [
    name,
    Object.fromEntries(
      Object.entries(table).map(([key, value]) => [
        key,
        typeof value === "function" ? vi.fn() : value,
      ]),
    ),
  ]);
  return {
    ...actual,
    getAllLibrarianStatuses: vi.fn(),
    revivePendingDelete: vi.fn(),
    TABLES: Object.freeze(Object.fromEntries(tables)),
  };
});

import * as API from "@/api/v4/admin";
import { useAdminStore } from "@/stores/admin";
import { useAuthStore } from "@/stores/auth";
import { useCommonStore } from "@/stores/common";

const { TABLES } = API;
const TABLE_NAMES = Object.keys(TABLES);
const NOW = Date.UTC(2026, 0, 1);
const TTL_MS = 5000;
const ONE_YEAR_MS = 365 * 24 * 60 * 60 * 1000;
const PENDING = Symbol("pending");
const TAKEN = "Group with this Name already exists.";

const allMocks = () =>
  [
    ...Object.values(API),
    ...Object.values(TABLES).flatMap((table) => Object.values(table)),
  ].filter((fn) => typeof fn?.mockReset === "function");

const rowsFor = (name, version = 1) => [{ name, pk: 1, version }];

const serve = (name, version = 1) =>
  TABLES[name].getAll.mockResolvedValue({ data: rowsFor(name, version) });

// Hold the next fetch of ``name`` open; the returned function lands it.
const deferGetAll = (name) => {
  const response = Promise.withResolvers();
  TABLES[name].getAll.mockReturnValueOnce(response.promise);
  return (version) => response.resolve({ data: rowsFor(name, version) });
};

const serveAll = (version = 1) => {
  for (const name of TABLE_NAMES) serve(name, version);
};

const clearGetAllCalls = () => {
  for (const table of Object.values(TABLES)) table.getAll.mockClear();
};

// Every table's fetch count, keyed by table name.
const getAllCalls = () =>
  Object.fromEntries(
    Object.entries(TABLES).map(([name, table]) => [
      name,
      table.getAll.mock.calls.length,
    ]),
  );

// The fetch counts when only ``names`` were fetched, once each.
const fetchedOnly = (...names) =>
  Object.fromEntries(
    TABLE_NAMES.map((name) => [name, names.includes(name) ? 1 : 0]),
  );

// Every table's state field, keyed by table name.
const tableState = (store) =>
  Object.fromEntries(
    Object.entries(TABLES).map(([name, table]) => [
      name,
      store[table.stateField],
    ]),
  );

const loadStatuses = async (store, statuses) => {
  API.getAllLibrarianStatuses.mockResolvedValue({ data: statuses });
  await store.loadAllStatuses();
};

const advance = (ms) => vi.setSystemTime(Date.now() + ms);

const isSettled = async (promise) =>
  (await Promise.race([promise, PENDING])) !== PENDING;

const takenNameError = () => ({
  response: { data: { errors: { name: [TAKEN] } }, status: 400 },
});

const status = (statusType, complete = 0) => ({
  complete,
  statusType,
  subtitle: "",
  total: 10,
});

function adminStore() {
  useAuthStore().user = { id: 1, isStaff: true, username: "admin" };
  return useAdminStore();
}

beforeEach(() => {
  setActivePinia(createPinia());
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(NOW);
  for (const fn of allMocks()) fn.mockReset();
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe("loadTable response shapes", () => {
  it.each([
    ["a bare array", rowsFor("User")],
    [
      "a cursor page",
      { count: 1, next: null, previous: null, results: rowsFor("User") },
    ],
    [
      "a cursor page without a count",
      {
        next: "/admin/users?cursor=x",
        previous: null,
        results: rowsFor("User"),
      },
    ],
  ])("stores the rows of %s and stamps the table", async (_label, body) => {
    TABLES.User.getAll.mockResolvedValue({ data: body });
    const store = adminStore();

    await store.loadTable("User");

    expect(store.users).toStrictEqual(rowsFor("User"));
    expect(store.timestamps.User).toBe(NOW);
    // One request per load: the next cursor is never followed.
    expect(TABLES.User.getAll).toHaveBeenCalledOnce();
  });

  it("stores an empty page as no rows", async () => {
    const store = adminStore();
    store.users = rowsFor("User");
    TABLES.User.getAll.mockResolvedValue({ data: { results: [] } });

    await store.loadTable("User");

    expect(store.users).toStrictEqual([]);
  });

  it.each([
    ["an empty object", {}],
    ["null", null],
    ["no body", undefined],
    ["a string", "rows"],
    ["non-array results", { results: { pk: 1 } }],
  ])(
    "warns, keeps the rows and stamps nothing for %s",
    async (_label, body) => {
      const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
      const store = adminStore();
      store.users = rowsFor("User");
      TABLES.User.getAll.mockResolvedValue({ data: body });

      await store.loadTable("User");

      expect(warn).toHaveBeenCalledExactlyOnceWith(
        "users",
        "response shape unrecognized",
      );
      expect(store.users).toStrictEqual(rowsFor("User"));
      expect(store.timestamps).not.toHaveProperty("User");

      // Nothing was cached, so the next read goes back to the server.
      await store.loadTable("User");
      expect(TABLES.User.getAll).toHaveBeenCalledTimes(2);
    },
  );

  it("warns and keeps the old rows and stamp when the request fails", async () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    const failure = new Error("offline");
    serve("User");
    const store = adminStore();
    await store.loadTable("User");
    advance(TTL_MS);
    TABLES.User.getAll.mockRejectedValue(failure);

    await store.loadTable("User");

    expect(warn).toHaveBeenCalledExactlyOnceWith(failure);
    expect(store.users).toStrictEqual(rowsFor("User"));
    expect(store.timestamps.User).toBe(NOW);
  });
});

describe("loadTable sticky cache", () => {
  it("serves a read inside the TTL from state", async () => {
    serve("User");
    const store = adminStore();
    await store.loadTable("User");
    advance(TTL_MS - 1);
    serve("User", 2);

    await store.loadTable("User");

    expect(TABLES.User.getAll).toHaveBeenCalledOnce();
    expect(store.users).toStrictEqual(rowsFor("User"));
    expect(store.timestamps.User).toBe(NOW);
  });

  it("refetches and restamps once the TTL has passed", async () => {
    serve("User");
    const store = adminStore();
    await store.loadTable("User");
    advance(TTL_MS);
    serve("User", 2);

    await store.loadTable("User");

    expect(TABLES.User.getAll).toHaveBeenCalledTimes(2);
    expect(store.users).toStrictEqual(rowsFor("User", 2));
    expect(store.timestamps.User).toBe(NOW + TTL_MS);
  });

  it("refetches inside the TTL when forced", async () => {
    serve("User");
    const store = adminStore();
    await store.loadTable("User");
    advance(1);
    serve("User", 2);

    await store.loadTable("User", { force: true });

    expect(TABLES.User.getAll).toHaveBeenCalledTimes(2);
    expect(store.users).toStrictEqual(rowsFor("User", 2));
    expect(store.timestamps.User).toBe(NOW + 1);
  });

  it("keeps a separate clock for each table", async () => {
    serveAll();
    const store = adminStore();
    await store.loadTable("User");
    advance(TTL_MS - 1000);
    await store.loadTable("Group");
    advance(1000);

    await store.loadTables(["User", "Group"]);

    // User is TTL_MS old and refetches; Group is 1 s old and does not.
    expect(TABLES.User.getAll).toHaveBeenCalledTimes(2);
    expect(TABLES.Group.getAll).toHaveBeenCalledOnce();
  });

  it.each(TABLE_NAMES.filter((name) => name !== "AgeRatingMetron"))(
    "expires %s after the dynamic TTL",
    async (name) => {
      serve(name);
      const store = adminStore();
      await store.loadTable(name);
      advance(TTL_MS);

      await store.loadTable(name);

      expect(TABLES[name].getAll).toHaveBeenCalledTimes(2);
    },
  );

  it("never expires AgeRatingMetron unless forced", async () => {
    serve("AgeRatingMetron");
    const store = adminStore();
    await store.loadTable("AgeRatingMetron");
    advance(ONE_YEAR_MS);

    await store.loadTable("AgeRatingMetron");
    expect(TABLES.AgeRatingMetron.getAll).toHaveBeenCalledOnce();

    await store.loadTable("AgeRatingMetron", { force: true });
    expect(TABLES.AgeRatingMetron.getAll).toHaveBeenCalledTimes(2);
  });
});

describe("loadTable response order", () => {
  const SAVED_AT = NOW + 1000;

  it("drops a slow read that lands after a later forced reload", async () => {
    const landA = deferGetAll("Library");
    const landB = deferGetAll("Library");
    const store = adminStore();
    // A tab mounts with an empty cache; its read A goes out and stalls.
    const readA = store.loadTable("Library");
    // A save force-reloads the table; read B goes out and lands first.
    vi.setSystemTime(SAVED_AT);
    const readB = store.loadTable("Library", { force: true });
    landB(2);
    await readB;
    advance(500);
    landA(1);
    await readA;

    expect(store.libraries).toStrictEqual(rowsFor("Library", 2));
    expect(store.timestamps.Library).toBe(SAVED_AT);

    // An unforced read inside B's TTL is served B's rows from state.
    vi.setSystemTime(SAVED_AT + TTL_MS - 1);
    await store.loadTable("Library");

    expect(TABLES.Library.getAll).toHaveBeenCalledTimes(2);
    expect(store.libraries).toStrictEqual(rowsFor("Library", 2));
  });

  it("lands both reads when they arrive in order", async () => {
    const landA = deferGetAll("Library");
    const landB = deferGetAll("Library");
    const store = adminStore();
    const readA = store.loadTable("Library");
    vi.setSystemTime(SAVED_AT);
    const readB = store.loadTable("Library", { force: true });

    landA(1);
    await readA;
    expect(store.libraries).toStrictEqual(rowsFor("Library", 1));
    expect(store.timestamps.Library).toBe(NOW);

    landB(2);
    await readB;
    expect(store.libraries).toStrictEqual(rowsFor("Library", 2));
    expect(store.timestamps.Library).toBe(SAVED_AT);
  });

  it("still lands an earlier read when the later one fails", async () => {
    vi.spyOn(console, "warn").mockImplementation(() => {});
    const landA = deferGetAll("Library");
    TABLES.Library.getAll.mockRejectedValueOnce(new Error("offline"));
    const store = adminStore();
    const readA = store.loadTable("Library");
    await store.loadTable("Library", { force: true });

    landA(1);
    await readA;

    expect(store.libraries).toStrictEqual(rowsFor("Library", 1));
    expect(store.timestamps.Library).toBe(NOW);
  });

  it("stamps the time the read went out, not when it landed", async () => {
    const land = deferGetAll("User");
    const store = adminStore();
    const read = store.loadTable("User");
    advance(3000);
    land(1);
    await read;

    expect(store.timestamps.User).toBe(NOW);

    // The TTL runs from the request, so it is over TTL_MS after it went out.
    vi.setSystemTime(NOW + TTL_MS);
    serve("User", 2);
    await store.loadTable("User");

    expect(TABLES.User.getAll).toHaveBeenCalledTimes(2);
    expect(store.users).toStrictEqual(rowsFor("User", 2));
  });
});

describe("loadTables", () => {
  it("loads every named table into its own state field", async () => {
    serveAll();
    const store = adminStore();

    await store.loadTables(TABLE_NAMES);

    expect(getAllCalls()).toStrictEqual(fetchedOnly(...TABLE_NAMES));
    expect(tableState(store)).toStrictEqual(
      Object.fromEntries(TABLE_NAMES.map((name) => [name, rowsFor(name)])),
    );
    expect(store.timestamps).toStrictEqual(
      Object.fromEntries(TABLE_NAMES.map((name) => [name, NOW])),
    );
  });

  it("loads only the tables it names", async () => {
    serveAll();
    const store = adminStore();

    await store.loadTables(["Group", "Library"]);

    expect(getAllCalls()).toStrictEqual(fetchedOnly("Group", "Library"));
    expect(store.users).toStrictEqual([]);
  });

  it("passes force through to every table", async () => {
    serveAll();
    const store = adminStore();
    await store.loadTables(["User", "AgeRatingMetron"]);
    serveAll(2);

    await store.loadTables(["User", "AgeRatingMetron"], { force: true });

    expect(TABLES.User.getAll).toHaveBeenCalledTimes(2);
    expect(TABLES.AgeRatingMetron.getAll).toHaveBeenCalledTimes(2);
    expect(store.users).toStrictEqual(rowsFor("User", 2));
    expect(store.ageRatingMetrons).toStrictEqual(rowsFor("AgeRatingMetron", 2));
  });

  it("resolves only after every table has landed", async () => {
    serve("User");
    const library = Promise.withResolvers();
    TABLES.Library.getAll.mockReturnValue(library.promise);
    const store = adminStore();

    const loading = store.loadTables(["User", "Library"]);
    await flushPromises();

    expect(store.users).toStrictEqual(rowsFor("User"));
    expect(await isSettled(loading)).toBe(false);

    library.resolve({ data: rowsFor("Library") });
    await loading;
    expect(store.libraries).toStrictEqual(rowsFor("Library"));
  });
});

describe("row writes force-reload their own table", () => {
  it.each([
    ["createRow", "create", [{ name: "g" }]],
    ["updateRow", "update", [3, { name: "g" }]],
    ["deleteRow", "destroy", [3]],
  ])(
    "%s writes, then reloads Group inside the TTL",
    async (action, method, apiArgs) => {
      serveAll();
      const store = adminStore();
      await store.loadTables(TABLE_NAMES);
      clearGetAllCalls();
      serve("Group", 2);
      TABLES.Group[method].mockResolvedValue({ data: {} });
      advance(1);

      await store[action]("Group", ...apiArgs);

      expect(TABLES.Group[method]).toHaveBeenCalledExactlyOnceWith(...apiArgs);
      expect(getAllCalls()).toStrictEqual(fetchedOnly("Group"));
      expect(TABLES.Group[method].mock.invocationCallOrder[0]).toBeLessThan(
        TABLES.Group.getAll.mock.invocationCallOrder[0],
      );
      expect(store.groups).toStrictEqual(rowsFor("Group", 2));
      expect(store.timestamps.Group).toBe(NOW + 1);
    },
  );

  it.each([
    ["createRow", "create", [{ name: "g" }]],
    ["updateRow", "update", [3, { name: "g" }]],
    ["deleteRow", "destroy", [3]],
  ])(
    "%s reloads nothing when the write is rejected",
    async (action, method, apiArgs) => {
      serve("Group");
      const store = adminStore();
      await store.loadTable("Group");
      clearGetAllCalls();
      TABLES.Group[method].mockRejectedValue(takenNameError());

      await store[action]("Group", ...apiArgs);

      expect(TABLES.Group.getAll).not.toHaveBeenCalled();
      expect(store.groups).toStrictEqual(rowsFor("Group"));
      expect(useCommonStore().form.fieldErrors).toStrictEqual({
        name: [TAKEN],
      });
    },
  );
});

describe("revivePendingDelete", () => {
  it("revives the row, then force-reloads PendingDelete and Library", async () => {
    serveAll();
    const store = adminStore();
    await store.loadTables(TABLE_NAMES);
    clearGetAllCalls();
    serveAll(2);
    API.revivePendingDelete.mockResolvedValue({ data: {} });

    await store.revivePendingDelete("comics", 7);

    expect(API.revivePendingDelete).toHaveBeenCalledExactlyOnceWith(
      "comics",
      7,
    );
    expect(getAllCalls()).toStrictEqual(
      fetchedOnly("PendingDelete", "Library"),
    );
    expect(store.pendingDeletes).toStrictEqual(rowsFor("PendingDelete", 2));
    expect(store.libraries).toStrictEqual(rowsFor("Library", 2));
  });

  it("reloads nothing when the revive is rejected", async () => {
    const store = adminStore();
    API.revivePendingDelete.mockRejectedValue(takenNameError());

    await store.revivePendingDelete("comics", 7);

    expect(getAllCalls()).toStrictEqual(fetchedOnly());
    expect(useCommonStore().form.fieldErrors).toStrictEqual({ name: [TAKEN] });
  });
});

describe("librarian status diff", () => {
  const FIRST = Object.freeze([status("CCC"), status("ICC"), status("IFQ")]);

  it("keys the statuses by statusType", async () => {
    const store = adminStore();

    await loadStatuses(store, FIRST);

    expect(store.allLibrarianStatuses).toStrictEqual({
      CCC: status("CCC"),
      ICC: status("ICC"),
      IFQ: status("IFQ"),
    });
  });

  it("patches the map in place, keeping unchanged rows", async () => {
    const store = adminStore();
    await loadStatuses(store, FIRST);
    const map = toRaw(store.allLibrarianStatuses);
    const kept = toRaw(store.allLibrarianStatuses.CCC);
    const changed = toRaw(store.allLibrarianStatuses.ICC);

    // CCC arrives as an equal copy, ICC moves, IFQ is gone, CRC is new.
    await loadStatuses(store, [status("CCC"), status("ICC", 4), status("CRC")]);

    expect(toRaw(store.allLibrarianStatuses)).toBe(map);
    expect(toRaw(store.allLibrarianStatuses.CCC)).toBe(kept);
    expect(toRaw(store.allLibrarianStatuses.ICC)).not.toBe(changed);
    expect(store.allLibrarianStatuses).toStrictEqual({
      CCC: status("CCC"),
      CRC: status("CRC"),
      ICC: status("ICC", 4),
    });
  });

  it("notifies only watchers of rows that changed", async () => {
    const store = adminStore();
    await loadStatuses(store, FIRST);
    const onKept = vi.fn();
    const onChanged = vi.fn();
    const onRemoved = vi.fn();
    const sync = { flush: "sync" };
    watch(() => store.allLibrarianStatuses.CCC, onKept, sync);
    watch(() => store.allLibrarianStatuses.ICC, onChanged, sync);
    watch(() => store.allLibrarianStatuses.IFQ, onRemoved, sync);

    await loadStatuses(store, [status("CCC"), status("ICC", 4)]);

    expect(onKept).not.toHaveBeenCalled();
    expect(onChanged).toHaveBeenCalledOnce();
    expect(onRemoved).toHaveBeenCalledOnce();
  });

  it("leaves the map alone for a non-array payload", async () => {
    const store = adminStore();
    await loadStatuses(store, FIRST);

    await loadStatuses(store, { results: [status("CRC")] });

    expect(Object.keys(store.allLibrarianStatuses)).toStrictEqual([
      "CCC",
      "ICC",
      "IFQ",
    ]);
  });

  it("warns and leaves the map alone when the request fails", async () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    const failure = new Error("offline");
    const store = adminStore();
    await loadStatuses(store, FIRST);
    API.getAllLibrarianStatuses.mockRejectedValue(failure);

    await store.loadAllStatuses();

    expect(warn).toHaveBeenCalledExactlyOnceWith(failure);
    expect(Object.keys(store.allLibrarianStatuses)).toStrictEqual([
      "CCC",
      "ICC",
      "IFQ",
    ]);
  });
});

describe("admin gate", () => {
  const GATED = [
    { action: "loadTable", args: ["User"], label: "loadTable" },
    {
      action: "loadTable",
      args: ["User", { force: true }],
      label: "forced loadTable",
    },
    {
      action: "loadTables",
      args: [["User", "Group"], { force: true }],
      label: "forced loadTables",
    },
    { action: "createRow", args: ["Group", { name: "g" }], label: "createRow" },
    {
      action: "updateRow",
      args: ["Group", 3, { name: "g" }],
      label: "updateRow",
    },
    { action: "deleteRow", args: ["Group", 3], label: "deleteRow" },
    {
      action: "revivePendingDelete",
      args: ["comics", 7],
      label: "revivePendingDelete",
    },
    { action: "loadAllStatuses", args: [], label: "loadAllStatuses" },
  ];
  const USERS = [
    { user: undefined, who: "an anonymous visitor" },
    {
      user: { id: 2, isStaff: false, username: "reader" },
      who: "a non-staff user",
    },
  ];

  it.each(
    USERS.flatMap((visitor) =>
      GATED.map((gated) => ({ ...gated, ...visitor })),
    ),
  )("$label refuses $who", async ({ action, args, user }) => {
    serveAll();
    useAuthStore().user = user;
    const store = useAdminStore();
    store.$patch({
      allLibrarianStatuses: { CCC: status("CCC") },
      groups: rowsFor("Group"),
      users: rowsFor("User"),
    });
    const before = structuredClone(toRaw(store.$state));

    await expect(store[action](...args)).resolves.toBe(false);

    for (const fn of allMocks()) {
      expect(fn).not.toHaveBeenCalled();
    }
    expect(store.$state).toStrictEqual(before);
  });
});
