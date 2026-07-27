import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export function NavTile({
  to,
  icon,
  label,
  description,
}: {
  to: string;
  icon: ReactNode;
  label: string;
  description: string;
}) {
  return (
    <Link to={to} className="block">
      <Card className="h-full transition-colors hover:bg-accent">
        <CardHeader>
          <div className="w-fit rounded-xl border bg-secondary p-2 compact:p-1">{icon}</div>

          <CardTitle className="compact:text-xs">{label}</CardTitle>

          <CardDescription className="compact:hidden">{description}</CardDescription>
        </CardHeader>
      </Card>
    </Link>
  );
}
