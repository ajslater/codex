/*
 * The enveloped redirect, end to end through the v4 interceptor.
 *
 * Codex answers an unbrowsable route with a 303 that carries its target
 * in the envelope's ``data`` and ships no ``Location`` header, so fetch
 * cannot follow it and it arrives as a rejection. Before the
 * interceptor learned the shape, ``handlePageError`` read ``settings``
 * and ``route`` off the envelope itself, found neither, and left the
 * page on a route the server had already refused.
 *
 * The other half is the one that is easy to break while fixing this:
 * an enveloped *error* puts ``null`` in ``data`` and the content in
 * ``errors`` (codex/views/envelope.py), so unwrapping every rejection
 * would hand ``fieldErrorMap`` a null and blank every form error in the
 * app. Both halves are asserted here.
 */
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";

const push = vi.fn(() => Promise.resolve());

vi.mock("@/plugins/router", () => ({
  default: {
    push: (...args) => push(...args),
    currentRoute: { value: { params: {}, query: {} } },
  },
}));

import { APIError, rejectEnvelopeError } from "@/api/v4/base";
import { useBrowserStore } from "@/stores/browser";
import { useCommonStore } from "@/stores/common";

/** What ``BrowserBreadcrumbsView`` puts in the 303's ``data``. */
const REDIRECT_DETAIL = {
  route: {
    name: "browser",
    params: { collection: "folders", parentIds: [], page: 1, name: "" },
  },
  settings: {
    orderBy: "sort_name",
    orderReverse: false,
    topCollection: "folders",
  },
  reason: "folders__in=(99999,) does not resolve",
};

const xiorError = (status, data) => ({ response: { status, data } });

const envelope = (data, errors = []) => ({ data, meta: {}, errors });

beforeEach(() => {
  push.mockClear();
  setActivePinia(createPinia());
});

describe("the v4 error interceptor", () => {
  it("unwraps an enveloped redirect to its detail", async () => {
    const error = xiorError(303, envelope(REDIRECT_DETAIL));

    await expect(rejectEnvelopeError(error)).rejects.toBe(error);

    expect(error.response.data).toStrictEqual(REDIRECT_DETAIL);
  });

  it("leaves an enveloped error body wrapped", async () => {
    const body = envelope(null, [
      {
        status: "400",
        title: "Bad Request",
        detail: { port: ["Ensure this value is greater than or equal to 1."] },
      },
    ]);
    const error = xiorError(400, body);

    const rejected = await rejectEnvelopeError(error).catch((e) => e);

    expect(rejected).toBeInstanceOf(APIError);
    // Not ``null``: several callers still read the raw body.
    expect(error.response.data).toStrictEqual(body);
  });

  it("keeps the field-error map readable off an enveloped 400", async () => {
    const error = xiorError(
      400,
      envelope(null, [
        {
          status: "400",
          title: "Bad Request",
          detail: { fromAddress: ["Enter a valid email address."] },
        },
      ]),
    );

    const rejected = await rejectEnvelopeError(error).catch((e) => e);
    useCommonStore().setErrors(rejected);

    expect(useCommonStore().form.fieldErrors).toStrictEqual({
      fromAddress: ["Enter a valid email address."],
    });
  });

  it("leaves a JSON:API body alone", async () => {
    // The admin renderer's ``errors`` is a dict, not the envelope list.
    const data = { errors: { username: ["Already taken."] } };
    const error = xiorError(400, data);

    await expect(rejectEnvelopeError(error)).rejects.toBe(error);

    expect(error.response.data).toStrictEqual(data);
  });

  it("leaves a redirect with no envelope data alone", async () => {
    const data = envelope(null);
    const error = xiorError(303, data);

    await expect(rejectEnvelopeError(error)).rejects.toBe(error);

    expect(error.response.data).toStrictEqual(data);
  });
});

describe("the browser store's redirect handler", () => {
  it("follows the unwrapped redirect", async () => {
    const error = xiorError(303, envelope(REDIRECT_DETAIL));
    await rejectEnvelopeError(error).catch(() => undefined);

    useBrowserStore().handlePageError(error);

    expect(push).toHaveBeenCalledWith({
      name: "browser",
      params: { collection: "folders" },
    });
  });

  it("goes nowhere when the envelope is still wrapped", () => {
    // The pre-fix shape, pinned so the unwrap cannot silently regress.
    useBrowserStore().handlePageError(
      xiorError(303, envelope(REDIRECT_DETAIL)),
    );

    expect(push).not.toHaveBeenCalled();
  });
});
