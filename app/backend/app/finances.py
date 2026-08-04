from pydantic import BaseModel
from typing import Literal
from fastapi import APIRouter
from pathlib import Path
import uuid
import json

router = APIRouter(prefix="/finances", tags=["finances"])
DATA_DIR = Path(__file__).parent/ "data"
DATA_FILE = DATA_DIR / "finances.json"

class FinanceEntry(BaseModel):
    id: str
    type: Literal["expense", "income", "fixed_expense"]
    name: str
    amount: float
    description: str | None = None

def _load_entries() -> list[FinanceEntry]:
    entries = []
    if DATA_FILE.exists():
        with open(DATA_FILE, "r") as f:
            raw_data = json.load(f)
            for data in raw_data:
                entries.append(FinanceEntry.model_validate(data))
    return entries

def _save_entries(entries: list[FinanceEntry]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    input_entries = []
    with open(DATA_FILE, "w") as f:
        for entry in entries:
            input_entries.append(FinanceEntry.model_dump(entry))
        
        json.dump(input_entries, f)

# Creating an entry
@router.post("", response_model=FinanceEntry)
def create_finance_entry(entry: FinanceEntry) -> FinanceEntry:
    id = uuid.uuid4().hex
    entries = _load_entries()
    new_entry = FinanceEntry(
        id = id,
        type = entry.type,
        name = entry.name,
        amount = entry.amount,
        description = entry.description
    )
    entries.append(new_entry)
    _save_entries(entries)
    return new_entry

# Getting all entries
@router.get("", response_model=list[FinanceEntry])
def get_finances() -> list[FinanceEntry]:
    return _load_entries()

# Deleting an entry
@router.delete("/{entry_id}")
def delete_finance_entry(entry_id : str):
    entries = _load_entries()
    entries = [e for e in entries if e.id != entry_id]
    _save_entries(entries)

    return