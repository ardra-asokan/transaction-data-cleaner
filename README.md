# Transaction Data Cleaner

## Overview
A standalone Python program that cleans and validates transaction data from a CSV file. It creates a standardized CSV file along with a JSON summary report.

## Requirements
- Python 3.10 or newer
- Python standard library only; no third-party packages required

## How to Run
Place `input.csv` and `clean_transactions.py` in the same folder. Open a terminal in that folder and run:

```bash
python clean_transactions.py
```

After execution, the program generates `cleaned.csv` and `report.json`.

## Assumptions
- Customer names are cleaned by removing extra whitespace, reducing repeated spaces, and standardizing capitalization. Original names are preserved.
- Slash-separated dates are interpreted as day/month/year.
- Amounts must be positive and contain no more than two decimal places.
- Supported statuses are `paid`, `pending`, `cancelled`, and `refund`. Unrecognized statuses are flagged.
- Invalid records are retained in the output, along with explanations of the issues found.
- Repeated transaction IDs and likely duplicate transactions are flagged based on the implemented matching rules.
- Revenue includes valid paid transactions only, excluding records flagged as duplicates.

## Edge Cases Checked
- Invalid date: `2026-15-08`
- Invalid amount: `oops`
- Missing or non-positive amounts
- Repeated transaction IDs
- Possible duplicate transactions

## Output Files
- `cleaned.csv` — Contains original and normalized values, validity status, issue explanations, and duplicate flags.
- `report.json` — Summarizes input, valid and invalid row counts, duplicate counts, issue counts, and total revenue.