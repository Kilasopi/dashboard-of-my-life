import { Badge } from "@/components/ui/badge";
import { DateTimeCard } from "./cards/DateTimeCard";

export function DashboardHeader() {
  return (
    <section className="grid gap-4 lg:grid-cols-[1fr_320px]">
        <div className="flex flex-col justify-end">
            <Badge variant="secondary" className="mb-3 w-fit">
                Local-first personal dashboard
            </Badge>

            <h1 className="text-4xl font-bold tracking-tight md:text-5xl">
                Dashboard of My Life
            </h1>

            <p className="mt-3 max-w-2xl text-muted-foreground">
                A personal command center for programming, sim racing, timers, routines, local device checks, and quality-of-life automations.
            </p>
        </div>

        <DateTimeCard />
    </section>
  );
}