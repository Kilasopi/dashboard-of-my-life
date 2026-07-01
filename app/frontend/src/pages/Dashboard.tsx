import { DashboardHeader } from "@/components/dashboard/DashboardHeader"
import { ProgrammingCard } from "@/components/dashboard/cards/ProgrammingCard"
import { TimerCard } from "@/components/dashboard/cards/TimerCard"

export default function Dashboard(){
    return(
        <main className="min-h-screen px-6 py-6 md:px-10">
            <div className="mx-auto flex max-w-7xl flex-col gap-6">
                <DashboardHeader />

                <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                    <ProgrammingCard />
                    <TimerCard />
                </section>
            </div>
        </main>
    )
}