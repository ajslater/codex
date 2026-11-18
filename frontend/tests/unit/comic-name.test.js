/*
 * Issue number formatting.
 *
 * comicbox 5.6.2 reads issue "-1" as the number -1 with no suffix, so a
 * negative number reaches the card menu, which pads to three digits.
 */
import { describe, expect, it } from "vitest";

import { formattedIssue, getIssueName } from "@/comic-name";

describe("formattedIssue", () => {
  it("pads a positive issue", () => {
    expect(formattedIssue({ issueNumber: 7 }, 3)).toBe("007");
  });

  it("pads the magnitude of a negative issue and keeps the sign", () => {
    expect(formattedIssue({ issueNumber: -1 }, 3)).toBe("-001");
  });

  it("keeps a negative decimal issue's sign and fraction", () => {
    expect(formattedIssue({ issueNumber: -1.5 }, 3)).toBe("-001.5");
  });

  it("does not pad a negative issue without a pad", () => {
    expect(formattedIssue({ issueNumber: -1 })).toBe("-1");
  });

  it("appends a suffix to a negative issue", () => {
    expect(formattedIssue({ issueNumber: -1, issueSuffix: "AU" }, 2)).toBe(
      "-01AU",
    );
  });

  it("renders a bare suffix", () => {
    expect(formattedIssue({ issueNumber: null, issueSuffix: "AU" }, 3)).toBe(
      "AU",
    );
  });

  it("names a negative issue", () => {
    expect(getIssueName({ issueNumber: -1, issueCount: 12 }, 3)).toBe(
      "#-001 of 12",
    );
  });
});
