#!/usr/bin/env python3
"""
apply_decisions.py

Reads a decisions.csv file (edited after running auto_assign_rubrics.py)
and applies rubric associations only for rows where decision == "ADD" or "REPLACE".

Usage:
    python apply_decisions.py --csv decisions.csv [--dry-run]
"""

import csv
import os
import requests
import argparse
from dotenv import load_dotenv
from time import sleep

# ---------- ENV ----------
load_dotenv()
CANVAS_URL = os.getenv("CANVAS_URL")
CANVAS_TOKEN = os.getenv("CANVAS_TOKEN")
if not CANVAS_URL or not CANVAS_TOKEN:
    raise ValueError("❌ Missing CANVAS_URL or CANVAS_TOKEN in .env file")

BASE_URL = f"{CANVAS_URL}/api/v1"
HEADERS = {"Authorization": f"Bearer {CANVAS_TOKEN}"}


# ---------- HELPERS ----------
def find_course_by_sis_id(sis_course_id):
    """Find Canvas course ID from SIS ID."""
    url = f"{BASE_URL}/courses/sis_course_id:{sis_course_id}"
    r = requests.get(url, headers=HEADERS)
    if r.status_code == 200:
        return r.json().get("id")
    return None


def get_rubrics(course_id):
    """Fetch all rubrics for a course."""
    rubrics = []
    url = f"{BASE_URL}/courses/{course_id}/rubrics"
    while url:
        r = requests.get(url, headers=HEADERS)
        if r.status_code != 200:
            break
        rubrics.extend(r.json())
        url = r.links.get("next", {}).get("url")
    return rubrics


def get_assignments(course_id):
    """Fetch all assignments for a course."""
    assignments = []
    url = f"{BASE_URL}/courses/{course_id}/assignments"
    while url:
        r = requests.get(url, headers=HEADERS)
        if r.status_code != 200:
            break
        assignments.extend(r.json())
        url = r.links.get("next", {}).get("url")
    return assignments


def apply_rubric(course_id, assignment_id, rubric_id, dry_run=False):
    """Create or replace a rubric association for an assignment."""
    url = f"{BASE_URL}/courses/{course_id}/rubric_associations"
    data = {
        "rubric_association[rubric_id]": rubric_id,
        "rubric_association[association_id]": assignment_id,
        "rubric_association[association_type]": "Assignment",
        "rubric_association[title]": f"Auto-linked rubric {rubric_id}",
        "rubric_association[use_for_grading]": True,
        "rubric_association[purpose]": "grading",
    }

    if dry_run:
        print(f"   [DRY-RUN] Would POST to {url} with rubric_id={rubric_id}")
        return True

    r = requests.post(url, headers=HEADERS, data=data)
    if r.status_code in (200, 201):
        print("   ✅ Rubric association created.")
        return True
    else:
        print(f"   ⚠️ API returned {r.status_code}: {r.text[:300]}")
        if "association" in r.text:
            print("   💡 Hint: check assignment ID and rubric context.")
        return False


# ---------- MAIN ----------
def main():
    parser = argparse.ArgumentParser(description="Apply rubric associations based on an edited decisions.csv file.")
    parser.add_argument("--csv", required=True, help="CSV file with sis_course_id, assignment, suggested_rubric, decision columns")
    parser.add_argument("--dry-run", action="store_true", help="Preview actions without modifying Canvas")
    args = parser.parse_args()

    with open(args.csv, newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    actionable = [r for r in rows if r["decision"].strip().upper() in ["ADD", "REPLACE"]]

    print(f"\n📋 Loaded {len(rows)} rows from {args.csv}")
    print(f"🔎 {len(actionable)} actionable rows (ADD/REPLACE)\n")

    for row in actionable:
        sis_id = row["sis_course_id"]
        assignment_name = row["assignment"]
        rubric_title = row["suggested_rubric"]

        course_id = find_course_by_sis_id(sis_id)
        if not course_id:
            print(f"⚠️ Course not found for {sis_id}")
            continue

        rubrics = get_rubrics(course_id)
        rubric_map = {r["title"]: r["id"] for r in rubrics}
        rubric_id = rubric_map.get(rubric_title)
        if not rubric_id:
            print(f"⚠️ Rubric '{rubric_title}' not found in course {sis_id}")
            continue

        assignments = get_assignments(course_id)
        matching_assignments = [a for a in assignments if a["name"].strip() == assignment_name.strip()]

        print(f"🚀 Course {sis_id} ({course_id}) — {assignment_name}")
        print(f"   Suggested rubric: {rubric_title}")

        if not matching_assignments:
            print(f"   ⚠️ No assignment named '{assignment_name}' found in this course.")
            continue

        a = matching_assignments[0]
        success = apply_rubric(course_id, a["id"], rubric_id, dry_run=args.dry_run)
        if args.dry_run:
            print("   [DRY-RUN] Would apply rubric.")
        elif success:
            print("   ✅ Applied successfully.")
        else:
            print("   ❌ Failed to apply.")

        sleep(0.5)

    print("\n✅ All actions processed.")


if __name__ == "__main__":
    main()
