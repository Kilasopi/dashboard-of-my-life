import { useEffect, useMemo, useState } from "react";

export function useClock() {
  const [now, setNow] = useState(() => new Date());

  useEffect(() => {
    const intervalId = window.setInterval(() => {
      setNow(new Date());
    }, 1000);
    return () => {
      window.clearInterval(intervalId);
    };
  }, []);

  const time = useMemo(() => {
    return new Intl.DateTimeFormat("en-CA", {
      hour: "numeric",
      minute: "2-digit",
      second: "2-digit",
      hour12: true,
    }).format(now);
  }, [now]);

  const date = useMemo(() => {
    return new Intl.DateTimeFormat("en-CA", {
      weekday: "long",
      month: "long",
      day: "numeric",
      year: "numeric",
    }).format(now);
  }, [now]);

  const timeZone = useMemo(() => {
    return Intl.DateTimeFormat().resolvedOptions().timeZone;
  }, []);

  return { time, date, timeZone };
}
