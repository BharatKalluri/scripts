# Bank statement transformer

A simple script to convert the messy exported csv bank statement to a clean and readable format.

## Notes

- Ref ID / UTR  can be zero or just a bunch of zeros sometime, so the script hashes date, amount and description to generate a unique reference id.