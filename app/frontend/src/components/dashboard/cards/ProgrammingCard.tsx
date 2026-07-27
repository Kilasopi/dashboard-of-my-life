import { useEffect, useState } from "react";
import { Code2, Gauge, Timer } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { API_BASE_URL } from "@/lib/api";
import type { ClaudeUsage } from "@/types/claude-usage";
import type { ProgrammingStatus } from "@/types/programming-status";

const POLL_INTERVAL_MS = 5000;
const CLAUDE_POLL_INTERVAL_MS = 5000;
const LIMIT_WINDOW_HOURS = 5;

function formatDuration(totalSeconds: number) {
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = Math.floor(totalSeconds % 60);
  const parts = [hours, minutes, seconds].map((n) => String(n).padStart(2, "0"));
  return hours > 0 ? parts.join(":") : parts.slice(1).join(":");
}

function formatTokens(value: number) {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K`;
  return String(value);
}

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
  const [claudeUsage, setClaudeUsage] = useState<ClaudeUsage | null>(null);
  const [claudeError, setClaudeError] = useState<string | null>(null);
  const [nowTick, setNowTick] = useState(() => Date.now());

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

  useEffect(() => {
    let cancelled = false;

    async function poll() {
      try {
        const response = await fetch(`${API_BASE_URL}/claude-usage/status`);
        if (!response.ok) {
          throw new Error(`Request failed with status ${response.status}`);
        }
        const data = (await response.json()) as ClaudeUsage;
        if (!cancelled) {
          setClaudeUsage(data);
          setClaudeError(null);
        }
      } catch {
        if (!cancelled) {
          setClaudeError(`Can't reach the backend at ${API_BASE_URL}.`);
        }
      }
    }

    poll();
    const intervalId = window.setInterval(poll, CLAUDE_POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, []);

  // Ticks the on-screen timer every second between polls so it reads as live
  // instead of jumping in 5s steps.
  useEffect(() => {
    const tickId = window.setInterval(() => setNowTick(Date.now()), 1000);
    return () => window.clearInterval(tickId);
  }, []);

  const liveElapsedSeconds =
    claudeUsage?.live && claudeUsage.session_started_at
      ? (nowTick - new Date(claudeUsage.session_started_at).getTime()) / 1000
      : claudeUsage?.session_elapsed_seconds ?? null;

  const resetCountdownSeconds =
    claudeUsage?.limit_window_active && claudeUsage.limit_window_resets_at
      ? Math.max(0, (new Date(claudeUsage.limit_window_resets_at).getTime() - nowTick) / 1000)
      : null;

  const windowProgressPercent =
    claudeUsage?.limit_window_active && claudeUsage.limit_window_started_at
      ? Math.max(
          0,
          Math.min(
            100,
            ((nowTick - new Date(claudeUsage.limit_window_started_at).getTime()) /
              (LIMIT_WINDOW_HOURS * 60 * 60 * 1000)) *
              100,
          ),
        )
      : 0;

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

            <div className="rounded-lg border p-3 compact:p-2">
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2 text-muted-foreground">
                  <Timer className="h-4 w-4 compact:h-3.5 compact:w-3.5" />
                  <span className="text-sm font-medium text-foreground compact:text-xs">
                    Claude Usage
                  </span>
                </div>

                {claudeError ? (
                  <Badge variant="destructive">Offline</Badge>
                ) : !claudeUsage ? (
                  <Badge variant="outline">Loading…</Badge>
                ) : !claudeUsage.available ? (
                  <Badge variant="destructive">Unavailable</Badge>
                ) : claudeUsage.live ? (
                  <Badge variant="secondary">Live</Badge>
                ) : (
                  <Badge variant="outline">Idle</Badge>
                )}
              </div>

              {claudeError || claudeUsage?.available === false ? (
                <p className="mt-2 text-xs text-muted-foreground">
                  {claudeError ?? claudeUsage?.message}
                </p>
              ) : (
                <>
                  <div className="mt-2 flex items-baseline justify-between compact:mt-1">
                    <span className="text-2xl font-bold tracking-tight tabular-nums compact:text-base">
                      {liveElapsedSeconds != null ? formatDuration(liveElapsedSeconds) : "—:—"}
                    </span>
                    <span className="truncate text-xs text-muted-foreground">
                      {claudeUsage?.session_project ?? "no active session"}
                    </span>
                  </div>

                  <div className="mt-3 grid grid-cols-2 gap-2 text-xs compact:hidden">
                    <div className="flex items-center justify-between rounded-md bg-secondary/50 px-2 py-1">
                      <span className="text-muted-foreground">In (today)</span>
                      <span className="font-medium tabular-nums">
                        {formatTokens(claudeUsage?.today.input_tokens ?? 0)}
                      </span>
                    </div>
                    <div className="flex items-center justify-between rounded-md bg-secondary/50 px-2 py-1">
                      <span className="text-muted-foreground">Out (today)</span>
                      <span className="font-medium tabular-nums">
                        {formatTokens(claudeUsage?.today.output_tokens ?? 0)}
                      </span>
                    </div>
                    <div className="flex items-center justify-between rounded-md bg-secondary/50 px-2 py-1">
                      <span className="text-muted-foreground">Cache read</span>
                      <span className="font-medium tabular-nums">
                        {formatTokens(claudeUsage?.today.cache_read_tokens ?? 0)}
                      </span>
                    </div>
                    <div className="flex items-center justify-between rounded-md bg-secondary/50 px-2 py-1">
                      <span className="text-muted-foreground">Messages</span>
                      <span className="font-medium tabular-nums">
                        {claudeUsage?.today.messages ?? 0}
                      </span>
                    </div>
                  </div>
                </>
              )}
            </div>

            {!claudeError && claudeUsage?.available && (
              <div className="rounded-lg border p-3 compact:p-2">
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2 text-muted-foreground">
                    <Gauge className="h-4 w-4 compact:h-3.5 compact:w-3.5" />
                    <span className="text-sm font-medium text-foreground compact:text-xs">
                      5-Hour Limit
                    </span>
                  </div>

                  <Badge variant={claudeUsage.limit_window_active ? "secondary" : "outline"}>
                    {claudeUsage.limit_window_active ? "Window active" : "No active window"}
                  </Badge>
                </div>

                {claudeUsage.limit_window_active ? (
                  <>
                    <div className="mt-2 flex items-baseline justify-between compact:mt-1">
                      <span className="text-2xl font-bold tracking-tight tabular-nums compact:text-base">
                        {resetCountdownSeconds != null ? formatDuration(resetCountdownSeconds) : "—:—"}
                      </span>
                      <span className="text-xs text-muted-foreground">until reset</span>
                    </div>

                    <div className="mt-2 h-2 overflow-hidden rounded-full bg-secondary compact:mt-1 compact:h-1">
                      <div
                        className="h-full rounded-full bg-primary transition-all"
                        style={{ width: `${windowProgressPercent}%` }}
                      />
                    </div>

                    <div className="mt-2 flex items-center justify-between text-xs text-muted-foreground compact:hidden">
                      <span>Started {formatDate(claudeUsage.limit_window_started_at)}</span>
                      <span>Resets {formatDate(claudeUsage.limit_window_resets_at)}</span>
                    </div>

                    <div className="mt-3 grid grid-cols-2 gap-2 text-xs compact:hidden">
                      <div className="flex items-center justify-between rounded-md bg-secondary/50 px-2 py-1">
                        <span className="text-muted-foreground">In</span>
                        <span className="font-medium tabular-nums">
                          {formatTokens(claudeUsage.limit_window.input_tokens)}
                        </span>
                      </div>
                      <div className="flex items-center justify-between rounded-md bg-secondary/50 px-2 py-1">
                        <span className="text-muted-foreground">Out</span>
                        <span className="font-medium tabular-nums">
                          {formatTokens(claudeUsage.limit_window.output_tokens)}
                        </span>
                      </div>
                      <div className="flex items-center justify-between rounded-md bg-secondary/50 px-2 py-1 col-span-2">
                        <span className="text-muted-foreground">Messages</span>
                        <span className="font-medium tabular-nums">
                          {claudeUsage.limit_window.messages}
                        </span>
                      </div>
                    </div>
                  </>
                ) : (
                  <p className="mt-2 text-xs text-muted-foreground">
                    No messages in the last {LIMIT_WINDOW_HOURS} hours - your next message starts a
                    fresh window.
                  </p>
                )}
              </div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}
