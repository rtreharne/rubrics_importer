import csv
import os
import requests
import argparse
from dotenv import load_dotenv

# ---------- ENV ----------
load_dotenv()
CANVAS_URL = os.getenv("CANVAS_URL")
CANVAS_TOKEN = os.getenv("CANVAS_TOKEN")

if not CANVAS_URL or not CANVAS_TOKEN:
    raise ValueError("❌ Missing CANVAS_URL or CANVAS_TOKEN in .env file")

BASE_URL = f"{CANVAS_URL}/api/v1"
HEADERS = {"Authorization": f"Bearer {CANVAS_TOKEN}"}


def course_exists(sis_id):
    """Check if course exists on Canvas using SIS ID."""
    url = f"{BASE_URL}/courses/sis_course_id:{sis_id}"
    r = requests.get(url, headers=HEADERS)
    return r.status_code == 200


def main():
    parser = argparse.ArgumentParser(
        description="Filter valid Canvas courses from a CSV of SIS IDs."
    )
    parser.add_argument("--csv", required=True, help="Input CSV with 'sis_course_id' column")
    parser.add_argument("--out", default="valid_courses.csv", help="Output CSV filename (default: valid_courses.csv)")
    parser.add_argument("--invalid", help="Optional file to save invalid courses")
    args = parser.parse_args()

    valid_rows, invalid_rows = [], []

    with open(args.csv, newline="") as f:
        reader = csv.DictReader(f)
        if "sis_course_id" not in reader.fieldnames:
            raise ValueError("❌ CSV must contain a 'sis_course_id' column.")

        for row in reader:
            sis_id = row["sis_course_id"].strip()
            if not sis_id:
                continue
            print(f"🔍 Checking {sis_id} ... ", end="")
            if course_exists(sis_id):
                print("✅ Found")
                valid_rows.append(row)
            else:
                print("❌ Not found")
                invalid_rows.append(row)

    # Save valid
    with open(args.out, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["sis_course_id"])
        writer.writeheader()
        writer.writerows(valid_rows)
    print(f"\n✅ Saved {len(valid_rows)} valid courses to {args.out}")

    # Optionally save invalid
    if args.invalid:
        with open(args.invalid, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["sis_course_id"])
            writer.writeheader()
            writer.writerows(invalid_rows)
        print(f"⚠️ Saved {len(invalid_rows)} invalid courses to {args.invalid}")


if __name__ == "__main__":
    main()
