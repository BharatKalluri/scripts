import csv
import io
from datetime import datetime
from typing import Optional, List

from types import Transaction


def extract_payee_from_icici_credit_card_narration(narration: str) -> Optional[str]:
    """Extract payee name from ICICI credit card transaction narration.
    Takes the first part before comma as the payee name.
    """
    if not narration:
        return None

    parts = narration.split(",")
    if parts:
        return parts[0].strip()
    return None


def transform_icici_credit_card_statement_csv_to_transactions(
    file_contents: str,
) -> List[Transaction]:
    transactions = []
    csvfile = io.StringIO(file_contents)
    reader = csv.reader(csvfile)

    # Skip rows until we find transaction details section
    for row in reader:
        if row and row[1].strip() == "Transaction Details":
            try:
                next(reader)  # Skip column headers
            except StopIteration:
                return transactions
            break

    # Process all remaining rows as transactions
    for row in reader:
        if not row or len(row) < 9 or not row[2]:  # Check for date column
            continue

        date_str = row[2].strip().replace(",", "")
        date_obj = datetime.strptime(date_str, "%d%m%Y")

        description = row[3].strip()

        amount_str = row[6].strip()

        if not amount_str:
            continue

        # Remove "Dr." or "Cr." and convert to float
        amount_str = amount_str.replace(" Dr.", "").replace(" Cr.", "").replace(",", "")
        amount = float(amount_str)

        # Make debits negative and credits positive
        if "Dr." in row[6]:
            amount = -amount

        ref_num = row[8].strip()

        transactions.append(
            Transaction(
                amount=amount,
                narration=description,
                ref_id=ref_num,
                date=date_obj.date(),
                closing_balance=0.0,  # ICICI statements don't include running balance
            )
        )

    return transactions
