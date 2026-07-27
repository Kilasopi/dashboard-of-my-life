import { useEffect, useMemo, useState } from "react";
import { Dialog, VisuallyHidden } from "radix-ui";
import { ExternalLink, Music2, Pause, Play, Radio, Settings, X } from "lucide-react";

import { API_BASE_URL } from "@/lib/api";

const POLL_INTERVAL_MS = 5_000;
const FALLBACK_COLOR = "#18181b";
const FALLBACK_TEXT_COLOR = "#ffffff";

type SpotifyStatus = {
  configured: boolean;
  connected: boolean;
  message: string;
  login_url: string;
  redirect_uri: string;
};

type SpotifyNowPlaying = {
  connected: boolean;
  is_playing: boolean;
  progress_ms: number;
  shuffle_state: boolean;
  repeat_state: string;
  item: {
    id: string | null;
    type: string;
    name: string;
    artists: string[];
    album: string | null;
    artwork_url: string | null;
    dominant_color: string;
    text_color: string;
    spotify_url: string | null;
    duration_ms: number;
  } | null;
  device: {
    id: string | null;
    name: string;
    type: string;
    is_active: boolean;
    volume_percent: number | null;
  } | null;
};

function isHexColor(value: string | undefined): value is string {
  return Boolean(value && /^#[0-9a-f]{6}$/i.test(value));
}

function formatTime(milliseconds: number) {
  const totalSeconds = Math.max(0, Math.floor(milliseconds / 1000));
  return `${Math.floor(totalSeconds / 60)}:${String(totalSeconds % 60).padStart(2, "0")}`;
}

function SpotifySettingsDialog({
  onClose,
  redirectUriDefault,
  onSaved,
}: {
  onClose: () => void;
  redirectUriDefault: string;
  onSaved: () => void;
}) {
  // Mounted only while the dialog is open (see the parent's conditional
  // render), so this initial state is naturally fresh on every open with no
  // effect needed to re-sync it.
  const [clientId, setClientId] = useState("");
  const [clientSecret, setClientSecret] = useState("");
  const [redirectUri, setRedirectUri] = useState(redirectUriDefault);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSave() {
    if (!clientId.trim() || !clientSecret.trim()) {
      setError("Client ID and secret are both required.");
      return;
    }

    setSaving(true);
    setError(null);

    try {
      const response = await fetch(`${API_BASE_URL}/spotify/credentials`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          client_id: clientId.trim(),
          client_secret: clientSecret.trim(),
          redirect_uri: redirectUri.trim() || undefined,
        }),
      });

      if (!response.ok) {
        const detail = await response.json().catch(() => null);
        throw new Error(detail?.detail ?? `Request failed with status ${response.status}`);
      }

      setClientId("");
      setClientSecret("");
      onSaved();
      onClose();
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "Could not save Spotify credentials.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog.Root
      open
      onOpenChange={(next) => {
        if (!next) onClose();
      }}
    >
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/60" />
        <Dialog.Content className="fixed top-1/2 left-1/2 z-50 w-[calc(100%-2rem)] max-w-md -translate-x-1/2 -translate-y-1/2 rounded-2xl border bg-card p-5 text-card-foreground shadow-xl outline-none">
          <div className="mb-4 flex items-center justify-between">
            <Dialog.Title className="text-base font-semibold">Spotify credentials</Dialog.Title>
            <Dialog.Close asChild>
              <button
                type="button"
                className="rounded-lg p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground"
                aria-label="Close"
              >
                <X className="h-4 w-4" />
              </button>
            </Dialog.Close>
          </div>

          <VisuallyHidden.Root asChild>
            <Dialog.Description>
              Update the Spotify app client ID and secret used to connect this dashboard.
            </Dialog.Description>
          </VisuallyHidden.Root>

          <p className="mb-4 text-xs text-muted-foreground">
            From your app at{" "}
            <a
              href="https://developer.spotify.com/dashboard"
              target="_blank"
              rel="noreferrer"
              className="underline"
            >
              developer.spotify.com/dashboard
            </a>
            . Saving this reconnects Spotify, so you'll need to hit Connect again afterward.
          </p>

          <div className="space-y-3">
            <label className="block text-sm">
              <span className="mb-1 block text-muted-foreground">Client ID</span>
              <input
                value={clientId}
                onChange={(event) => setClientId(event.target.value)}
                className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
                autoComplete="off"
                spellCheck={false}
              />
            </label>

            <label className="block text-sm">
              <span className="mb-1 block text-muted-foreground">Client Secret</span>
              <input
                type="password"
                value={clientSecret}
                onChange={(event) => setClientSecret(event.target.value)}
                className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
                autoComplete="off"
                spellCheck={false}
              />
            </label>

            <label className="block text-sm">
              <span className="mb-1 block text-muted-foreground">Redirect URI</span>
              <input
                value={redirectUri}
                onChange={(event) => setRedirectUri(event.target.value)}
                className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
                autoComplete="off"
                spellCheck={false}
              />
              <span className="mt-1 block text-xs text-muted-foreground">
                Must exactly match a Redirect URI registered on your Spotify app.
              </span>
            </label>
          </div>

          {error && <p className="mt-3 text-sm text-destructive">{error}</p>}

          <div className="mt-5 flex justify-end gap-2">
            <Dialog.Close asChild>
              <button
                type="button"
                className="rounded-lg border px-3 py-1.5 text-sm font-medium hover:bg-muted"
              >
                Cancel
              </button>
            </Dialog.Close>
            <button
              type="button"
              onClick={handleSave}
              disabled={saving}
              className="rounded-lg bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/80 disabled:opacity-50"
            >
              {saving ? "Saving…" : "Save"}
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

export function SpotifyCards() {
  const [status, setStatus] = useState<SpotifyStatus | null>(null);
  const [playback, setPlayback] = useState<SpotifyNowPlaying | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);

  async function refresh() {
    try {
      const statusResponse = await fetch(`${API_BASE_URL}/spotify/status`);
      if (!statusResponse.ok) throw new Error("Spotify status is unavailable");

      const nextStatus = (await statusResponse.json()) as SpotifyStatus;
      setStatus(nextStatus);

      if (!nextStatus.connected) {
        setPlayback(null);
        setError(null);
        return;
      }

      const playbackResponse = await fetch(`${API_BASE_URL}/spotify/now-playing`);
      if (!playbackResponse.ok) throw new Error("Now playing is unavailable");

      const nextPlayback = (await playbackResponse.json()) as SpotifyNowPlaying;
      setPlayback(nextPlayback);
      setError(null);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Spotify is unavailable");
    }
  }

  useEffect(() => {
    let cancelled = false;

    async function poll() {
      if (cancelled) return;
      await refresh();
    }

    void poll();
    const interval = window.setInterval(poll, POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, []);

  const item = playback?.item;
  const backgroundColor = isHexColor(item?.dominant_color) ? item.dominant_color : FALLBACK_COLOR;
  const textColor = isHexColor(item?.text_color) ? item.text_color : FALLBACK_TEXT_COLOR;
  const progress = useMemo(() => {
    if (!item?.duration_ms) return 0;
    return Math.min(100, Math.max(0, ((playback?.progress_ms ?? 0) / item.duration_ms) * 100));
  }, [item?.duration_ms, playback?.progress_ms]);

  const loginUrl = status?.login_url
    ? `${API_BASE_URL}${status.login_url.startsWith("/") ? status.login_url : `/${status.login_url}`}`
    : `${API_BASE_URL}/spotify/login`;

  return (
    <section
      className="relative isolate min-h-[28rem] overflow-hidden rounded-3xl p-5 shadow-2xl transition-colors duration-700 sm:p-8 compact:min-h-0 compact:p-4"
      style={{ backgroundColor, color: textColor }}
      aria-label="Spotify now playing"
    >
      {item?.artwork_url && (
        <div
          className="absolute inset-0 -z-20 scale-110 bg-cover bg-center opacity-25 blur-3xl transition-[background-image] duration-700"
          style={{ backgroundImage: `url(${item.artwork_url})` }}
          aria-hidden="true"
        />
      )}
      <div className="absolute inset-0 -z-10 bg-gradient-to-br from-white/10 via-transparent to-black/35" />

      <header className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-2 text-sm font-semibold tracking-wide">
          <span className="grid h-9 w-9 place-items-center rounded-full bg-black/20 backdrop-blur">
            <Music2 className="h-5 w-5" />
          </span>
          Spotify
        </div>
        <div className="flex items-center gap-2">
          <span className="flex items-center gap-2 rounded-full bg-black/20 px-3 py-1.5 text-xs font-medium backdrop-blur">
            <span
              className={`h-2 w-2 rounded-full ${playback?.is_playing ? "animate-pulse bg-green-400" : "bg-current opacity-50"}`}
            />
            {playback?.is_playing ? "Now playing" : item ? "Paused" : "Idle"}
          </span>
          <button
            type="button"
            onClick={() => setSettingsOpen(true)}
            className="grid h-9 w-9 place-items-center rounded-full bg-black/20 backdrop-blur transition-colors hover:bg-black/30"
            aria-label="Spotify settings"
          >
            <Settings className="h-4 w-4" />
          </button>
        </div>
      </header>

      {error ? (
        <div className="grid min-h-[22rem] place-items-center text-center compact:min-h-[13rem]">
          <div>
            <Radio className="mx-auto mb-3 h-9 w-9 opacity-70" />
            <h1 className="text-xl font-semibold">Spotify could not be reached</h1>
            <p className="mt-1 text-sm opacity-70">{error}</p>
          </div>
        </div>
      ) : !status ? (
        <div className="grid min-h-[22rem] place-items-center compact:min-h-[13rem]">
          <p className="animate-pulse text-sm font-medium opacity-70">Loading Spotify…</p>
        </div>
      ) : !status.connected ? (
        <div className="grid min-h-[22rem] place-items-center text-center compact:min-h-[13rem]">
          <div>
            <Music2 className="mx-auto mb-4 h-10 w-10 opacity-70" />
            <h1 className="text-2xl font-bold">Connect your Spotify</h1>
            <p className="mt-2 max-w-sm text-sm opacity-70">{status.message}</p>
            <a
              href={status.configured ? loginUrl : undefined}
              onClick={
                status.configured
                  ? undefined
                  : (event) => {
                      event.preventDefault();
                      setSettingsOpen(true);
                    }
              }
              className="mt-5 inline-flex cursor-pointer items-center gap-2 rounded-full bg-[#1ed760] px-5 py-2.5 text-sm font-bold text-black transition-transform hover:scale-105"
            >
              {status.configured ? "Connect Spotify" : "Set up Spotify"} <ExternalLink className="h-4 w-4" />
            </a>
            {!status.configured && (
              <p className="mt-3 text-xs opacity-60">Missing client ID/secret - click above to add them.</p>
            )}
          </div>
        </div>
      ) : !item ? (
        <div className="grid min-h-[22rem] place-items-center text-center compact:min-h-[13rem]">
          <div>
            <Pause className="mx-auto mb-3 h-10 w-10 opacity-60" />
            <h1 className="text-2xl font-bold">Nothing playing</h1>
            <p className="mt-2 text-sm opacity-70">Start something in Spotify and it will appear here.</p>
          </div>
        </div>
      ) : (
        <div className="mt-8 grid items-end gap-7 md:grid-cols-[minmax(14rem,22rem)_1fr] compact:mt-3 compact:grid-cols-[8rem_1fr] compact:gap-4">
          {item.artwork_url ? (
            <img
              src={item.artwork_url}
              alt={`${item.album ?? item.name} artwork`}
              className="aspect-square w-full rounded-2xl object-cover shadow-2xl ring-1 ring-white/15 compact:rounded-xl"
            />
          ) : (
            <div className="grid aspect-square w-full place-items-center rounded-2xl bg-black/20 ring-1 ring-white/15">
              <Music2 className="h-16 w-16 opacity-50" />
            </div>
          )}

          <div className="min-w-0 pb-1">
            <p className="mb-2 text-xs font-semibold uppercase tracking-[0.2em] opacity-60 compact:hidden">
              {item.type === "episode" ? "Episode" : "Now playing"}
            </p>
            <h1 className="truncate text-4xl font-black tracking-tight sm:text-5xl compact:text-2xl">
              {item.name}
            </h1>
            <p className="mt-2 truncate text-lg font-medium opacity-75 compact:mt-1 compact:text-sm">
              {item.artists.join(", ") || item.album || "Spotify"}
            </p>
            {item.album && <p className="mt-1 truncate text-sm opacity-55 compact:hidden">{item.album}</p>}

            <div className="mt-7 compact:mt-4">
              <div className="h-1.5 overflow-hidden rounded-full bg-black/25">
                <div
                  className="h-full rounded-full bg-current transition-[width] duration-500"
                  style={{ width: `${progress}%` }}
                />
              </div>
              <div className="mt-2 flex justify-between text-xs font-medium tabular-nums opacity-65">
                <span>{formatTime(playback.progress_ms)}</span>
                <span>{formatTime(item.duration_ms)}</span>
              </div>
            </div>

            <div className="mt-5 flex items-center justify-between gap-4 compact:mt-3">
              <div className="flex min-w-0 items-center gap-2 text-xs font-medium opacity-65">
                {playback.is_playing ? (
                  <Play className="h-4 w-4 fill-current" />
                ) : (
                  <Pause className="h-4 w-4 fill-current" />
                )}
                <span className="truncate">{playback.device?.name ?? "Spotify"}</span>
              </div>
              {item.spotify_url && (
                <a
                  href={item.spotify_url}
                  target="_blank"
                  rel="noreferrer"
                  className="rounded-full bg-black/20 p-2.5 transition-colors hover:bg-black/30"
                  aria-label="Open in Spotify"
                >
                  <ExternalLink className="h-4 w-4" />
                </a>
              )}
            </div>
          </div>
        </div>
      )}

      {settingsOpen && (
        <SpotifySettingsDialog
          onClose={() => setSettingsOpen(false)}
          redirectUriDefault={status?.redirect_uri ?? ""}
          onSaved={refresh}
        />
      )}
    </section>
  );
}
