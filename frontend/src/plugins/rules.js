import { createRulesPlugin } from "vuetify";

/*
 * Codex aliases for Vuetify's rules plugin (vuetifyjs.com/features/rules).
 *
 * An alias builder runs once, when a `:rules` array is resolved; the rule it
 * RETURNS runs on every validate(). A parameter passed as a getter therefore
 * stays live — ["$notIn", () => this.usernames] re-reads the Set at
 * validation time, while ["$notIn", this.usernames] freezes whatever it was
 * when the array was built. Vuetify never re-validates merely because the
 * rules array changed (it watches the model and focus, not props.rules), so
 * pass a getter for anything that can move while the form is open.
 */
const unwrap = (value) => (typeof value === "function" ? value() : value);

// A blank numeric field is "unset", not "out of range" — every numeric field
// in Codex is optional and clears to null or "". Call sites that require a
// value put "$required" ahead of the range rule.
const isBlank = (value) =>
  value === null || value === "" || value === undefined;

const RANGE_MESSAGE = "Must be {0}–{1}";

export function createCodexRulesPlugin(locale) {
  // Custom aliases don't inherit the built-ins' translator. t() returns any
  // key that doesn't start with "$vuetify." verbatim, with {0}/{1} filled in.
  const { t } = locale;
  const range =
    (isNumber) =>
    ([min, max], err) =>
    (v) =>
      isBlank(v) ||
      (isNumber(Number(v)) && Number(v) >= min && Number(v) <= max) ||
      t(err ?? RANGE_MESSAGE, min, max);

  return createRulesPlugin(
    {
      aliases: {
        intRange: range(Number.isInteger),
        numRange: range(Number.isFinite),
        notIn: (names, err) => (v) => {
          const taken = unwrap(names);
          return (
            !v ||
            !taken ||
            !taken.has(String(v).trim()) ||
            t(err ?? "Already used")
          );
        },
      },
    },
    locale,
  );
}
