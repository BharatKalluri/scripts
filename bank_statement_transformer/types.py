from dataclasses import dataclass
from datetime import date
from enum import Enum


class FileSource(Enum):
    HDFC_CSV_EXPORT_FROM_WEB = "HDFC CSV Export from HDFC Netbanking web portal"
    ICICI_CREDIT_CARD_STATEMENT = "ICICI Credit Card Statement CSV"


@dataclass
class Transaction:
    amount: float  # positive for credit, negative for debit
    narration: str
    ref_id: str
    date: date
    closing_balance: float
