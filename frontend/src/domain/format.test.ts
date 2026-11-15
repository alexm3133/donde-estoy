import { describe, expect, it } from "vitest";
import { durationParts, formatAgo, formatClimb, formatDistance, wholeMinutes } from "./format";

describe("durationParts", () => {
  it("rounds to the minute and splits hours", () => {
    expect(durationParts(22 * 60 + 20)).toEqual({ hours: 0, minutes: 22, imminent: false });
    expect(durationParts(65 * 60)).toEqual({ hours: 1, minutes: 5, imminent: false });
    expect(durationParts(59 * 60 + 40)).toEqual({ hours: 1, minutes: 0, imminent: false });
  });

  it("flags the last moments as imminent", () => {
    expect(durationParts(30).imminent).toBe(true);
    expect(durationParts(0).imminent).toBe(true);
    expect(durationParts(50)).toEqual({ hours: 0, minutes: 1, imminent: false });
  });

  it("never goes negative", () => {
    expect(durationParts(-500)).toEqual({ hours: 0, minutes: 0, imminent: true });
  });
});

describe("distances", () => {
  it("uses metres below a kilometre and locale decimals above", () => {
    expect(formatDistance(847, "es")).toBe("850 m");
    expect(formatDistance(3449, "es")).toBe("3,4 km");
    expect(formatDistance(3449, "en")).toBe("3.4 km");
    expect(formatDistance(42_195, "en")).toBe("42 km");
  });

  it("rounds climb to ten metres", () => {
    expect(formatClimb(456, "es")).toBe("460 m");
    expect(formatClimb(4, "es")).toBe("0 m");
  });
});

describe("relative time", () => {
  it("picks a sensible unit", () => {
    expect(formatAgo(5, "en")).toMatch(/5 sec/);
    expect(formatAgo(200, "en")).toMatch(/3 min/);
    expect(formatAgo(7300, "en")).toMatch(/2 hr/);
  });

  it("counts whole minutes, at least one", () => {
    expect(wholeMinutes(20)).toBe(1);
    expect(wholeMinutes(11 * 60 + 40)).toBe(12);
  });
});
