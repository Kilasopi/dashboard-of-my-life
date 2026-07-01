import DashboardHeader from "@/components/dashboard/DashboardHeader"
import { ProgrammingCard } from "@/components/dashboard/cards/ProgrammingCard"

export default function Dashboard(){
    return(
        <main className="min-h-screen px-6 py-6 md:px-10">
            <div className="mx-auto flex max-w-7xl flex-col gap-6">
                <DashboardHeader />

                <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                    <ProgrammingCard />
                </section>
            </div>
        </main>
    )
}