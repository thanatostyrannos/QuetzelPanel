/**
 * Tests for the client-side computeResources formula (WP-B).
 * Must match the Python operator formula exactly.
 */
import { describe, it, expect } from "vitest";
import { computeResources, fmtMemory, fmtCpu } from "./sizing";
import type { Sizing } from "../types";

const SIZING: Sizing = {
  baseMemoryMiB: 512,
  memoryPerPlayerMiB: 10,
  baseCpuMilli: 250,
  cpuPerPlayerMilli: 5,
  maxPlayers: 50,
  ceilingMemoryMiB: 4096,
  ceilingCpuMilli: 2000,
};

const SIZING_NO_CEILING: Sizing = {
  baseMemoryMiB: 512,
  memoryPerPlayerMiB: 10,
  baseCpuMilli: 250,
  cpuPerPlayerMilli: 5,
  maxPlayers: 200,
};

describe("computeResources", () => {
  it("returns correct units: memory ends in Mi, cpu ends in m", () => {
    const r = computeResources(SIZING, 10);
    expect(r.requests.memory).toMatch(/^\d+Mi$/);
    expect(r.requests.cpu).toMatch(/^\d+m$/);
  });

  it("requests === limits (Guaranteed QoS)", () => {
    const r = computeResources(SIZING, 20);
    expect(r.requests).toEqual(r.limits);
  });

  it("basic formula: base + per_player * N (no ceiling hit)", () => {
    const r = computeResources(SIZING_NO_CEILING, 10);
    expect(r.requests.memory).toBe("612Mi");   // 512 + 10*10
    expect(r.requests.cpu).toBe("300m");        // 250 + 5*10
  });

  it("zero players yields base values", () => {
    const r = computeResources(SIZING_NO_CEILING, 0);
    expect(r.requests.memory).toBe("512Mi");
    expect(r.requests.cpu).toBe("250m");
  });

  it("clamps maxPlayers input to sizing.maxPlayers", () => {
    const r50 = computeResources(SIZING, 50);
    const r999 = computeResources(SIZING, 999);
    expect(r999.requests).toEqual(r50.requests);
  });

  it("clamps negative maxPlayers to 0", () => {
    const r = computeResources(SIZING_NO_CEILING, -5);
    const r0 = computeResources(SIZING_NO_CEILING, 0);
    expect(r.requests).toEqual(r0.requests);
  });

  it("memory ceiling clamps the result", () => {
    const lowCeiling: Sizing = { ...SIZING_NO_CEILING, ceilingMemoryMiB: 600 };
    const r = computeResources(lowCeiling, 20); // formula = 512 + 10*20 = 712 > 600
    expect(r.requests.memory).toBe("600Mi");
  });

  it("cpu ceiling clamps the result", () => {
    const lowCpu: Sizing = { ...SIZING_NO_CEILING, ceilingCpuMilli: 300 };
    const r = computeResources(lowCpu, 20); // 250 + 5*20 = 350 > 300
    expect(r.requests.cpu).toBe("300m");
  });

  it("no ceiling means unclamped growth", () => {
    const r = computeResources(SIZING_NO_CEILING, 100);
    expect(r.requests.memory).toBe("1512Mi"); // 512 + 10*100
  });

  it("is monotone in maxPlayers (memory)", () => {
    let prev = 0;
    for (const n of [0, 1, 5, 10, 20, 40, 50, 100]) {
      const mem = parseInt(computeResources(SIZING, n).requests.memory, 10);
      expect(mem).toBeGreaterThanOrEqual(prev);
      prev = mem;
    }
  });

  it("is monotone in maxPlayers (cpu)", () => {
    let prev = 0;
    for (const n of [0, 1, 5, 10, 20, 40, 50, 100]) {
      const cpu = parseInt(computeResources(SIZING, n).requests.cpu, 10);
      expect(cpu).toBeGreaterThanOrEqual(prev);
      prev = cpu;
    }
  });

  it("matches the operator formula for Minecraft catalog sizing at 20 players", () => {
    // Mirrors the Minecraft sizing block in catalog.py
    const mcSizing: Sizing = {
      baseMemoryMiB: 768,
      memoryPerPlayerMiB: 12,
      baseCpuMilli: 250,
      cpuPerPlayerMilli: 5,
      maxPlayers: 50,
      ceilingMemoryMiB: 4096,
      ceilingCpuMilli: 2000,
    };
    const r = computeResources(mcSizing, 20);
    // 768 + 12*20 = 1008 MiB; 250 + 5*20 = 350 mCPU
    expect(r.requests.memory).toBe("1008Mi");
    expect(r.requests.cpu).toBe("350m");
  });
});

describe("fmtMemory", () => {
  it("formats Mi correctly", () => {
    expect(fmtMemory("612Mi")).toBe("612 MiB");
  });
  it("formats Gi correctly", () => {
    expect(fmtMemory("2Gi")).toBe("2 GiB");
  });
});

describe("fmtCpu", () => {
  it("formats milli-CPU under 1000", () => {
    expect(fmtCpu("350m")).toBe("350 mCPU");
  });
  it("formats milli-CPU >= 1000 as cores", () => {
    expect(fmtCpu("2000m")).toBe("2.0 cores");
  });
});
