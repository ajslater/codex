// Common store functions
import { defineStore } from "pinia";

import * as API from "@/api/v4/common";

/*
 * Two renderers, two 400 shapes, one normalized map.
 *
 * Admin resource viewsets render through AdminJSONAPIRenderer, whose
 * ``format_errors`` is literally ``{"errors": data}`` -- so the body is
 * ``{"errors": {"username": [...]}}``, a dict rather than the JSON:API
 * error list, because DJA's own exception handler is not installed. It
 * stays a plain xior error, since the interceptor only wraps when
 * ``errors`` is an array.
 *
 * Envelope endpoints emit ``{"errors": [{status, title, detail}]}``,
 * which DOES wrap into an APIError -- and APIError has no ``.response``,
 * so anything reading ``error.response.data`` saw nothing at all.
 *
 * Both are pinned by tests/test_admin_error_shapes.py.
 */
const isPlainObject = (value) =>
  Boolean(value) && typeof value === "object" && !Array.isArray(value);

const messagesOf = (value) =>
  (Array.isArray(value) ? value.flat(Number.POSITIVE_INFINITY) : [value])
    .filter((message) => message !== null && message !== undefined)
    .map(String);

const fieldErrorMap = (error) => {
  const body = error?.response?.data;
  const envelopeDetail = error?.envelopeError?.detail;
  let map;
  if (isPlainObject(body) && isPlainObject(body.errors)) {
    map = body.errors;
  } else if (isPlainObject(envelopeDetail)) {
    map = envelopeDetail;
  } else if (isPlainObject(body) && !("errors" in body)) {
    // A bare DRF body, which is what a non-admin endpoint returns.
    map = body;
  }
  if (!map) {
    return {};
  }
  const fieldErrors = {};
  for (const [field, value] of Object.entries(map)) {
    const messages = messagesOf(value);
    if (messages.length > 0) {
      fieldErrors[field] = messages;
    }
  }
  return fieldErrors;
};

// Sentence-case a camelCase field name for the summary line.
const fieldLabel = (field) =>
  field
    .replaceAll(/([A-Z])/g, " $1")
    .replace(/^./, (c) => c.toUpperCase())
    .trim();

const flattenErrors = (fieldErrors) => {
  const entries = Object.entries(fieldErrors);
  if (entries.length === 0) {
    return [];
  }
  // A lone ``detail`` is already a whole sentence; naming it adds noise.
  if (entries.length === 1 && entries[0][0] === "detail") {
    return entries[0][1];
  }
  return entries.flatMap(([field, messages]) =>
    field === "detail"
      ? messages
      : messages.map((message) => `${fieldLabel(field)}: ${message}`),
  );
};

const getErrors = (xiorError) => {
  let errors = flattenErrors(fieldErrorMap(xiorError));
  if (errors.length === 0) {
    console.warn("Unable to parse error", xiorError);
    errors = ["Unknown error"];
  }
  return errors;
};

export const useCommonStore = defineStore("common", {
  state: () => ({
    form: {
      errors: [],
      // ``{field: [messages]}``, for binding :error-messages per input.
      fieldErrors: {},
      success: "",
    },
    versions: {
      // This is injected by vite define

      installed: CODEX_PACKAGE_VERSION,
      latest: undefined,
      // The server decides this, in /api/v4/version.
      outdated: false,
    },
    timestamp: Date.now(),
    isSettingsDrawerOpen: false,
    opdsURLs: undefined,
    /*
     * Why the OPDS urls failed to load, or "" when they haven't. The
     * dialog has nothing of its own to show while they're missing, so
     * without this a failed request leaves it spinning forever.
     */
    opdsURLsError: "",
    /*
     * Global app-level error string surfaced via a v-snackbar in
     * the root component. Reserved for problems that aren't tied
     * to a specific form (where ``form.errors`` would suffice) —
     * e.g. an expired CSRF cookie that leaves the session in a
     * silently-broken state and needs a user-visible nudge.
     */
    sessionError: "",
  }),
  actions: {
    async loadVersions() {
      await API.getVersions(this.timestamp)
        .then((response) => {
          const data = response.data;
          this.versions = data;
          return this.versions;
        })
        .catch(console.error);
    },
    setErrors(xiorError) {
      const fieldErrors = fieldErrorMap(xiorError);
      const errors = getErrors(xiorError);
      this.$patch((state) => {
        state.form.errors = errors;
        state.form.fieldErrors = fieldErrors;
        state.form.success = "";
      });
    },
    setSuccess(success) {
      this.$patch((state) => {
        state.form.errors = [];
        state.form.fieldErrors = {};
        state.form.success = success;
      });
    },
    clearErrors() {
      this.$patch((state) => {
        state.form.errors = [];
        state.form.fieldErrors = {};
        state.form.success = "";
      });
    },
    setSessionError(message) {
      this.sessionError = message;
    },
    clearSessionError() {
      this.sessionError = "";
    },
    setTimestamp() {
      this.timestamp = Date.now();
    },
    setSettingsDrawerOpen(value) {
      this.isSettingsDrawerOpen = value;
    },
    async loadOPDSURLs() {
      if (this.opdsURLs) {
        return;
      }
      this.opdsURLsError = "";
      await API.getOPDSURLs()
        .then((response) => {
          this.opdsURLs = Object.freeze({ ...response.data });
          return this.opdsURLs;
        })
        .catch((error) => {
          this.opdsURLsError = "Could not load the OPDS urls.";
          console.error(error);
        });
    },
  },
});
