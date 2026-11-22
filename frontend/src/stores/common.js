// Common store functions
import { defineStore } from "pinia";
import { markRaw } from "vue";

import * as API from "@/api/v4/common";

/*
 * Two renderers, two 400 shapes, one normalized map.
 *
 * Admin resource viewsets render through AdminJSONAPIRenderer, whose
 * ``render_errors`` is literally ``{"errors": data}`` -- so the body is
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
  (Array.isArray(value) ? value.flat(Infinity) : [value])
    .filter((message) => message !== null && message !== undefined)
    .map(String);

export const fieldErrorMap = (error) => {
  const body = error?.response?.data;
  const envelopeDetail = error?.envelopeError?.detail;
  let map;
  if (isPlainObject(body) && isPlainObject(body.errors)) {
    map = body.errors;
  } else if (isPlainObject(envelopeDetail)) {
    map = envelopeDetail;
  } else if (typeof envelopeDetail === "string" && envelopeDetail) {
    // A view's ``Response({"detail": "..."})``: the envelope's detail is
    // the sentence itself.
    map = { detail: [envelopeDetail] };
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
    .replaceAll(/[A-Z]/gu, " $&")
    .replace(/^./u, (c) => c.toUpperCase())
    .trim();

const flattenErrors = (fieldErrors) => {
  const entries = Object.entries(fieldErrors);
  if (entries.length === 0) {
    return [];
  }
  // A lone ``detail`` is already a whole sentence; naming it adds noise.
  return entries.length === 1 && entries[0][0] === "detail"
    ? entries[0][1]
    : entries.flatMap(([field, messages]) =>
        field === "detail"
          ? messages
          : messages.map((message) => `${fieldLabel(field)}: ${message}`),
      );
};

export const getErrors = (xiorError) => {
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
    /*
     * Global app-level error string surfaced via a v-snackbar in
     * the root component. Reserved for problems that aren't tied
     * to a specific form (where ``form.errors`` would suffice) —
     * e.g. an expired CSRF cookie that leaves the session in a
     * silently-broken state and needs a user-visible nudge.
     */
    sessionError: "",
    /*
     * App-wide notice for an action taken outside a form, such as adding
     * comics to a reading list from a menu, where ``form.success`` and
     * ``form.errors`` have nothing to show them. ``notice-snackbar.vue``
     * in the root component shows it.
     */
    notice: { text: "", error: false, action: undefined },
  }),
  actions: {
    async loadVersions() {
      try {
        const response = await API.getVersions(this.timestamp);
        const data = response.data;
        this.versions = data;
      } catch (error) {
        console.error(error);
      }
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
    setNotice(text, { error = false, action } = {}) {
      /*
       * ``action`` is ``{label, run}``: a button on the notice that runs
       * ``run`` and closes it, such as removing the series an issue is in
       * a list through. Raw: a function nothing renders.
       */
      this.notice = {
        text,
        error,
        action: action ? markRaw(action) : undefined,
      };
    },
    setErrorNotice(xiorError) {
      this.setNotice(getErrors(xiorError).join(" "), { error: true });
    },
    clearNotice() {
      this.notice = { text: "", error: false, action: undefined };
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
  },
});
