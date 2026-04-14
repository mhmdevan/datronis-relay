import { describe, expect, it } from "vitest";
import {
  INTERVAL_PRESETS,
  findPresetKey,
  formatCustomSeconds,
  intervalLabelKey,
} from "@/lib/interval";

describe("findPresetKey", () => {
  it("returns the preset key for 60 seconds", () => {
    expect(findPresetKey(60)).toBe("1m");
  });

  it("returns the preset key for 3600 seconds", () => {
    expect(findPresetKey(3600)).toBe("1h");
  });

  it("returns undefined for non-preset values", () => {
    expect(findPresetKey(75)).toBeUndefined();
    expect(findPresetKey(0)).toBeUndefined();
  });

  it("round-trips every preset", () => {
    for (const preset of INTERVAL_PRESETS) {
      expect(findPresetKey(preset.seconds)).toBe(preset.key);
    }
  });
});

describe("intervalLabelKey", () => {
  it("maps preset seconds to preset intl keys", () => {
    expect(intervalLabelKey(60)).toBe("intervals.1m");
    expect(intervalLabelKey(86400)).toBe("intervals.1d");
  });

  it("falls back to the custom key for non-preset values", () => {
    expect(intervalLabelKey(75)).toBe("intervals.custom");
  });
});

describe("formatCustomSeconds", () => {
  it("formats sub-minute values as seconds", () => {
    expect(formatCustomSeconds(45)).toBe("45s");
  });

  it("formats sub-hour values as minutes", () => {
    expect(formatCustomSeconds(120)).toBe("2m");
  });

  it("formats sub-day values as hours", () => {
    expect(formatCustomSeconds(7200)).toBe("2h");
  });

  it("formats day-plus values as days", () => {
    expect(formatCustomSeconds(172800)).toBe("2d");
  });
});
