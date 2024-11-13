from datetime import date

from main import transform_hdfc_csv_to_transactions, Transaction


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
