/**
 * Client-side mirror of the operator's compute_resources formula (WP-B).
 *
 * Pure function — no I/O, no side effects. Used by DeployModal to preview
 * the CPU/memory that will be allocated for a given player count before
 * the user submits the deploy form.
 *
 * Formula (integer arithmetic, matches Python operator exactly):
 *   memoryMiB = baseMemoryMiB + memoryPerPlayerMiB * N
 *   cpuMilli  = baseCpuMilli  + cpuPerPlayerMilli  * N
 * where N = clamp(maxPlayers, 0, sizing.maxPlayers)
 *
 * Optional ceilings (ceilingMemoryMiB / ceilingCpuMilli) clamp from above.
 * Output units: memory as "<int>Mi", cpu as "<int>m". requests === limits.
 */

import type { Sizing } from "../types";

export interface ResourceTier {
  cpu: string;   // e.g. "300m"
  memory: string; // e.g. "612Mi"
}

export interface ComputedResources {
  requests: ResourceTier;
  limits: ResourceTier;
}

export function computeResources(sizing: Sizing, maxPlayers: number): ComputedResources {
  // Clamp player count to [0, sizing.maxPlayers]
  const n = Math.max(0, Math.min(Math.floor(maxPlayers), sizing.maxPlayers));

  let memMiB = sizing.baseMemoryMiB + sizing.memoryPerPlayerMiB * n;
  let cpuMilli = sizing.baseCpuMilli + sizing.cpuPerPlayerMilli * n;

  if (sizing.ceilingMemoryMiB !== undefined) {
    memMiB = Math.min(memMiB, sizing.ceilingMemoryMiB);
  }
  if (sizing.ceilingCpuMilli !== undefined) {
    cpuMilli = Math.min(cpuMilli, sizing.ceilingCpuMilli);
  }

  const tier: ResourceTier = {
    cpu: `${cpuMilli}m`,
    memory: `${memMiB}Mi`,
  };
  return { requests: tier, limits: tier };
}

/** Format memory string for display: "612Mi" -> "612 MiB" */
export function fmtMemory(memory: string): string {
  if (memory.endsWith("Mi")) return `${memory.slice(0, -2)} MiB`;
  if (memory.endsWith("Gi")) return `${memory.slice(0, -2)} GiB`;
  return memory;
}

/** Format CPU string for display: "300m" -> "300 m" or "1000m" -> "1.0 cores" */
export function fmtCpu(cpu: string): string {
  if (cpu.endsWith("m")) {
    const milli = parseInt(cpu.slice(0, -1), 10);
    if (milli >= 1000) return `${(milli / 1000).toFixed(1)} cores`;
    return `${milli} mCPU`;
  }
  return cpu;
}
