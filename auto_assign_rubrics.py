import csv
import os
import re
import requests
import argparse
from datetime import datetime, timezone
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


def numeric_code_from_sis(sis_course_id):
    """Extract numeric code (XXX) from ABCDXXX-YYYYYY."""
    m = re.search(r"[A-Z]{4}(\d{3})-", sis_course_id)
    return int(m.group(1)) if m else None


def word_overlap(a, b):
    """Count shared words between two strings."""
    a_words = set(re.findall(r"[A-Za-z]+", a.lower()))
    b_words = set(re.findall(r"[A-Za-z]+", b.lower()))
    return len(a_words & b_words)


def guess_best_rubric(assignment, rubrics, sis_course_id):
    """Decide which rubric fits an assignment."""
    code = numeric_code_from_sis(sis_course_id)
    level = "PG" if code and code > 400 else "UG"
    rubric_pool = [
        r for r in rubrics
        if ("Postgraduate" in r["title"] if level == "PG" else "Undergraduate" in r["title"])
    ]
    if not rubric_pool:
        return None

    scores = [(word_overlap(assignment["name"], r["title"]), r) for r in rubric_pool]
    scores.sort(key=lambda x: (-x[0], x[1]["title"].lower()))
    return scores[0][1] if scores else None


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
    parser = argparse.ArgumentParser(description="Auto-assign or replace Canvas rubrics intelligently.")
    parser.add_argument("--csv", required=True, help="CSV file with sis_course_id column")
    parser.add_argument("--dry-run", action="store_true", help="Preview only; do not apply rubrics")
    parser.add_argument("--threshold", type=int, default=1, help="Minimum word overlap to justify replacement")
    parser.add_argument("--log", help="Optional CSV file to save decisions")
    args = parser.parse_args()

    with open(args.csv, newline="") as f:
        reader = csv.DictReader(f)
        sis_ids = [row["sis_course_id"] for row in reader]

    now = datetime.now(timezone.utc)
    print(f"\n📋 Processing {len(sis_ids)} courses from {args.csv}\n")

    decisions = []  # for optional logging

    for sis_id in sis_ids:
        course_id = find_course_by_sis_id(sis_id)
        if not course_id:
            print(f"⚠️ Could not find course for SIS ID {sis_id}")
            continue

        print(f"\n🚀 Course {course_id} ({sis_id})")
        rubrics = get_rubrics(course_id)
        if not rubrics:
            print("⚠️ No rubrics found.")
            continue

        # Map rubric titles to IDs for this course
        rubric_map = {r["title"]: r["id"] for r in rubrics}

        assignments = get_assignments(course_id)
        upcoming = [
            a for a in assignments
            if "online_upload" in a.get("submission_types", [])
            and a.get("due_at")
            and datetime.fromisoformat(a["due_at"].replace("Z", "+00:00")) > now
        ]

        print(f"📅 {len(upcoming)} upcoming online-upload assignments.")

        for a in upcoming:
            rubric_settings = a.get("rubric_settings", {})
            current_rubric = (
                rubric_settings.get("title")
                or rubric_settings.get("rubric_title")
                or ""
            )

            best = guess_best_rubric(a, rubrics, sis_id)
            best_title = best["title"] if best else None
            decision, overlap = "NO MATCH", 0

            if not best:
                print(f"⚠️ No suitable rubric for {a['name']}")
                continue

            if not current_rubric:
                decision = "ADD"
            else:
                overlap = word_overlap(current_rubric or "", best_title or "")
                decision = "REPLACE" if overlap >= args.threshold else "SKIP"

            print(f"🧭 {a['name']}")
            print(f"   Current rubric: {current_rubric or 'None'}")
            print(f"   Suggested rubric: {best_title}")
            print(f"   Overlap: {overlap} → Decision: {decision}")

            decisions.append({
                "sis_course_id": sis_id,
                "assignment": a["name"],
                "current_rubric": current_rubric or "",
                "suggested_rubric": best_title or "",
                "overlap": overlap,
                "decision": decision,
            })

            if decision in ["ADD", "REPLACE"] and best_title:
                rubric_id = rubric_map.get(best_title)
                if rubric_id:
                    success = apply_rubric(course_id, a["id"], rubric_id, dry_run=args.dry_run)
                    status = "✅ Applied" if success else "❌ Failed"
                else:
                    status = f"⚠️ No rubric titled '{best_title}' found in course"
                    success = False
                if args.dry_run:
                    status = "[DRY-RUN] Would apply"
                print(f"   {status}")

        sleep(0.5)

    if args.log:
        with open(args.log, "w", newline="") as f:
            fieldnames = ["sis_course_id", "assignment", "current_rubric", "suggested_rubric", "overlap", "decision"]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(decisions)
        print(f"\n🧾 Decisions logged to {args.log}")

    print("\n✅ All courses processed.")


if __name__ == "__main__":
    main()
