import { describe, expect, it } from "vitest";
import ca from "./locales/ca.json";
import en from "./locales/en.json";
import es from "./locales/es.json";

type Tree = { [key: string]: string | Tree };

/** Flatten to `{ "a.b.c": "text" }`. */
function flatten(tree: Tree, prefix = ""): Record<string, string> {
  return Object.entries(tree).reduce<Record<string, string>>((all, [key, value]) => {
    if (typeof value === "string") all[prefix + key] = value;
    else Object.assign(all, flatten(value, `${prefix}${key}.`));
    return all;
  }, {});
}

const placeholders = (text: string) => [...text.matchAll(/{{(\w+)}}/g)].map((m) => m[1]).sort();

describe("translations", () => {
  const reference = flatten(es);

  it.each([
    ["ca", ca],
    ["en", en],
  ])("%s has exactly the same keys as es", (_, locale) => {
    expect(Object.keys(flatten(locale)).sort()).toEqual(Object.keys(reference).sort());
  });

  it.each([
    ["ca", ca],
    ["en", en],
  ])("%s uses the same {{placeholders}} as es", (_, locale) => {
    const flat = flatten(locale);
    for (const [key, text] of Object.entries(reference)) {
      expect(placeholders(flat[key]), key).toEqual(placeholders(text));
    }
  });

  it("has no empty strings", () => {
    for (const locale of [es, ca, en]) {
      for (const [key, text] of Object.entries(flatten(locale))) {
        expect(text.trim(), key).not.toBe("");
      }
    }
  });
});
