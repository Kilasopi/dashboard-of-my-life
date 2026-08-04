export interface FinanceEntry {
    id: string;
    type: "expense" | "income" |"fixed_expense";
    name: string;
    amount: number;
    description: string | null;
}

export type FinanceEntryCreate = Omit<FinanceEntry, "id">;
