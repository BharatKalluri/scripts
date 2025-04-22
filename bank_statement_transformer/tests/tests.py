from datetime import date

from transformers.hdfc_bank_statement_csv import extract_payee_from_hdfc_bank_statement_narration, \
    transform_hdfc_csv_to_transactions
from types import Transaction


def test_extract_payee_from_narration():
    # Test UPI transaction with multiple parts
    assert extract_payee_from_hdfc_bank_statement_narration("UPI-ZOMATO LTD-ZOMATO-ORDER@PTYBL-YESB0PTMUPI-430213318243-ZOMATO PAYMENT") == "ZOMATO LTD"
    
    # Test simple UPI transaction
    assert extract_payee_from_hdfc_bank_statement_narration("UPI-John Doe-Reference") == "John Doe"
    
    # Test NEFT transaction
    assert extract_payee_from_hdfc_bank_statement_narration("NEFT DR-PUNB0498700-random name-NETBANK") == "random name"
    
    # Test RTGS transaction
    assert extract_payee_from_hdfc_bank_statement_narration("RTGS-SBIN000123-ACME Corp-Transfer") == "ACME Corp"
    
    # Test non-UPI/NEFT/RTGS transaction
    assert extract_payee_from_hdfc_bank_statement_narration("ATM Withdrawal") == ""
    
    # Test empty string
    assert extract_payee_from_hdfc_bank_statement_narration("") == ""


def test_transform_single_transaction():
    sample_csv = """Date,Narration,Value Dat,Debit Amount,Credit Amount,Chq/Ref Number,Closing Balance
01/10/24,ACH C- NATIONAL HIGHWAYS AU-1320825,01/10/24,0,15296,9053114532,51807.2"""

    # Test the transform function
    transactions = transform_hdfc_csv_to_transactions(sample_csv)

    assert len(transactions) == 1
    transaction = transactions[0]
    assert isinstance(transaction, Transaction)
    assert transaction.amount == 15296.0
    assert transaction.narration == "ACH C- NATIONAL HIGHWAYS AU-1320825"
    assert transaction.ref_id == "9053114532"
    assert transaction.date == date(2024, 10, 1)
    assert transaction.closing_balance == 51807.2
