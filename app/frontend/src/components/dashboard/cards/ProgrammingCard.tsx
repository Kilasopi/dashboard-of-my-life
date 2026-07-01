import { Code2 } from "lucide-react";

import { Badge } from '@/components/ui/badge' 
import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from '@/components/ui/card'

export function ProgrammingCard(){
    return(
        <Card>
            <CardHeader>
                <div className="flex items-start justify-between gap-4">
                    <div className="rounded-xl border bg-secondary p-2">
                        <Code2 className="h-5 w-5" />
                    </div>

                    <Badge variant="secondary">Active</Badge>
                </div>
                <CardTitle>
                    Programming Mode
                </CardTitle>

                <CardDescription>
                    Current project, branch, coding focus
                </CardDescription>
            </CardHeader>

            <CardContent className="space-y-3 text-sm">
                <InfoRow label="Project" value="dashboard-of-my-life"/>
                <InfoRow label="Branch" value="feature/dashboard-shell"/>
                <InfoRow label="Next Task" value="Build Dashboard Cards"/>
            </CardContent>
        </Card>
    );
}

function InfoRow({ label,value }: { label: string, value: string }) {
    return(
        <div className="flex items-center justify-between gap-4 rounded-lg border px-3 py-2">
            <span className="text-muted-foreground">{label}</span>
            <span className="text-right font-medium">{value}</span>
        </div>
    )
}

