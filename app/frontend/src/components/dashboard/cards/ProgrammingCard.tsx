import { useEffect, useState } from "react";
import { Code2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { API_BASE_URL } from "@/lib/api";
import type { ProgrammingStatus } from "@/types/programming-status";

const POLL_INTERVAL_MS = 5000;

function formatDate(iso: string | null | undefined) {
  if (!iso) return "—";
  return new Intl.DateTimeFormat("en-CA", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(iso));
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-4 rounded-lg border px-3 py-2 compact:px-2 compact:py-1 compact:text-xs">
      <span className="shrink-0 text-muted-foreground">{label}</span>
      <span className="truncate text-right font-medium">{value}</span>
    </div>
  );
}

export function ProgrammingCard() {
  const [status, setStatus] = useState<ProgrammingStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function poll() {
      try {
        const response = await fetch(`${API_BASE_URL}/programming/status`);
        if (!response.ok) {
          throw new Error(`Request failed with status ${response.status}`);
        }
        const data = (await response.json()) as ProgrammingStatus;
        if (!cancelled) {
          setStatus(data);
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
    : !status
      ? { label: "Loading…", variant: "outline" as const }
      : !status.available
        ? { label: "Unavailable", variant: "destructive" as const }
        : status.changed_files === 0
          ? { label: "Clean", variant: "secondary" as const }
          : {
              label: `${status.changed_files} change${status.changed_files === 1 ? "" : "s"}`,
              variant: "outline" as const,
            };

  const syncLabel = !status
    ? "—"
    : status.ahead || status.behind
      ? [status.ahead ? `${status.ahead} ahead` : null, status.behind ? `${status.behind} behind` : null]
          .filter(Boolean)
          .join(" · ")
      : "In sync";

  const commitValue =
    status?.commit_message && status.commit_hash
      ? `${status.commit_message} (${status.commit_hash})`
      : "—";

  return (
    <Card className="w-full">
      <CardHeader>
        <div className="flex items-start justify-between gap-4">
          <div className="rounded-xl border bg-secondary p-2 compact:p-1">
            <Code2 className="h-5 w-5 compact:h-3.5 compact:w-3.5" />
          </div>

          <Badge variant={statusBadge.variant}>{statusBadge.label}</Badge>
        </div>
        <CardTitle className="compact:text-xs">Programming Mode</CardTitle>

        <CardDescription className="compact:hidden">
          Current project, branch, coding focus
        </CardDescription>
      </CardHeader>

      <CardContent className="space-y-3 text-sm compact:space-y-1">
        {error || status?.available === false ? (
          <p className="text-sm text-muted-foreground">{error ?? status?.message}</p>
        ) : (
          <>
            <InfoRow label="Project" value={status?.project_name ?? "—"} />
            <InfoRow label="Branch" value={status?.branch ?? "—"} />
            <InfoRow label="Latest Commit" value={commitValue} />
            <InfoRow label="Author" value={status?.commit_author ?? "—"} />
            <InfoRow label="Updated" value={formatDate(status?.commit_date)} />
            <InfoRow label="Sync" value={syncLabel} />
          </>
        )}
      </CardContent>
    </Card>
  );
}
