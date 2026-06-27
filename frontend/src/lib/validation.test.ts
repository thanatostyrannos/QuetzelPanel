import { describe, it, expect } from "vitest";
import { isValidServerName } from "./validation";

describe("isValidServerName (DNS-1123 label)", () => {
  it.each(["mc", "mc-survival", "game123", "a", "a".repeat(32)])(
    "accepts %s",
    (name) => {
      expect(isValidServerName(name)).toBe(true);
    }
  );

  it.each([
    "",
    "-leading",
    "trailing-",
    "Has-Upper",
    "has space",
    "under_score",
    "a".repeat(33),
    "weird$",
  ])("rejects %s", (name) => {
    expect(isValidServerName(name)).toBe(false);
  });
});
