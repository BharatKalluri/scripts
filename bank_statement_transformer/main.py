from typing import List, Optional

import streamlit as st
import pandas as pd

from transformers.hdfc_bank_statement_csv import extract_payee_from_hdfc_bank_statement_narration, \
    transform_hdfc_csv_to_transactions
from transformers.icici_credit_card_statement_csv import extract_payee_from_icici_credit_card_narration, \
    transform_icici_credit_card_statement_csv_to_transactions
from types import FileSource, Transaction

# Configure Streamlit page
st.set_page_config(
    page_title="Bank Statement Parser",
    page_icon="🏦",
    layout="wide",
)


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
        ],
        help="Select the format of your bank statement export",
    )

    uploaded_file = st.file_uploader("Choose bank statement file", type="csv")

    if uploaded_file is not None:
        try:
            # Parse transactions
            file_contents = uploaded_file.getvalue().decode()
            if data_source == FileSource.HDFC_CSV_EXPORT_FROM_WEB.value:
                payee_extractor = extract_payee_from_hdfc_bank_statement_narration
                transactions = transform_hdfc_csv_to_transactions(
                    file_contents,
                )
            elif data_source == FileSource.ICICI_CREDIT_CARD_STATEMENT.value:
                payee_extractor = extract_payee_from_icici_credit_card_narration
                transactions = (
                    transform_icici_credit_card_statement_csv_to_transactions(
                        file_contents,
                    )
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
