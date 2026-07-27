import { Activity, Code2, Timer as TimerIcon } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { NavTile } from "@/components/dashboard/NavTile";
import { PlaceholderCard } from "@/components/dashboard/cards/PlaceholderCard";

export default function Overview() {
  return (
    <>
      <div className="flex flex-col compact:hidden">
        <Badge variant="secondary" className="mb-3 w-fit">
          Local-first personal dashboard
        </Badge>

        <h1 className="text-4xl font-bold tracking-tight md:text-5xl">Dashboard of My Life</h1>

        <p className="mt-3 max-w-2xl text-muted-foreground">
          A personal command center for programming, sim racing, timers, routines, local device
          checks, and quality-of-life automations.
        </p>
      </div>

      <section className="grid grid-cols-2 gap-4 compact:gap-2">
        <NavTile
          to="/programming"
          icon={<Code2 className="h-5 w-5 compact:h-3.5 compact:w-3.5" />}
          label="Programming Mode"
          description="Current project, branch, coding focus"
        />

        <NavTile
          to="/timer"
          icon={<TimerIcon className="h-5 w-5 compact:h-3.5 compact:w-3.5" />}
          label="Focus Timer"
          description="Start a simple focus session or break timer"
        />

        <NavTile
          to="/system-health"
          icon={<Activity className="h-5 w-5 compact:h-3.5 compact:w-3.5" />}
          label="System Health"
          description="Live hardware stats from this PC"
        />

        <PlaceholderCard />
      </section>
    </>
  );
}
