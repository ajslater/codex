/*
 * Normalizing the server's 400s into one field-keyed map.
 *
 * Two renderers emit two different shapes, and the old parser saw
 * neither of them:
 *
 *   - Admin resource viewsets emit ``{"errors": {field: [...]}}``. The
 *     old scan looked for its known keys at the TOP level, so it fell
 *     through to ``errors = [data]`` and SubmitFooter rendered an
 *     object, which Vue stringified as JSON.
 *   - Envelope endpoints emit ``{"errors": [{status, title, detail}]}``,
 *     which the xior interceptor wraps into an APIError -- and APIError
 *     has no ``.response``, so the parser logged "Unable to parse
 *     error" and returned ["Unknown error"].
 *
 * Both shapes are pinned server-side by tests/test_admin_error_shapes.py.
 */
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, test } from "vitest";

import { APIError } from "@/api/v4/base";
import { useCommonStore } from "@/stores/common";

/** A plain xior error, which is what the JSON:API renderer produces. */
const jsonApiError = (errors) => ({
  response: { status: 400, data: { errors } },
});

/** What the interceptor hands callers for an envelope 400. */
const envelopeError = (detail) =>
  new APIError({ status: "400", title: "Bad Request", detail }, 400);

describe("common store error normalization", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  test("a JSON:API field error becomes a field-keyed map", () => {
    const store = useCommonStore();

    store.setErrors(
      jsonApiError({ username: ["A user with that username already exists."] }),
    );

    expect(store.form.fieldErrors).toStrictEqual({
      username: ["A user with that username already exists."],
    });
  });

  test("an envelope field error becomes the same shape", () => {
    const store = useCommonStore();

    store.setErrors(
      envelopeError({
        port: ["Ensure this value is greater than or equal to 1."],
        fromAddress: ["Enter a valid email address."],
      }),
    );

    expect(store.form.fieldErrors).toStrictEqual({
      port: ["Ensure this value is greater than or equal to 1."],
      fromAddress: ["Enter a valid email address."],
    });
  });

  test("the summary names the field when there is more than one", () => {
    const store = useCommonStore();

    store.setErrors(
      envelopeError({ port: ["Too small."], fromAddress: ["Bad address."] }),
    );

    expect(store.form.errors).toStrictEqual([
      "Port: Too small.",
      "From Address: Bad address.",
    ]);
  });

  test("a lone detail stays a bare sentence", () => {
    const store = useCommonStore();

    store.setErrors(jsonApiError({ detail: "Not found." }));

    expect(store.form.errors).toStrictEqual(["Not found."]);
  });

  test("the summary is never a stringified object", () => {
    const store = useCommonStore();

    store.setErrors(
      jsonApiError({ username: ["A user with that username already exists."] }),
    );

    for (const error of store.form.errors) {
      expect(typeof error).toBe("string");
      expect(error).not.toContain("[object Object]");
      expect(error).not.toContain('{"');
    }
  });

  test("an unparseable error still yields something to show", () => {
    const store = useCommonStore();

    store.setErrors(new Error("network down"));

    expect(store.form.errors).toStrictEqual(["Unknown error"]);
    expect(store.form.fieldErrors).toStrictEqual({});
  });

  test("clearing drops the field map too", () => {
    const store = useCommonStore();
    store.setErrors(jsonApiError({ username: ["Taken."] }));

    store.clearErrors();

    expect(store.form.fieldErrors).toStrictEqual({});
    expect(store.form.errors).toStrictEqual([]);
  });

  test("a success drops the field map too", () => {
    const store = useCommonStore();
    store.setErrors(jsonApiError({ username: ["Taken."] }));

    store.setSuccess("Saved.");

    expect(store.form.fieldErrors).toStrictEqual({});
  });
});

export default {};
