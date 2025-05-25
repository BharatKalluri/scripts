import csv
import hashlib
import io
import logging
from dataclasses import dataclass
from datetime import datetime, date
from enum import Enum
from typing import List, Optional

import streamlit as st
import pandas as pd
import tempfile
import camelot

# Configure Streamlit page
st.set_page_config(
    page_title="Bank Statement Parser",
    page_icon="🏦",
    layout="wide",
)


class FileSource(Enum):
    HDFC_CSV_EXPORT_FROM_WEB = "HDFC CSV Export from HDFC Netbanking web portal"
    ICICI_CREDIT_CARD_STATEMENT = "ICICI Credit Card Statement CSV"
    HDFC_CREDIT_CARD_STATEMENT_PDF = "HDFC Credit Card Statement PDF"


@dataclass
class Transaction:
    amount: float  # positive for credit, negative for debit
    narration: str
    ref_id: str
    date: date
    closing_balance: float


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

def extract_payee_from_hdfc_credit_card_narration(narration: str) -> Optional[str]:
    return None


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

def transform_hdfc_credit_card_statement_to_transactions(
    file_contents: bytes,
) -> List[Transaction]:
    """Extract transactions from HDFC credit card statement PDF.
    
    Args:
        file_contents: Raw PDF file contents as bytes
        
    Returns:
        List of Transaction objects
    """
    
    transactions = []
    
    # Create a temporary file to save the PDF content
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_file:
        temp_file.write(file_contents)
        temp_file_path = temp_file.name
        # Try multiple table extraction methods for page 1
        # Method 1: Lattice mode with specific settings
        tables_lattice = camelot.read_pdf(
            temp_file_path,
            pages='all',
            flavor='lattice',
            line_scale=40,  # Increase line detection sensitivity
            process_background=True
        )

        # Method 2: Stream mode with specific settings
        tables_stream = camelot.read_pdf(
            temp_file_path,
            pages='all',
            flavor='stream',
            edge_tol=500,  # More tolerant of imperfect table edges
            row_tol=10     # More tolerant of row variations
        )

        # Filter for tables containing "Domestic Transactions"
        domestic_transaction_dfs = []

        # Process lattice tables
        if tables_lattice and len(tables_lattice) > 0:
            for table in tables_lattice:
                if table.df.shape[0] > 1:
                    # Check if "Domestic Transactions" is in the first row
                    first_row = ' '.join(str(cell) for cell in table.df.iloc[0])
                    if "Domestic Transactions" in first_row:
                        # Skip the first 4 rows
                        if table.df.shape[0] > 4:
                            domestic_transaction_dfs.append(table.df.iloc[4:].reset_index(drop=True))

        # Process stream tables
        if tables_stream and len(tables_stream) > 0:
            for table in tables_stream:
                if table.df.shape[0] > 1:
                    # Check if "Domestic Transactions" is in the first row
                    first_row = ' '.join(str(cell) for cell in table.df.iloc[0])
                    if "Domestic Transactions" in first_row:
                        # Skip the first 4 rows
                        if table.df.shape[0] > 4:
                            domestic_transaction_dfs.append(table.df.iloc[4:].reset_index(drop=True))

        # Combine all domestic transaction dataframes
        if domestic_transaction_dfs:
            combined_df = pd.concat(domestic_transaction_dfs, ignore_index=True)
            # Remove duplicate rows that might be present in multiple tables
            combined_df = combined_df.drop_duplicates()
        else:
            logging.warning("No 'Domestic Transactions' tables found in the PDF")
            return transactions

        # Skip header row if present
        if len(combined_df) > 1:
            # Assuming standard HDFC credit card statement format
            # Process each row in the table
            for _, row in combined_df.iterrows():
                # Extract date, description, reward points, and amount
                if len(row) >= 3:  # Ensure we have all four columns
                    date_str = row[0].strip()
                    description = row[1].strip()
                    # Skip reward points (index 2) if reward points column is present, else use col 2
                    amount_str = row[3].strip().replace(',', '') if len(row)>3 else row[2].strip().replace(',', '')

                    # Parse date
                    date_part = date_str.split(' ')[0]
                    date_obj = datetime.strptime(date_part, "%d/%m/%Y")

                    # Parse amount (check for 'Cr' suffix)
                    is_credit = 'Cr' in amount_str
                    clean_amount = amount_str.replace('Cr', '').strip()
                    amount = float(clean_amount)

                    # For credit card statements:
                    # - If marked with 'Cr', it's a credit (positive)
                    # - Otherwise, it's a debit (negative)
                    if not is_credit:
                        amount = -amount

                    # Generate reference ID from transaction details
                    hash_input = f"{date_obj.date().isoformat()}:{amount}:{description}"
                    ref_id = hashlib.sha256(hash_input.encode()).hexdigest()

                    transactions.append(
                        Transaction(
                            amount=amount,
                            narration=description,
                            ref_id=ref_id,
                            date=date_obj.date(),
                            closing_balance=0.0,  # Credit card statements typically don't include running balance
                        )
                    )
            
    return transactions


def transactions_to_df(
    transactions: List[Transaction], payee_extractor: Optional[callable] = None
) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Date": t.date,
                "Amount": t.amount,
                "Payee": payee_extractor(t.narration) if payee_extractor else None,
                "Description": t.narration,
                "Reference": t.ref_id,
                "Closing Balance": t.closing_balance,
            }
            for t in transactions
        ]
    )


def main():
    st.title("Bank Statement Parser")

    data_source = st.selectbox(
        "Data Source",
        options=[
            FileSource.HDFC_CSV_EXPORT_FROM_WEB.value,
            FileSource.ICICI_CREDIT_CARD_STATEMENT.value,
            FileSource.HDFC_CREDIT_CARD_STATEMENT_PDF.value,
        ],
        help="Select the format of your bank statement export",
    )

    uploaded_file = st.file_uploader("Choose bank statement file", type=["csv", "pdf"])

    if uploaded_file is not None:
        try:
            # Parse transactions
            if data_source == FileSource.HDFC_CSV_EXPORT_FROM_WEB.value:
                payee_extractor = extract_payee_from_hdfc_bank_statement_narration
                file_contents = uploaded_file.getvalue().decode()
                transactions = transform_hdfc_csv_to_transactions(
                    file_contents,
                )
            elif data_source == FileSource.ICICI_CREDIT_CARD_STATEMENT.value:
                payee_extractor = extract_payee_from_icici_credit_card_narration
                file_contents = uploaded_file.getvalue().decode()
                transactions = (
                    transform_icici_credit_card_statement_csv_to_transactions(
                        file_contents,
                    )
                )
            elif data_source == FileSource.HDFC_CREDIT_CARD_STATEMENT_PDF.value:
                payee_extractor = extract_payee_from_hdfc_credit_card_narration
                # For PDF files, use bytes directly without decoding
                file_contents_bytes = uploaded_file.getvalue()
                transactions = transform_hdfc_credit_card_statement_to_transactions(
                    file_contents_bytes,
                )
            else:
                raise ValueError(f"Unsupported data source: {data_source}")

            st.success("Parsed transactions successfully! 🎉")
            st.subheader("Parsed Transactions")
            st.dataframe(
                transactions_to_df(transactions, payee_extractor=payee_extractor),
                use_container_width=True,
            )

        except Exception as e:
            st.error(f"Error parsing file: {str(e)}")
            print(e)
            raise e


if __name__ == "__main__":
    main()
