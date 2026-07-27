import { Outlet } from "react-router-dom";

import { NavMenu } from "@/components/dashboard/NavMenu";
import { useClock } from "@/hooks/useClock";

export function AppShell() {
  const { time } = useClock();

  return (
    <div className="flex min-h-screen flex-col">
      <header className="flex items-center justify-between gap-4 border-b px-6 py-3 compact:px-3 compact:py-1.5">
        <div className="flex items-center gap-3 compact:gap-2">
          <NavMenu />
          <span className="font-semibold tracking-tight compact:text-xs">Dashboard of My Life</span>
        </div>

        <span className="text-sm font-medium tabular-nums text-muted-foreground compact:text-xs">{time}</span>
      </header>

      <main className="flex-1 px-6 py-6 md:px-10 compact:px-3 compact:py-2">
        <div className="mx-auto flex max-w-7xl flex-col gap-6 compact:gap-2">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
