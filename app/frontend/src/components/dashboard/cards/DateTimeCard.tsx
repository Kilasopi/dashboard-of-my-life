import { useEffect, useMemo, useState } from "react";
import { Clock3 } from "lucide-react";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

export function DateTimeCard(){
    const [now, setNow] = useState(() => new Date());

    useEffect(() => {
        const intervalId = window.setInterval(() => {
            setNow(new Date());
        }, 1000);
        return() => {
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
        return new Intl.DateTimeFormat ("en-CA", {
            weekday: "long",
            month: "long",
            day: "numeric",
            year: "numeric",
        }).format(now);
    }, [now]);

    const timeZone = useMemo(() => {
        return Intl.DateTimeFormat().resolvedOptions().timeZone;
    }, []);

    return(
        <Card>
            <CardHeader className="pb-2">
                <div className="flex items-center justify-between gap-4">
                    <div>
                        <CardTitle className="text-base">Today</CardTitle>
                        <CardDescription>{timeZone}</CardDescription>
                    </div>

                    <div className="rounded-xl border bg-secondary p-2">
                        <Clock3 className="h-5 w-5" />
                    </div>
                </div>
            </CardHeader>

            <CardContent>
                <div className="text-3xl font-bold tracking-tight">{time}</div>
                <p className="mt-1 text-sm text-muted-foreground">{date}</p>
            </CardContent>
        </Card>
    );
}