export interface CpuStats {
  name: string | null;
  load_percent: number | null;
  temperature_c: number | null;
  per_core_load_percent: number[];
}

export interface MemoryStats {
  load_percent: number | null;
  used_gb: number | null;
  total_gb: number | null;
}

export interface GpuStats {
  name: string;
  load_percent: number | null;
  temperature_c: number | null;
  memory_used_gb: number | null;
  memory_total_gb: number | null;
}

export interface StorageStats {
  name: string;
  used_percent: number | null;
  used_gb: number | null;
  total_gb: number | null;
  temperature_c: number | null;
}

export interface SystemHealth {
  source: "lhm" | "fallback";
  generated_at: string;
  message: string | null;
  cpu: CpuStats;
  memory: MemoryStats;
  gpu: GpuStats[];
  storage: StorageStats[];
}
