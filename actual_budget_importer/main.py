import csv
import io
import logging
from dataclasses import dataclass
from datetime import datetime, date
from typing import List

import streamlit as st
import pandas as pd

# Configure Streamlit page
st.set_page_config(
    page_title="Bank Statement to Actual Budget Importer",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded",
)
from actual import Actual
from actual.queries import reconcile_transaction, get_account, get_accounts


@dataclass
class Transaction:
    amount: float  # positive for credit, negative for debit
    narration: str
    ref_id: str
    date: date
    closing_balance: float


def transform_hdfc_csv_to_transactions(file_contents: str) -> List[Transaction]:
    transactions = []
    csvfile = io.StringIO(file_contents)
    # Skip the header row
    next(csvfile)
    reader = csv.reader(csvfile)
    for row_num, row in enumerate(reader, start=2):  # start=2 because we skipped header
        if not row:
            logging.warning(f"Empty row found at line {row_num}")
            continue
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

        transactions.append(
            Transaction(
                amount=amount,
                narration=narration.strip(),
                ref_id=ref_id.strip(),
                date=date_only,
                closing_balance=float(closing_balance.strip()),
            )
        )

    return transactions


def upsert_transactions_to_actual(transactions: List[Transaction], session, account):
    for transaction in transactions:
        # Use reconcile_transaction for both new and existing transactions
        reconcile_transaction(
            s=session,
            amount=transaction.amount,
            # TODO: payee is not narration, but we don't really have a choice here :(
            payee=transaction.narration,
            imported_id=transaction.ref_id,
            date=transaction.date,
            account=account,
            notes=transaction.narration,
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
    st.title("Bank Statement to Actual Budget Importer")

    # Authentication in sidebar
    with st.sidebar:
        st.subheader("Authentication")
        with st.form("auth_form"):
            actual_url = st.text_input("Actual Server URL")
            actual_password = st.text_input("Actual Password", type="password")
            auth_submit = st.form_submit_button("Connect")

    # Check if authenticated
    is_authenticated = auth_submit or (
        "actual_url" in st.session_state and "actual_password" in st.session_state
    )

    if not is_authenticated:
        st.info(
            "👈 Please enter your Actual server URL and password in the sidebar to get started."
        )
        return

    if is_authenticated:
        # Store credentials in session state
        if auth_submit:
            st.session_state["actual_url"] = actual_url
            st.session_state["actual_password"] = actual_password

        # Get accounts list for dropdown
        try:
            with Actual(
                st.session_state["actual_url"],
                password=st.session_state["actual_password"],
            ) as actual:
                actual.set_file(actual.list_user_files().data[0])
                actual.download_budget()
                accounts = get_accounts(actual.session)
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
            with st.spinner("Checking Actual connection and account..."):
                with Actual(actual_url, password=actual_password) as actual:
                    actual.set_file(actual.list_user_files().data[0])
                    actual.download_budget()
                    account = get_account(actual.session, name=account_name)
                if not account:
                    raise ValueError(
                        f"Account '{account_name}' not found in Actual. Please create it first."
                    )

            # Process and import transactions
            file_contents = uploaded_file.getvalue().decode()

            # Convert file contents to transactions based on selected data source
            # TODO: Convert to a factory setup so more data sources are supported
            if data_source == "HDFC CSV Export":
                transactions = transform_hdfc_csv_to_transactions(file_contents)
            else:
                raise ValueError(f"Unsupported data source: {data_source}")

            with st.spinner("Importing transactions to Actual..."):
                with Actual(actual_url, password=actual_password) as actual:
                    actual.set_file(actual.list_user_files().data[0])
                    actual.download_budget()
                    upsert_transactions_to_actual(
                        transactions=transactions,
                        session=actual.session,
                        account=account,
                    )
                    actual.commit()

            # Show imported transactions
            st.success(
                f"Successfully imported {len(transactions)} transactions to Actual! 🎉"
            )
            st.subheader("Imported Transactions")
            st.dataframe(transactions_to_df(transactions), use_container_width=True)


if __name__ == "__main__":
    main()
