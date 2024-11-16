import csv
import hashlib
import io
import logging
from dataclasses import dataclass
from datetime import datetime, date
from typing import List, Optional

import streamlit as st
import pandas as pd

# Configure Streamlit page
st.set_page_config(
    page_title="Bank Statement to Firefly III Importer",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded",
)
from firefly_client import FireflyClient


@dataclass
class Transaction:
    amount: float  # positive for credit, negative for debit
    narration: str
    ref_id: str
    date: date
    closing_balance: float


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


def transform_hdfc_csv_to_transactions(file_contents: str) -> List[Transaction]:
    transactions = []
    csvfile = io.StringIO(file_contents)

    # skip empty line since HDFC statement has an empty line at the start
    next(csvfile)
    
    # Get number of columns from header
    first_line = next(csvfile).strip()
    num_cols = len([col for col in first_line.split(',') if col.strip()])
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
            narration_parts = row[1:2+extra_cols]
            merged_narration = ' '.join(part.strip() for part in narration_parts)
            # Reconstruct row with merged narration
            row = [row[0], merged_narration] + row[2+extra_cols:]
            
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

        # Generate hash if ref_id is '0'
        cleaned_ref_id = ref_id.strip()
        if cleaned_ref_id == '0':
            # Create a unique hash from narration and date
            hash_input = f"{date_only.isoformat()}:{narration.strip()}"
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


def import_transactions_to_firefly(transactions: List[Transaction], client: FireflyClient, account_id: int):
    for transaction in transactions:
        payee = extract_payee_from_hdfc_bank_statement_narration(transaction.narration)
        client.create_transaction(
            account_id=account_id,
            amount=transaction.amount,
            date=transaction.date,
            description=transaction.narration[:255],  # Firefly has a limit on description length
            notes=transaction.narration,
            external_id=transaction.ref_id,
            payee=payee
        )


def transactions_to_df(transactions: List[Transaction]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Date": t.date,
                "Amount": t.amount,
                "Description": t.narration,
                "Reference": t.ref_id,
                "Closing Balance": t.closing_balance,
            }
            for t in transactions
        ]
    )


def main():
    st.title("Bank Statement to Firefly III Importer")

    # Authentication in sidebar
    with st.sidebar:
        st.subheader("Authentication")
        with st.form("auth_form"):
            firefly_url = st.text_input("Firefly III URL")
            personal_access_token = st.text_input("Personal Access Token", type="password")
            auth_submit = st.form_submit_button("Connect")

    # Check if authenticated
    is_authenticated = auth_submit or (
        "firefly_url" in st.session_state and "personal_access_token" in st.session_state
    )

    if not is_authenticated:
        st.info(
            "👈 Please enter your Firefly III URL and Personal Access Token in the sidebar to get started."
        )
        return

    if is_authenticated:
        # Store credentials in session state
        if auth_submit:
            st.session_state["firefly_url"] = firefly_url
            st.session_state["personal_access_token"] = personal_access_token

        # Get accounts list for dropdown
        try:
            client = FireflyClient(
                st.session_state["firefly_url"],
                st.session_state["personal_access_token"]
            )
            accounts = client.get_accounts()
            account_names = [acc.name for acc in accounts]
        except Exception as e:
            st.error(f"Failed to connect to Actual: {str(e)}")
            return

        # Main import form
        with st.form("actual_config"):
            account_name = st.selectbox(
                "Account",
                options=account_names,
                help="Select the account to import transactions into",
            )
            data_source = st.selectbox(
                "Data Source",
                options=["HDFC CSV Export"],
                help="Select the format of your bank statement export",
            )
            uploaded_file = st.file_uploader("Choose bank statement file", type="csv")
            submit_button = st.form_submit_button("Import Transactions")

        if submit_button and uploaded_file is not None:
            # First verify Actual connection and account existence
            with st.spinner("Checking Firefly III connection and account..."):
                client = FireflyClient(firefly_url, personal_access_token)
                accounts = client.get_accounts()
                account = next((acc for acc in accounts if acc.name == account_name), None)
                if not account:
                    raise ValueError(
                        f"Account '{account_name}' not found in Firefly III. Please create it first."
                    )

            # Process and import transactions
            file_contents = uploaded_file.getvalue().decode()

            # Convert file contents to transactions based on selected data source
            # TODO: Convert to a factory setup so more data sources are supported
            if data_source == "HDFC CSV Export":
                transactions = transform_hdfc_csv_to_transactions(file_contents)
            else:
                raise ValueError(f"Unsupported data source: {data_source}")

            with st.spinner("Importing transactions to Firefly III..."):
                client = FireflyClient(firefly_url, personal_access_token)
                import_transactions_to_firefly(
                    transactions=transactions,
                    client=client,
                    account_id=account.id
                )

            # Show imported transactions
            st.success(
                f"Successfully imported {len(transactions)} transactions to Actual! 🎉"
            )
            st.subheader("Imported Transactions")
            st.dataframe(transactions_to_df(transactions), use_container_width=True)


if __name__ == "__main__":
    main()
