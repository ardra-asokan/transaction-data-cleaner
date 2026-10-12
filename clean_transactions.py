import csv
import json
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from collections import Counter


INPUT_FILE = "input.csv"
OUTPUT_FILE = "cleaned.csv"
REPORT_FILE = "report.json"

KNOWN_STATUSES = {"paid", "pending", "cancelled", "refund"}


def clean_name(value):
    """Clean up the customer name and keep the original value."""
    original = value or ""
    normalized = " ".join(original.split()).title()
    return original, normalized


def clean_date(value):
    """Convert supported date formats into YYYY-MM-DD."""
    value = (value or "").strip()

    formats = [
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
    ]

    for date_format in formats:
        try:
            parsed = datetime.strptime(value, date_format)
            return parsed.strftime("%Y-%m-%d"), None
        except ValueError:
            continue

    return value, "invalid_date"


def clean_amount(value):
    """Clean the amount and check whether it is valid."""
    value = (value or "").strip()

    if not value:
        return "", "missing_amount"

    value = re.sub(r"[\s₹$€£]", "", value)

    if not re.fullmatch(r"-?\d[\d.,]*", value):
        return value, "invalid_amount"

    if "," in value and "." in value:
        if value.rfind(",") > value.rfind("."):
            value = value.replace(".", "").replace(",", ".")
        else:
            value = value.replace(",", "")

    elif "," in value:
        if re.fullmatch(r"-?\d{1,3}(,\d{3})+", value):
            value = value.replace(",", "")
        elif value.count(",") == 1:
            value = value.replace(",", ".")
        else:
            return value, "invalid_amount"

    try:
        amount = Decimal(value)
    except InvalidOperation:
        return value, "invalid_amount"

    if not amount.is_finite():
        return value, "invalid_amount"

    if amount <= 0:
        return str(amount), "non_positive_amount"

    if amount != amount.quantize(Decimal("0.01")):
        return str(amount), "too_many_decimal_places"

    return f"{amount:.2f}", None


def clean_status(value):
    """Standardize the status and check if it is supported."""
    status = (value or "").strip().lower()

    if status not in KNOWN_STATUSES:
        return status, "unknown_status"

    return status, None


def process_row(row, row_number):
    """Clean a transaction row and collect any issues found."""
    issues = []

    original_name, customer_name = clean_name(
        row.get("customer_name", "")
    )
    transaction_id = (row.get("transaction_id") or "").strip()
    order_id = (row.get("order_id") or "").strip()

    if not transaction_id:
        issues.append("missing_transaction_id")

    if not customer_name:
        issues.append("missing_customer_name")

    if not order_id:
        issues.append("missing_order_id")

    transaction_date, date_issue = clean_date(
        row.get("transaction_date", "")
    )
    if date_issue:
        issues.append(date_issue)

    amount, amount_issue = clean_amount(row.get("amount", ""))
    if amount_issue:
        issues.append(amount_issue)

    status, status_issue = clean_status(row.get("status", ""))
    if status_issue:
        issues.append(status_issue)

    return {
        "row_number": row_number,
        "transaction_id": transaction_id,
        "customer_name_original": original_name,
        "customer_name": customer_name,
        "amount_original": row.get("amount", ""),
        "amount": amount,
        "transaction_date_original": row.get("transaction_date", ""),
        "transaction_date": transaction_date,
        "status_original": row.get("status", ""),
        "status": status,
        "order_id": order_id,
        "validity": "valid" if not issues else "invalid",
        "issues": issues,
        "duplicate_transaction_id": False,
        "duplicate_real_world_transaction": False,
    }


def main():
    """Read the transactions, clean the data, and create the report."""
    with open(INPUT_FILE, "r", newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)

        if reader.fieldnames is None:
            raise ValueError("Input CSV has no header.")

        required_columns = {
            "transaction_id", "customer_name", "amount",
            "transaction_date", "status", "order_id"
        }

        missing = required_columns - set(reader.fieldnames)
        if missing:
            raise ValueError(f"Missing CSV columns: {sorted(missing)}")

        raw_rows = list(reader)

    rows = [
        process_row(row, index)
        for index, row in enumerate(raw_rows, start=2)
    ]

    # Keep track of transaction IDs that have already appeared.
    seen_ids = set()

    # Use these details to identify transactions that may be duplicates.
    seen_fingerprints = set()

    for row in rows:
        transaction_id = row["transaction_id"]

        if transaction_id and transaction_id in seen_ids:
            row["duplicate_transaction_id"] = True
            row["issues"].append("duplicate_transaction_id")
        elif transaction_id:
            seen_ids.add(transaction_id)

        # Check for possible duplicates only when the key details are available.
        if (
            row["customer_name"]
            and row["order_id"]
            and row["transaction_date"]
            and row["amount"]
            and row["status"] in KNOWN_STATUSES
            and not any(
                issue in row["issues"]
                for issue in (
                    "invalid_date", "missing_amount", "invalid_amount",
                    "non_positive_amount", "too_many_decimal_places"
                )
            )
        ):
            fingerprint = (
                row["customer_name"].casefold(),
                row["order_id"],
                row["transaction_date"],
                row["amount"],
                row["status"],
            )

            if fingerprint in seen_fingerprints:
                row["duplicate_real_world_transaction"] = True
                row["issues"].append(
                    "possible_duplicate_real_world_transaction"
                )
            else:
                seen_fingerprints.add(fingerprint)

        # Mark duplicate records as invalid.
        if (
            row["duplicate_transaction_id"]
            or row["duplicate_real_world_transaction"]
        ):
            row["validity"] = "invalid"

    # Save all transactions, including the ones with validation issues.
    columns = [
        "row_number", "transaction_id",
        "customer_name_original", "customer_name",
        "amount_original", "amount",
        "transaction_date_original", "transaction_date",
        "status_original", "status", "order_id",
        "validity", "issues",
        "duplicate_transaction_id",
        "duplicate_real_world_transaction",
    ]

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()

        for row in rows:
            output_row = row.copy()
            output_row["issues"] = "; ".join(row["issues"])
            writer.writerow(output_row)

    valid_rows = [r for r in rows if r["validity"] == "valid"]
    invalid_rows = [r for r in rows if r["validity"] == "invalid"]

    duplicate_id_count = sum(
        r["duplicate_transaction_id"] for r in rows
    )
    duplicate_real_count = sum(
        r["duplicate_real_world_transaction"] for r in rows
    )

    # Calculate revenue from valid paid transactions only.
    total_revenue = sum(
        (
            Decimal(r["amount"])
            for r in valid_rows
            if r["status"] == "paid"
        ),
        Decimal("0.00"),
    )

    # Count how many times each issue appears in the data.
    issue_counts = Counter(
        issue for row in rows for issue in row["issues"]
    )

    report = {
        "input_rows": len(rows),
        "valid_rows": len(valid_rows),
        "invalid_rows": len(invalid_rows),
        "duplicate_counts": {
            "repeated_transaction_id_rows": duplicate_id_count,
            "possible_duplicate_real_world_rows": duplicate_real_count,
        },
        "total_revenue": f"{total_revenue:.2f}",
        "revenue_definition": (
            "Valid paid transactions, excluding duplicate records."
        ),
        "issue_counts": dict(sorted(issue_counts.items())),
    }

    # Make sure every input row is included in the results.
    assert len(rows) == len(raw_rows)
    assert len(rows) == len(valid_rows) + len(invalid_rows)

    assert all(
        row["validity"] == "invalid"
        for row in rows
        if row["duplicate_transaction_id"]
        or row["duplicate_real_world_transaction"]
    )

    with open(REPORT_FILE, "w", encoding="utf-8") as file:
        json.dump(report, file, indent=4)

    print("Data cleaning completed successfully!")
    print(f"Input rows: {len(rows)}")
    print(f"Valid rows: {len(valid_rows)}")
    print(f"Invalid rows: {len(invalid_rows)}")
    print(f"Total revenue: {total_revenue:.2f}")
    print("Generated files: cleaned.csv and report.json")


if __name__ == "__main__":
    main()
