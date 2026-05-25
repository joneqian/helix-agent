/**
 * i18n bootstrap tests — Stream H.1b PR 2a.
 *
 * Two invariants we care about:
 *
 *   1. The locale modules are structurally identical (catches missing
 *      translations early). ``TranslationKeys`` already enforces it at
 *      compile time, but a runtime check guards against accidental
 *      drift via ``as unknown`` casts in future PRs.
 *   2. ``i18next.changeLanguage`` flips ``t()`` in place — i.e. the
 *      React glue is wired.
 */
import { describe, expect, it } from "vitest";

import "../index";
import i18n from "../index";
import en from "../locales/en";
import zhCN from "../locales/zh-CN";

function collectKeys(obj: object, prefix = ""): string[] {
  const out: string[] = [];
  for (const [key, value] of Object.entries(obj)) {
    const path = prefix ? `${prefix}.${key}` : key;
    if (value !== null && typeof value === "object") {
      out.push(...collectKeys(value, path));
    } else {
      out.push(path);
    }
  }
  return out.sort();
}

describe("locale modules", () => {
  it("zh-CN has the same key set as en", () => {
    expect(collectKeys(zhCN)).toEqual(collectKeys(en));
  });
});

describe("i18n runtime", () => {
  it("changeLanguage swaps the returned translations", async () => {
    await i18n.changeLanguage("en");
    expect(i18n.t("common.sign_in")).toBe("Sign in");
    await i18n.changeLanguage("zh-CN");
    expect(i18n.t("common.sign_in")).toBe("登录");
  });
});
