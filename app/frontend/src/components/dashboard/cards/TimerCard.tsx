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
        <Card className="w-full">
            <CardHeader>
                <div className="w-fit rounded-xl border bg-secondary p-2 compact:p-1">
                    <Timer className="h-5 w-5 compact:h-3.5 compact:w-3.5"/>
                </div>

                <CardTitle className="compact:text-xs">Focus Timer</CardTitle>

                <CardDescription className="compact:hidden">
                    Start a simple focus session or break timer
                </CardDescription>
            </CardHeader>

            <CardContent className="flex flex-col items-center space-y-6 py-6 compact:space-y-1 compact:py-0">
                <div className="text-center">
                    <div className="text-7xl font-bold tracking-tight compact:text-xl md:text-8xl">
                        {formattedTime}
                    </div>

                    <p className="mt-2 text-sm text-muted-foreground compact:mt-0 compact:text-xs">
                        {isRunning ? "Timer Running" : "Timer Paused"}
                    </p>
                </div>

                <div className="h-3 w-full max-w-md overflow-hidden rounded-full bg-secondary compact:h-1.5">
                    <div
                        className="h-full rounded-full bg-primary transition-all"
                        style={{ width: `${clampedProgressPercent}%`}}
                    />
                </div>

                <div className="flex flex-wrap justify-center gap-2 compact:gap-1">
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