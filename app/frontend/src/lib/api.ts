// Relative by default so requests always hit whatever origin served this page -
// correct for the packaged desktop app (single process/port) and for dev servers
// via the Vite proxy below. Only override VITE_API_BASE_URL for a genuinely
// different-origin backend.
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";
