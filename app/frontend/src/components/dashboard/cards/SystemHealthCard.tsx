import { useEffect, useState } from "react";
import { Activity, Cpu, Gpu, HardDrive, MemoryStick } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { API_BASE_URL } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { SystemHealth } from "@/types/system-health";

const POLL_INTERVAL_MS = 3000;

function formatPercent(value: number | null) {
  return value == null ? "—" : `${Math.round(value)}%`;
}

function formatTemp(value: number | null) {
  return value == null ? null : `${value.toFixed(1)}°C`;
}

function formatGb(value: number | null) {
  if (value == null) return "—";
  if (value >= 1000) return `${(value / 1000).toFixed(2)} TB`;
  return `${value.toFixed(1)} GB`;
}

function UsageTile({
  icon,
  label,
  detail,
  percent,
  temperatureC,
}: {
  icon: React.ReactNode;
  label: string;
  detail?: string;
  percent: number | null;
  temperatureC?: number | null;
}) {
  const clampedPercent = percent == null ? 0 : Math.max(0, Math.min(percent, 100));
  const isHot = temperatureC != null && temperatureC >= 85;
  const isHighLoad = percent != null && percent >= 90;

  return (
    <div className="rounded-lg border p-3 compact:p-1.5">
      <div className="flex items-center justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2 text-muted-foreground compact:gap-1">
          <span className="shrink-0">{icon}</span>
          <span className="truncate text-sm font-medium text-foreground compact:text-xs">{label}</span>
        </div>

        {temperatureC != null && (
          <span className={cn("shrink-0 text-xs font-medium", isHot ? "text-destructive" : "text-muted-foreground")}>
            {formatTemp(temperatureC)}
          </span>
        )}
      </div>

      <div className={cn("mt-2 text-2xl font-bold tracking-tight compact:mt-0.5 compact:text-base", isHighLoad && "text-destructive")}>
        {formatPercent(percent)}
      </div>

      {detail && <p className="truncate text-xs text-muted-foreground compact:hidden">{detail}</p>}

      <div className="mt-2 h-2 overflow-hidden rounded-full bg-secondary compact:mt-1 compact:h-1">
        <div
          className={cn("h-full rounded-full transition-all", isHighLoad ? "bg-destructive" : "bg-primary")}
          style={{ width: `${clampedPercent}%` }}
        />
      </div>
    </div>
  );
}

export function SystemHealthCard() {
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function poll() {
      try {
        const response = await fetch(`${API_BASE_URL}/system/health`);
        if (!response.ok) {
          throw new Error(`Request failed with status ${response.status}`);
        }
        const data = (await response.json()) as SystemHealth;
        if (!cancelled) {
          setHealth(data);
          setError(null);
        }
      } catch {
        if (!cancelled) {
          setError(`Can't reach the backend at ${API_BASE_URL}.`);
        }
      }
    }

    poll();
    const intervalId = window.setInterval(poll, POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, []);

  const statusBadge = error
    ? { label: "Offline", variant: "destructive" as const }
    : !health
      ? { label: "Loading…", variant: "outline" as const }
      : health.source === "lhm"
        ? { label: "Live", variant: "secondary" as const }
        : { label: "Approximate", variant: "outline" as const };

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-center gap-3 compact:gap-2">
            <div className="w-fit rounded-xl border bg-secondary p-2 compact:p-1">
              <Activity className="h-5 w-5 compact:h-3.5 compact:w-3.5" />
            </div>
            <div>
              <CardTitle className="compact:text-xs">System Health</CardTitle>
              <CardDescription className="compact:hidden">Live hardware stats from this PC</CardDescription>
            </div>
          </div>

          <Badge variant={statusBadge.variant}>{statusBadge.label}</Badge>
        </div>
      </CardHeader>

      <CardContent className="space-y-3 compact:space-y-1.5">
        {error ? (
          <p className="text-sm text-muted-foreground">{error}</p>
        ) : (
          <>
            {health?.message && (
              <p className="rounded-lg border border-dashed p-3 text-xs text-muted-foreground compact:hidden">
                {health.message}
              </p>
            )}

            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4 compact:grid-cols-4 compact:gap-1.5">
              <UsageTile
                icon={<Cpu className="h-4 w-4" />}
                label="CPU"
                detail={[health?.cpu.name, health?.cpu.per_core_load_percent.length ? `${health.cpu.per_core_load_percent.length} cores` : null]
                  .filter(Boolean)
                  .join(" · ") || undefined}
                percent={health?.cpu.load_percent ?? null}
                temperatureC={health?.cpu.temperature_c}
              />

              <UsageTile
                icon={<MemoryStick className="h-4 w-4" />}
                label="Memory"
                detail={
                  health?.memory.used_gb != null && health?.memory.total_gb != null
                    ? `${formatGb(health.memory.used_gb)} / ${formatGb(health.memory.total_gb)}`
                    : undefined
                }
                percent={health?.memory.load_percent ?? null}
              />

              {health?.gpu.map((gpu) => (
                <UsageTile
                  key={gpu.name}
                  icon={<Gpu className="h-4 w-4" />}
                  label={gpu.name}
                  detail={
                    gpu.memory_used_gb != null && gpu.memory_total_gb != null
                      ? `${formatGb(gpu.memory_used_gb)} / ${formatGb(gpu.memory_total_gb)} VRAM`
                      : undefined
                  }
                  percent={gpu.load_percent}
                  temperatureC={gpu.temperature_c}
                />
              ))}

              {health?.storage.map((drive) => (
                <UsageTile
                  key={drive.name}
                  icon={<HardDrive className="h-4 w-4" />}
                  label={drive.name}
                  detail={
                    drive.used_gb != null && drive.total_gb != null
                      ? `${formatGb(drive.used_gb)} / ${formatGb(drive.total_gb)}`
                      : undefined
                  }
                  percent={drive.used_percent}
                  temperatureC={drive.temperature_c}
                />
              ))}
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
