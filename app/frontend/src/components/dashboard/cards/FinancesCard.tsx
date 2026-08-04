import type { FinanceEntry, FinanceEntryCreate } from "@/types/finances";
import { useEffect, useState } from "react";

import { API_BASE_URL } from "@/lib/api";

import {
  Card,
  CardAction,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

import { Badge } from "@/components/ui/badge";

const statusColours = {
  income: "default",
  expense: "destructive",
  fixed_expense: "outline",
} as const;

export function FinancesCard() {
  const [entries, setEntries] = useState<FinanceEntry[]>([]);
  const [error, setError] =useState<string | null>();

  useEffect(() => {
    fetch(`${API_BASE_URL}/finances`)
      .then((response) => response.json())
      .then((data) => setEntries(data))
  }, [])
  return (
    <div className="grid grid-cols-2">
      <div>
        <p>Form go here</p>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Finances</CardTitle>
        </CardHeader>
        <CardContent>
          {entries.map(entry => (
            <Card key={entry.id}>
              <CardHeader>
                <CardTitle>{entry.name}</CardTitle>
                <CardAction>
                  <Badge variant={statusColours[entry.type]}>{entry.type}</Badge>
                </CardAction>
              </CardHeader>
              <CardContent>
                <div className="text-3xl font-bold">${entry.amount.toFixed(2)} CAD</div>
                <div>{entry.description}</div>
              </CardContent>
            </Card>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}