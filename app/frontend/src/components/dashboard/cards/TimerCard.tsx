import { useEffect, useMemo, useState } from "react";
import { Timer } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

const DEFAULT_SECONDS = 25 * 60;

export function TimerCard() {
    const [secondsLeft, setSecondsLeft] = useState(DEFAULT_SECONDS);
    const [isRunning, setIsRunning] = useState(false);

    useEffect(() => {
        if (!isRunning) {
            return;
        }

        const intervalId = window.setInterval(() => {
            setSecondsLeft((currentSeconds) => {
            if (currentSeconds <= 1) {
                window.clearInterval(intervalId);
                setIsRunning(false);
                return 0;
            }

            return currentSeconds - 1;
            });
        }, 1000);

        return () => {
            window.clearInterval(intervalId);
        };
    }, [isRunning]);

    const formattedTime = useMemo(() => {
        const minutes = Math.floor(secondsLeft / 60);
        const seconds = secondsLeft % 60;

        return `${minutes.toString().padStart(2, "0")}:${seconds.toString().padStart(2,"0")}`;
    }, [secondsLeft]);

    const progressPercent = ((DEFAULT_SECONDS - secondsLeft) / DEFAULT_SECONDS) * 100;

    const clampedProgressPercent = Math.max(0, Math.min(progressPercent, 100));

    function handleStartPause() {
        if (secondsLeft <= 0) {
            setSecondsLeft(DEFAULT_SECONDS);
            setIsRunning(true);
            return;
        }

        setIsRunning((currentValue) => !currentValue);
    }

    function handleReset() {
        setIsRunning(false);
        setSecondsLeft(DEFAULT_SECONDS);
    }

    function handleAddFiveMinutes() {
        setSecondsLeft((currentSeconds) => currentSeconds + 5 * 60);
    }

    return(
        <Card>
            <CardHeader>
                <div className="w-fit rounded-xl border bg-secondary p-2">
                    <Timer className="h-5 w-5"/>
                </div>

                <CardTitle>Focus Timer</CardTitle>

                <CardDescription>
                    Start a simple focus session or break timer
                </CardDescription>
            </CardHeader>

            <CardContent className="space-y-5">
                <div>
                    <div className="text-5xl font-bold tracking-tight">
                        {formattedTime}
                    </div>

                    <p className="mt-1 text-sm text-muted-foreground">
                        {isRunning ? "Timer Running" : "Timer Paused"}
                    </p>
                </div>

                <div className="h-3 overflow-hidden rounded-full bg-secondary">
                    <div
                        className="h-full rounded-full bg-primary transition-all"
                        style={{ width: `${clampedProgressPercent}%`}}
                    />
                </div>

                <div className="flex flex-wrap gap-2">
                    <Button size="sm" onClick={handleStartPause}>
                        {isRunning ? "Pause" : "Start"}
                    </Button>

                    <Button size="sm" variant="secondary" onClick={handleReset}>
                        Reset
                    </Button>

                    <Button size="sm" variant="outline" onClick={handleAddFiveMinutes}>
                        +5 min
                    </Button>
                </div>
            </CardContent>
        </Card>
    );
}