# 🧩 Canvas Rubric Importer Toolkit

This toolkit provides utilities for managing **Canvas rubrics** and automating their assignment to course assessments. It streamlines the process of linking the correct rubric to each assignment using SIS course IDs and smart matching logic.

## 📂 Project Overview

| File | Purpose |
|------|----------|
| `rubric_import.py` | Imports rubrics into Canvas from CSV templates or files. |
| `auto_assign_rubric.py` | Intelligently applies or replaces rubrics for assignments across multiple Canvas courses. Includes a dry-run mode for safe testing. |
| `filter_valid_courses.py` | Verifies a list of SIS course IDs against Canvas and filters out invalid ones. |

---

## ⚙️ Prerequisites

Before running any script, ensure you have:

1. **Python 3.8+** installed.
2. **A Canvas API token** with sufficient permissions.
3. A `.env` file in the project root containing:
   ```bash
   CANVAS_URL=https://your.canvas.instance
   CANVAS_TOKEN=your_api_token_here
   ```
4. Required dependencies installed:
   ```bash
   pip install requests python-dotenv
   ```

---

## 🧾 Scripts

### 1. `rubric_import.py`

Imports rubrics into Canvas from local CSV rubric files. Each rubric is uploaded to the specified Canvas course context.

**Usage:**
```bash
python rubric_import.py --csv rubrics_to_import.csv
```

**Example CSV format:**
```csv
course_id,file_path
12345,/path/to/rubric.csv
67890,/path/to/another_rubric.csv
```

This script uses the Canvas endpoint:
```
POST /api/v1/courses/:course_id/rubrics/upload
```

---

### 2. `auto_assign_rubric.py`

Automatically attaches the best-fitting rubric to assignments using smart matching based on assignment names and rubric titles.

It:
- Identifies upcoming online-upload assignments.
- Chooses the most relevant rubric (UG/PG detection).
- Adds or replaces rubrics based on keyword overlap.
- Supports a **dry-run** mode for previewing actions safely.

**Usage:**
```bash
python auto_assign_rubric.py --csv courses.csv --dry-run --log decisions.csv
```

**Options:**
| Flag | Description |
|------|--------------|
| `--csv` | Input CSV containing a `sis_course_id` column |
| `--dry-run` | Preview changes without modifying Canvas |
| `--threshold` | Minimum keyword overlap to trigger replacement (default: 1) |
| `--log` | Output CSV file to record all decisions |

**Decision Logic:**
- **ADD** – No rubric currently attached → apply best match.
- **REPLACE** – Current rubric has sufficient keyword overlap with best match.
- **SKIP** – Current rubric does not match → leave unchanged.

Uses the Canvas endpoint:
```
POST /api/v1/courses/:course_id/rubric_associations
```

---

### 3. `filter_valid_courses.py`

Validates SIS course IDs before bulk operations.

**Usage:**
```bash
python filter_valid_courses.py --csv sis_ids.csv --out valid_courses.csv --invalid invalid_courses.csv
```

**Options:**
| Flag | Description |
|------|--------------|
| `--csv` | Input CSV with a `sis_course_id` column |
| `--out` | Output CSV for valid courses (default: `valid_courses.csv`) |
| `--invalid` | Optional file for invalid course IDs |

The script checks each course via:
```
GET /api/v1/courses/sis_course_id:{id}
```

---

## 🧠 Recommended Workflow

1. **Filter your SIS course list**:
   ```bash
   python filter_valid_courses.py --csv all_courses.csv --out valid_courses.csv
   ```
2. **Import new rubrics** (if needed):
   ```bash
   python rubric_import.py --csv rubrics_to_import.csv
   ```
3. **Auto-assign rubrics** (start in dry-run mode):
   ```bash
   python auto_assign_rubric.py --csv valid_courses.csv --dry-run --log dryrun_decisions.csv
   ```
4. **Review the dry-run log**, then rerun without `--dry-run` to apply changes.

---

## 🧩 Example Output

**Dry run (auto_assign_rubric.py):**
```
🚀 Course 86243 (LIFE113-202526)
📅 3 upcoming online-upload assignments.
🧭 LIFE113 Essay (40%)
   Current rubric: None
   Suggested rubric: School of Biosciences Essay Rubric (Undergraduate) 25/26
   Overlap: 0 → Decision: ADD
   [DRY-RUN] Would POST to /rubric_associations with rubric_id=1123
```

**filter_valid_courses.py:**
```
🔍 Checking LIFE223-202526 ... ✅ Found
🔍 Checking LIFE999-202526 ... ❌ Not found
✅ Saved 12 valid courses to valid_courses.csv
⚠️ Saved 3 invalid courses to invalid_courses.csv
```

---

## 📘 License

This toolkit was developed by the **School of Biosciences, University of Liverpool**.  
© 2025 Instructure, Inc. API references included under fair use for integration documentation.

---

## 🧑‍💻 Author
**Dr. Robert Treharne**  
Senior Lecturer in Technology Enhanced Learning  
University of Liverpool  
📧 R.Treharne@liverpool.ac.uk

