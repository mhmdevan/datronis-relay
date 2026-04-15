import { describe, expect, it } from "vitest";
import en from "../../messages/en.json";
import de from "../../messages/de.json";
import es from "../../messages/es.json";
import fr from "../../messages/fr.json";
import zh from "../../messages/zh.json";
import ja from "../../messages/ja.json";

/**
 * Locale-parity guard.
 *
 * Every non-English locale file must define the exact same set of keys
 * as `en.json`. This is an explicit KPI ("Locale files out of sync" must
 * be zero) from `datronis-relay-ui-roadmap.md`. It catches copy-paste
 * drift the moment a translator forgets to propagate a new key.
 */

type JsonShape = Record<string, unknown>;

function collectKeys(
  obj: JsonShape,
  prefix = "",
  out: string[] = [],
): string[] {
  for (const [key, value] of Object.entries(obj)) {
    const path = prefix ? `${prefix}.${key}` : key;
    if (value !== null && typeof value === "object" && !Array.isArray(value)) {
      collectKeys(value as JsonShape, path, out);
    } else {
      out.push(path);
    }
  }
  return out;
}

const LOCALES: Array<[string, JsonShape]> = [
  ["de", de as JsonShape],
  ["es", es as JsonShape],
  ["fr", fr as JsonShape],
  ["zh", zh as JsonShape],
  ["ja", ja as JsonShape],
];

describe("locale parity", () => {
  const enKeys = new Set(collectKeys(en as JsonShape));

  for (const [name, bundle] of LOCALES) {
    it(`${name}.json has the same keys as en.json`, () => {
      const localeKeys = new Set(collectKeys(bundle));
      const missingInLocale = [...enKeys].filter((k) => !localeKeys.has(k));
      const extraInLocale = [...localeKeys].filter((k) => !enKeys.has(k));
      expect({ missing: missingInLocale, extra: extraInLocale }).toEqual({
        missing: [],
        extra: [],
      });
    });
  }
});
