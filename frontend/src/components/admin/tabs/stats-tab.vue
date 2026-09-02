<template>
  <div v-if="stats" id="stats">
    <AdminKeyValueTable
      v-for="section of sections"
      :key="section.title"
      :title="section.title"
      :items="section.items"
    />
  </div>
</template>

<script>
import { mapActions, mapState } from "pinia";
import { capitalCase, snakeCase } from "text-case";

import AdminKeyValueTable from "@/components/admin/tabs/key-value-table.vue";
import { useAdminStore } from "@/stores/admin";
import { useCommonStore } from "@/stores/common";

import { ORDER_BY, TOP_COLLECTION } from "@/choices/browser-map.json";
import { FIT_TO, READING_DIRECTION } from "@/choices/reader-map.json";

const VIEW_MODE = Object.freeze({ cover: "Cover", table: "Table" });
const TABLE_COVER_SIZE = Object.freeze({ sm: "Small" });
// What "" means per setting, in the words chronicle's dashboard uses for the
// same key, so the two surfaces do not describe one number differently.
const UNSET_LABELS = Object.freeze({
  fitTo: "Unset (Fit to Width)",
  readingDirection: "Unset (Left to Right)",
  orderBy: "Unset (Name)",
  finishOnLastPage: "Unset (On)",
  twoPages: "Unset (Off)",
  readRtlInReverse: "Unset (Off)",
  pageTransition: "Unset (On)",
  cacheBook: "Unset (Off)",
});
const LOOKUPS = Object.freeze({
  topCollection: TOP_COLLECTION,
  orderBy: ORDER_BY,
  fitTo: FIT_TO,
  readingDirection: READING_DIRECTION,
  viewMode: VIEW_MODE,
  tableCoverSize: TABLE_COVER_SIZE,
});
const CONFIG_LABELS = Object.freeze({
  authGroupCount: "Authorization Groups",
  libraryCount: "Libraries",
  libraryReadOnlyCount: "+Read Only",
  libraryPollCount: "+Polled",
  libraryEventsCount: "+Watched for Events",
  libraryGroupAclCount: "+Group Restricted",
  sessionCount: "Sessions",
  userAnonymousCount: "Anonymous Users",
  userRegisteredCount: "Registered Users",
  customCoverCount: "Custom Covers",
  customCoverUploadedCount: "+Uploaded",
  customCoverDirCount: "+From Covers Folder",
  failedImportCount: "Failed Imports",
});
// Metadata keys whose label isn't just the key plus an "s".
const METADATA_LABELS = Object.freeze({
  countryCount: "Countries",
  storyCount: "Stories",
  comicCommunityRatingCount: "Comics Rated",
  comicCommunityRatingVoteCount: "+With Vote Counts",
  comicAlternativeIssueNumberCount: "Comics with Alternate Issue Numbers",
  comicMetadataImportedCount: "Comics with Imported Tags",
});
const USAGE_LABELS = Object.freeze({
  bookmarkCount: "Bookmarks",
  favoriteCount: "Favorites",
  favoriteUserCount: "Users with Favorites",
  favorites: "Favorites by Collection",
});
const ADMIN_FLAG_LABELS = Object.freeze({
  autoUpdate: "Auto Update",
  folderView: "Folder View",
  importMetadata: "Import Tags on Library Scan",
  lazyImportMetadata: "Import Tags on Demand",
  nonUsers: "Non Users",
  registration: "Registration",
  registerVerification: "Verify New User Email",
  sendTelemetry: "Send Stats",
  apiKeySet: "API Key",
  bannerTextSet: "Banner Text",
  browserDefaultCollection: "Default View",
  browserMaxObjPerPage: "Browser Page Size",
  customCoverMaxUploadMb: "Custom Cover Max Upload (MB)",
  ageRatingDefault: "Age Rating Default",
  anonymousUserAgeRating: "Anonymous User Age Rating",
});
const TAGGING_LABELS = Object.freeze({
  defaultMatchMode: "Match Mode",
  defaultPromptsMode: "Prompts",
  mergeAllSources: "Merge All Sources",
  deleteOriginal: "Delete Original",
  renameFiles: "Rename Files",
  defaultSources: "Enabled Sources",
  defaultFormatCount: "Write Formats",
  hasMetronCredentials: "Metron Credentials",
  hasComicvineCredentials: "Comic Vine Credentials",
  comicvineUrlSet: "Custom Comic Vine URL",
});
const AUTH_LABELS = Object.freeze({
  oidcEnabled: "Single Sign On",
  oidcCreateUsers: "+Create Users",
  oidcLinkByEmail: "+Link by Email",
  oidcSyncGroups: "+Sync Groups",
  oidcPkce: "+PKCE",
  oidcFetchUserinfo: "+Fetch Userinfo",
  oidcRpInitiatedLogout: "+Logout at Provider",
  oidcAdminGroupSet: "+Admin Group",
  oidcScopeCustom: "+Custom Scope",
  oidcUsernameClaimCustom: "+Custom Username Claim",
  oidcGroupsClaimCustom: "+Custom Groups Claim",
  oidcTokenAuthMethod: "+Token Auth Method",
  userAgeCeilingCount: "Age Restricted Users",
  authGroupExcludeCount: "Excluded Groups",
});
const EMAIL_LABELS = Object.freeze({
  smtpConfigured: "SMTP Configured",
  smtpUseTls: "Use TLS",
  smtpUseSsl: "Use SSL",
});
const THROTTLE_LABELS = Object.freeze({
  throttleAnon: "Anonymous",
  throttleUser: "User",
  throttleOpds: "OPDS",
  throttleOpensearch: "OpenSearch",
  throttleResetPassword: "Reset Password",
});
const DEPLOYMENT_LABELS = Object.freeze({
  remoteUserAuth: "Remote User SSO",
  failedLoginLog: "Failed Login Log",
  failedLoginLogTrustForwardedFor: "+Trust Forwarded For",
  urlPathPrefixSet: "Reverse Proxy Subpath",
});
const INDENT_KEYS = Object.freeze(
  new Set([
    "creditPersonsCount",
    "creditRolesCount",
    "identifierSourcesCount",
    "storyArcNumbersCount",
  ]),
);
// Booleans that answer "have you configured this", not "is this turned on".
const SET_SUFFIXES = ["Set", "Custom", "Configured", "Credentials"];
const NONE = "None";

// Every stats table, in render order: the caption it wears and the computed
// that fills it. Exported so a test enumerates the sections from here instead
// of keeping a second copy of the titles that goes stale when one is renamed.
const SECTIONS = Object.freeze([
  ["Platform", "platformTable"],
  // The API key is deliberately absent: the payload still carries
  // ``stats.config.apiKey``, but configTable drops it from the rendered keys.
  // The key itself and its regenerate button live on the Settings tab.
  ["Config", "configTable"],
  ["File Types", "fileTypesTable"],
  // Two denominators, named apart. Sessions counts settings rows, one per user
  // and per anonymous session; per user counts people, one vote each. Titling
  // either of them "User Settings" invited reading one as the other.
  ["Settings by Session", "sessionSettingsTable"],
  ["Settings by User", "perUserSettingsTable"],
  ["Browser Collections", "browserCollectionsTable"],
  ["Tags", "metadataTable"],
  ["Reading", "usageTable"],
  ["Identifiers", "identifiersTable"],
  ["Admin Flags", "adminFlagsTable"],
  ["Online Tagging", "taggingTable"],
  ["Authentication", "authTable"],
  ["Email", "emailTable"],
  ["Rate Limits", "throttleTable"],
  ["Deployment", "deploymentTable"],
]);
export const SECTION_TITLES = Object.freeze(SECTIONS.map(([title]) => title));

export default {
  name: "AdminStatsTab",
  components: {
    AdminKeyValueTable,
  },
  data() {
    return {
      showTooltip: { show: false },
    };
  },
  computed: {
    sections() {
      return SECTIONS.map(([title, items]) => ({
        title,
        items: this[items],
      }));
    },
    ...mapState(useCommonStore, {}),
    ...mapState(useAdminStore, {
      stats: (state) => state.stats,
    }),
    platformTable() {
      const table = {};
      for (const [key, value] of Object.entries(this.stats?.platform ?? {})) {
        const label = this.keyToLabel(key);
        const labelValue =
          key === "system" ? `${value.name} ${value.release}` : value;
        Reflect.set(table, label, labelValue);
      }
      return table;
    },
    configTable() {
      return this.labeledTable(this.stats?.config, CONFIG_LABELS, ["apiKey"]);
    },
    sessionSettingsTable() {
      return this.settingsTable(this.stats?.sessions);
    },
    perUserSettingsTable() {
      // Bucket names carry their family as a prefix and "_users" as a suffix;
      // the vocabulary to label them by is the setting in between.
      return this.settingsTable(this.stats?.per_user, (key) =>
        key
          .replace(/^(browser|reader)_(chosen_|global_)?/, "")
          .replace(/_users$/, ""),
      );
    },
    browserCollectionsTable() {
      const table = {};
      for (const [key, value] of Object.entries(
        this.stats?.collections ?? {},
      )) {
        let label = this.keyToLabel(key);
        if (label !== "Series") {
          label += "s";
        }
        Reflect.set(table, label, value);
      }
      return table;
    },
    fileTypesTable() {
      const table = {};
      for (const [key, value] of Object.entries(this.stats?.fileTypes ?? {})) {
        const label =
          key === "unknown"
            ? capitalCase(key)
            : this.keyToLabel(key).toUpperCase();
        Reflect.set(table, label, value);
      }
      return table;
    },
    metadataTable() {
      const table = {};
      for (const [key, value] of Object.entries(this.stats?.metadata ?? {})) {
        // Most metadata keys are "<tag>Count" and pluralize by adding an s.
        // The ones that don't are named outright.
        let label =
          Reflect.get(METADATA_LABELS, key) ?? this.keyToLabel(key) + "s";
        if (INDENT_KEYS.has(key)) {
          label = label.replace(/^\w+ /, "+");
        }
        Reflect.set(table, label, value);
      }
      return table;
    },
    usageTable() {
      return this.labeledTable(this.stats?.usage, USAGE_LABELS);
    },
    identifiersTable() {
      const table = {};
      for (const [key, value] of Object.entries(
        this.stats?.identifiers ?? {},
      )) {
        const [source, idType] = key.split(":");
        const label = `${capitalCase(source)}: ${capitalCase(idType)}`;
        Reflect.set(table, label, value);
      }
      return table;
    },
    adminFlagsTable() {
      return this.labeledTable(this.stats?.adminFlags, ADMIN_FLAG_LABELS);
    },
    taggingTable() {
      return this.labeledTable(this.stats?.tagging, TAGGING_LABELS);
    },
    authTable() {
      return this.labeledTable(this.stats?.auth, AUTH_LABELS);
    },
    emailTable() {
      return this.labeledTable(this.stats?.email, EMAIL_LABELS);
    },
    throttleTable() {
      return this.labeledTable(this.stats?.throttle, THROTTLE_LABELS);
    },
    deploymentTable() {
      return this.labeledTable(this.stats?.deployment, DEPLOYMENT_LABELS);
    },
  },
  created() {
    this.loadStats();
  },
  methods: {
    bucketLabel(lookupKey, typeKey) {
      // "" means nobody touched the setting, which no choices map has a name
      // for -- and before this fallback existed it resolved to undefined and
      // rendered as the literal string "undefined".
      if (typeKey === "") {
        return Reflect.get(UNSET_LABELS, lookupKey) ?? "Unset";
      }
      const lookup = Reflect.get(LOOKUPS, lookupKey);
      const label = lookup
        ? Reflect.get(lookup, snakeCase(typeKey))
        : undefined;
      // Fall back to the key itself rather than undefined: an unmapped value
      // is a vocabulary that drifted, and its name is more use than a hole.
      return label ?? typeKey;
    },
    settingsTable(section, lookupFor = (key) => key) {
      const table = {};
      for (const [key, value] of Object.entries(section ?? {})) {
        const label = this.keyToLabel(key);
        if (typeof value !== "object") {
          Reflect.set(table, label, this.displayValue(key, value));
          continue;
        }
        const countTable = {};
        for (const [typeKey, count] of Object.entries(value)) {
          Reflect.set(
            countTable,
            this.bucketLabel(lookupFor(key), typeKey),
            count,
          );
        }
        Reflect.set(table, label, countTable);
      }
      return table;
    },
    ...mapActions(useAdminStore, ["loadStats"]),
    keyToLabel(key) {
      key = key.replace(/Count$/, "");
      return capitalCase(key);
    },
    labeledTable(section, labels, skipKeys = []) {
      const table = {};
      for (const [key, value] of Object.entries(section ?? {})) {
        if (skipKeys.includes(key)) {
          continue;
        }
        const label = Reflect.get(labels, key) ?? this.keyToLabel(key);
        Reflect.set(table, label, this.displayValue(key, value));
      }
      return table;
    },
    // A boolean means one of two different things depending on the setting,
    // and the difference is the point of this page: "Yes" is a toggle that is
    // on, "Set" is a value we deliberately do not report.
    displayValue(key, value) {
      if (typeof value === "boolean") {
        const isSetFlag = SET_SUFFIXES.some((suffix) => key.endsWith(suffix));
        if (isSetFlag) {
          return value ? "Set" : "Not set";
        }
        return value ? "Yes" : "No";
      }
      if (value === "" || value === null) {
        return NONE;
      }
      if (typeof value === "object" && Object.keys(value).length === 0) {
        return NONE;
      }
      return value;
    },
  },
};
</script>
