import csv
import hashlib
import io
import logging
from datetime import datetime
from typing import Optional, List

from types import Transaction


def extract_payee_from_hdfc_bank_statement_narration(narration: str) -> Optional[str]:
    """Extract payee name from transaction narration.

    For UPI transactions, extracts the second part after splitting by '-'.
    For NEFT/RTGS transactions, extracts the third part after splitting by '-'.
    For other transactions, returns empty string.
    """
    narration_lower = narration.lower()
    if narration_lower.startswith("upi-"):
        parts = narration.split("-")
        if len(parts) > 1:
            return parts[1].strip()
    elif narration_lower.startswith("neft") or narration_lower.startswith("rtgs"):
        parts = narration.split("-")
        if len(parts) > 2:
            return parts[2].strip()
    return None


def transform_hdfc_csv_to_transactions(
    file_contents: str,
) -> List[Transaction]:
    transactions = []
    csvfile = io.StringIO(file_contents)

    # skip empty line since HDFC statement has an empty line at the start
    next(csvfile)

    # Get number of columns from header
    first_line = next(csvfile).strip()
    num_cols = len([col for col in first_line.split(",") if col.strip()])
    reader = csv.reader(csvfile)

    for row_num, row in enumerate(reader, start=2):  # start=2 because we skipped header
        row = [el for el in row if el.strip()]
        if not row:
            logging.warning(f"Empty row found at line {row_num}")
            continue

        # Handle case where narration contains a comma
        if len(row) > num_cols:
            # Merge the split narration fields
            extra_cols = len(row) - num_cols
            narration_parts = row[1 : 2 + extra_cols]
            merged_narration = " ".join(part.strip() for part in narration_parts)
            # Reconstruct row with merged narration
            row = [row[0], merged_narration] + row[2 + extra_cols :]

        if len(row) < 7:
            logging.warning(
                f"Malformed row at line {row_num}. Expected 7 columns, got {len(row)}. Row content: {row}"
            )
            continue

        date_str, narration, _, debit_amt, credit_amt, ref_id, closing_balance = row

        # Convert date string to datetime
        date_obj = datetime.strptime(date_str.strip(), "%d/%m/%y")
        date_only = date_obj.date()

        # Handle amount (negative for debit, positive for credit)
        amount = float(credit_amt.strip() or "0") - float(debit_amt.strip() or "0")

        # Generate hash if ref_id is '0' or if the entire string is made out of zeros
        cleaned_ref_id = ref_id.strip()
        if cleaned_ref_id == "0" or all(c == "0" for c in cleaned_ref_id):
            # Create a unique hash from narration and date since the ref_id is 0
            hash_input = f"{date_only.isoformat()}:{amount}:{narration.strip()}"
            cleaned_ref_id = hashlib.sha256(hash_input.encode()).hexdigest()

        assert len(cleaned_ref_id) > 3, f"Invalid ref_id: {cleaned_ref_id}"

        transactions.append(
            Transaction(
                amount=amount,
                narration=narration.strip(),
                ref_id=cleaned_ref_id,
                date=date_only,
                closing_balance=float(closing_balance.strip()),
            )
        )

    return transactions
