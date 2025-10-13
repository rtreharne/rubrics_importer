import csv
import os
import requests
import argparse
from time import sleep
from dotenv import load_dotenv

# ---------- ENV ----------
load_dotenv()
CANVAS_URL = os.getenv("CANVAS_URL")
CANVAS_TOKEN = os.getenv("CANVAS_TOKEN")
if not CANVAS_URL or not CANVAS_TOKEN:
    raise ValueError("❌ Missing CANVAS_URL or CANVAS_TOKEN in .env file")

BASE_URL = f"{CANVAS_URL}/api/v1"
HEADERS = {"Authorization": f"Bearer {CANVAS_TOKEN}"}


# ---------- HELPERS ----------
def get_rubrics(course_id):
    """Fetch all rubrics from a given Canvas course."""
    rubrics = []
    url = f"{BASE_URL}/courses/{course_id}/rubrics"
    while url:
        r = requests.get(url, headers=HEADERS)
        if r.status_code != 200:
            break
        rubrics.extend(r.json())
        url = r.links.get("next", {}).get("url")
    return rubrics


def find_course_by_sis_id(sis_course_id):
    """Find Canvas course ID from SIS ID."""
    url = f"{BASE_URL}/courses/sis_course_id:{sis_course_id}"
    r = requests.get(url, headers=HEADERS)
    if r.status_code == 200:
        return r.json().get("id")
    else:
        print(f"⚠️ Could not find course for SIS ID: {sis_course_id}")
        return None


def wait_for_completion(progress_url):
    """Polls Canvas progress endpoint until migration completes."""
    print("⏳ Waiting for migration to complete...", end="", flush=True)
    while True:
        r = requests.get(progress_url, headers=HEADERS)
        r.raise_for_status()
        p = r.json()
        state = p.get("workflow_state")
        completion = p.get("completion", 0)
        print(".", end="", flush=True)
        if state in ["completed", "failed"]:
            print(f"\n➡️  Migration {state.upper()} ({completion}% done)")
            return state
        sleep(3)


# ---------- SELECTIVE IMPORT FLOW ----------
def import_selected_rubrics(source_id, target_id, rubric_match, dry_run=False, no_wait=False):
    """
    Perform a 2-step selective course copy importing only new rubrics
    that match the given substring.
    """
    # Step 0. Check for existing rubrics in target course
    target_rubrics = get_rubrics(target_id)
    existing_titles = {r["title"].strip().lower() for r in target_rubrics}

    # Step 1. Create migration in 'waiting_for_select'
    payload = {
        "migration_type": "course_copy_importer",
        "selective_import": "true",
        "settings[source_course_id]": str(source_id),
    }
    create_url = f"{BASE_URL}/courses/{target_id}/content_migrations"
    r = requests.post(create_url, headers=HEADERS, data=payload)
    if r.status_code not in (200, 201):
        print(f"❌ Failed to start selective import for {target_id}: {r.text}")
        return
    migration = r.json()
    migration_id = migration["id"]
    print(f"🟢 Migration created (ID {migration_id}, waiting_for_select)")

    # Step 2. List available rubrics from source for this migration
    list_url = f"{BASE_URL}/courses/{target_id}/content_migrations/{migration_id}/selective_data?type=rubrics"
    r = requests.get(list_url, headers=HEADERS)
    r.raise_for_status()
    rubric_items = r.json()

    if not rubric_items:
        print("⚠️ No rubrics found in source course.")
        return

    matching = [
        item for item in rubric_items
        if rubric_match.lower() in item["title"].lower()
    ]

    if not matching:
        print(f"⚠️ No rubrics matched '{rubric_match}'")
        return

    # Step 3. Filter out rubrics that already exist in the target course
    new_rubrics = [
        m for m in matching
        if m["title"].strip().lower() not in existing_titles
    ]

    if not new_rubrics:
        print(f"🟡 Skipping course {target_id} — all matching rubrics already exist.")
        return

    print(f"🎯 Found {len(new_rubrics)} new rubrics to import:")
    for m in new_rubrics:
        print(f"  - {m['title']}")

    if dry_run:
        print("[DRY-RUN] Skipping actual import.")
        return

    # Step 4. Build copy parameters for new rubrics
    copy_params = {m["property"]: 1 for m in new_rubrics}

    # Step 5. Trigger import
    update_url = f"{BASE_URL}/courses/{target_id}/content_migrations/{migration_id}"
    r = requests.put(update_url, headers=HEADERS, data=copy_params)
    if r.status_code not in (200, 201):
        print(f"❌ Failed to trigger rubric import for {target_id}: {r.text}")
        return

    updated = r.json()
    progress_url = updated.get("progress_url")

    if progress_url and not no_wait:
        wait_for_completion(progress_url)
    elif no_wait:
        print(f"🚀 Migration started for {target_id} (not waiting for completion).")
    else:
        print("⚠️ No progress URL returned; migration may have failed.")


# ---------- MAIN ----------
def main():
    parser = argparse.ArgumentParser(
        description="Selective import of new rubrics from a Canvas source course into target courses."
    )
    parser.add_argument("--source", required=True, help="Source course_id (numeric)")
    parser.add_argument("--match", required=True, help="Substring to match rubric titles (e.g. 202526)")
    parser.add_argument("--csv", required=True, help="CSV with sis_course_id column")
    parser.add_argument("--dry-run", action="store_true", help="Preview only (no import)")
    parser.add_argument("--no-wait", action="store_true", help="Do not wait for migrations to finish (fire and forget)")
    args = parser.parse_args()

    print(f"\n🔍 Fetching rubrics from source course {args.source}...")
    rubrics = get_rubrics(args.source)
    print(f"Found {len(rubrics)} total rubrics in source course.")

    with open(args.csv, newline="") as f:
        reader = csv.DictReader(f)
        sis_ids = [row["sis_course_id"] for row in reader]

    print(f"\n📋 Found {len(sis_ids)} destination courses from {args.csv}\n")

    for sis_id in sis_ids:
        target_id = find_course_by_sis_id(sis_id)
        if not target_id:
            continue
        print(f"\n🚀 Processing target course {target_id} (from {sis_id})")
        import_selected_rubrics(
            args.source,
            target_id,
            args.match,
            dry_run=args.dry_run,
            no_wait=args.no_wait,
        )
        sleep(0.5)  # avoid hammering API

    if args.dry_run:
        print("\n✅ Dry run complete (no changes made).")
    else:
        print("\n✅ All migrations processed.")


if __name__ == "__main__":
    main()
