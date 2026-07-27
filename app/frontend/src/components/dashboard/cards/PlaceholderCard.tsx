import { Plus } from "lucide-react";

import { Card } from "@/components/ui/card";

export function PlaceholderCard() {
  return (
    <Card className="items-center justify-center border border-dashed bg-transparent text-muted-foreground shadow-none ring-0">
      <Plus className="h-5 w-5" />
    </Card>
  );
}
