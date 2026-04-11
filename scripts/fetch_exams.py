#!/usr/bin/env python3
"""
fetch_exams.py — Fetch study guide markdown from Microsoft Learn for all tracked exams.

For each exam in exams.json:
1. Fetch the study guide page as markdown
2. Parse YAML front matter for metadata (updated_at, git_commit_id)
3. Extract skills measured (objectives with weights)
4. Extract the change log (if present)
5. Save structured data to site/current_state.json
"""

import json
import os
import re
import sys
import time
import hashlib
import requests
import yaml

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SITE_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "site")
EXAMS_CONFIG = os.path.join(SCRIPT_DIR, "exams.json")

STUDY_GUIDE_URL = "https://learn.microsoft.com/en-us/certifications/resources/study-guides/{code}"
EXAM_PAGE_URL = "https://learn.microsoft.com/en-us/credentials/certifications/exams/{code_lower}/"

# Polite delay between requests (seconds)
REQUEST_DELAY = 1.5
REQUEST_TIMEOUT = 30

HEADERS = {
    "Accept": "text/markdown",
    "User-Agent": "CertTracker/1.0 (aguidetocloud.com; educational tool)"
}


def load_exam_config():
    with open(EXAMS_CONFIG, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["exams"]


def fetch_study_guide_markdown(code: str) -> str | None:
    """Fetch the study guide page as markdown. Returns raw text or None on failure."""
    # URL uses the code with hyphen lowercased
    url = STUDY_GUIDE_URL.format(code=code.lower())
    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT, allow_redirects=True)
        if resp.status_code == 200:
            return resp.text
        print(f"  ⚠️ {code}: HTTP {resp.status_code} from {url}")
        return None
    except requests.RequestException as e:
        print(f"  ❌ {code}: Request failed — {e}")
        return None


def parse_front_matter(markdown: str) -> tuple[dict, str]:
    """Split YAML front matter from markdown body. Returns (metadata_dict, body_text)."""
    if not markdown.startswith("---"):
        return {}, markdown

    end = markdown.find("\n---", 3)
    if end == -1:
        return {}, markdown

    fm_text = markdown[3:end].strip()
    body = markdown[end + 4:].strip()

    try:
        metadata = yaml.safe_load(fm_text)
        if not isinstance(metadata, dict):
            metadata = {}
    except yaml.YAMLError:
        metadata = {}

    return metadata, body


def parse_skills_measured(body: str) -> dict:
    """
    Parse the skills measured section from the study guide body.
    Returns a structured dict:
    {
        "skills_date": "January 14, 2026",
        "audience_profile": "...",
        "skills_at_a_glance": [{"area": "...", "weight": "25-30%"}, ...],
        "skills_detailed": {
            "Area Name (weight)": {
                "Sub-area": ["bullet1", "bullet2", ...]
            }
        }
    }
    """
    result = {
        "skills_date": None,
        "audience_profile": "",
        "skills_at_a_glance": [],
        "skills_detailed": {}
    }

    # Find "Skills measured as of ..." section
    skills_match = re.search(
        r"##\s+Skills measured as of (.+?)$",
        body, re.MULTILINE
    )
    if skills_match:
        result["skills_date"] = skills_match.group(1).strip()

    # Find "Skills at a glance" section
    glance_match = re.search(
        r"###\s+Skills at a glance\s*\n([\s\S]*?)(?=\n###\s|\Z)",
        body
    )
    if glance_match:
        glance_text = glance_match.group(1)
        # Parse bullet items like "- Describe cloud concepts (25–30%)"
        for item in re.finditer(r"[-*]\s+(.+?)\s*\((\d+[\–\-]\d+%)\)", glance_text):
            result["skills_at_a_glance"].append({
                "area": item.group(1).strip(),
                "weight": item.group(2).replace("–", "-")
            })

    # Parse detailed skills — h3 areas containing h4 sub-areas with bullet lists
    # Find the section after "Skills at a glance" or "Audience profile"
    skills_section = body
    if skills_match:
        skills_section = body[skills_match.start():]

    current_h3 = None
    current_h4 = None

    for line in skills_section.split("\n"):
        line = line.strip()

        # Match h3: ### Area Name (weight) — these are the main skill areas
        h3_match = re.match(r"^###\s+(?!Skills at a glance|Audience profile)(.+?)$", line)
        if h3_match:
            heading = h3_match.group(1).strip()
            # Skip utility headings
            if heading.lower() in ["study resources", "change log", "updates to the exam"]:
                current_h3 = None
                continue
            current_h3 = heading
            if current_h3 not in result["skills_detailed"]:
                result["skills_detailed"][current_h3] = {}
            current_h4 = None
            continue

        # Match h4: #### Sub-area Name
        h4_match = re.match(r"^####\s+(?!Note)(.+?)$", line)
        if h4_match and current_h3:
            current_h4 = h4_match.group(1).strip()
            if current_h4 not in result["skills_detailed"].get(current_h3, {}):
                result["skills_detailed"][current_h3][current_h4] = []
            continue

        # Match bullet items
        bullet_match = re.match(r"^[-*]\s+(.+)$", line)
        if bullet_match and current_h3 and current_h4:
            bullet_text = bullet_match.group(1).strip()
            # Skip empty or loading items
            if bullet_text and bullet_text != "Loading...":
                result["skills_detailed"][current_h3][current_h4].append(bullet_text)

    return result


def parse_change_log(body: str) -> list[dict]:
    """
    Extract the change log table from the study guide.
    Returns list of dicts with area, previous, current, change fields.
    """
    changes = []
    # Find change log section
    cl_match = re.search(r"##\s+Change log\s*\n([\s\S]*?)(?=\n##\s|\Z)", body)
    if not cl_match:
        return changes

    cl_text = cl_match.group(1)
    # Parse markdown table rows
    rows = re.findall(r"\|(.+?)\|(.+?)\|(.+?)\|(.+?)\|", cl_text)
    for row in rows:
        cells = [c.strip() for c in row]
        # Skip header and separator rows
        if cells[0].startswith("---") or cells[0].lower().startswith("skill"):
            continue
        if all(c == "" or c.startswith("---") for c in cells):
            continue
        # Clean bold markers
        area = re.sub(r"\*\*(.+?)\*\*", r"\1", cells[0])
        changes.append({
            "skill_area_previous": cells[0].strip("* "),
            "skill_area_current": cells[1].strip("* "),
            "change_type": cells[2].strip() if len(cells) > 2 else "",
            "description": cells[3].strip() if len(cells) > 3 else ""
        })

    return changes


def compute_content_hash(skills: dict) -> str:
    """Compute a hash of the skills measured for change detection."""
    content = json.dumps(skills.get("skills_detailed", {}), sort_keys=True)
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def fetch_exam_page_info(code: str) -> dict:
    """Fetch supplementary info from the exam page (practice test URL, etc.)."""
    url = EXAM_PAGE_URL.format(code_lower=code.lower())
    info = {
        "exam_url": url,
        "practice_assessment_url": None,
        "study_guide_url": STUDY_GUIDE_URL.format(code=code.lower())
    }
    try:
        resp = requests.get(url, headers={"Accept": "text/markdown"}, timeout=REQUEST_TIMEOUT)
        if resp.status_code == 200:
            text = resp.text
            # Find practice assessment link
            pa_match = re.search(r"\(/en-us/credentials/certifications/exams/.+?/practice/assessment[^)]+\)", text)
            if pa_match:
                info["practice_assessment_url"] = "https://learn.microsoft.com" + pa_match.group(0)[1:-1]
    except requests.RequestException:
        pass
    return info


def main():
    os.makedirs(SITE_DIR, exist_ok=True)
    exams_config = load_exam_config()
    print(f"📊 Cert Tracker — Fetching {len(exams_config)} exams")
    print("=" * 60)

    results = []
    errors = []

    for i, exam in enumerate(exams_config):
        code = exam["code"]
        print(f"\n[{i+1}/{len(exams_config)}] {code}: {exam['title']}")

        # Fetch study guide markdown
        md = fetch_study_guide_markdown(code)
        if not md:
            errors.append(code)
            print(f"  ⚠️ Skipping — no study guide found")
            continue

        # Parse front matter
        metadata, body = parse_front_matter(md)
        updated_at = metadata.get("updated_at", metadata.get("ms.date", ""))
        git_commit = metadata.get("git_commit_id", "")

        # Parse skills measured
        skills = parse_skills_measured(body)
        skill_areas = len(skills["skills_detailed"])
        total_bullets = sum(
            len(bullets)
            for area in skills["skills_detailed"].values()
            for bullets in area.values()
        )
        print(f"  ✅ Skills: {skill_areas} areas, {total_bullets} objectives")

        # Parse change log
        change_log = parse_change_log(body)
        if change_log:
            print(f"  📝 Change log: {len(change_log)} entries")

        # Compute content hash
        content_hash = compute_content_hash(skills)

        # Build exam record
        record = {
            "code": code,
            "title": exam["title"],
            "level": exam["level"],
            "roles": exam["roles"],
            "products": exam["products"],
            "category": exam["category"],
            "updated_at": str(updated_at) if updated_at else "",
            "git_commit_id": git_commit,
            "content_hash": content_hash,
            "skills_date": skills["skills_date"],
            "skills_at_a_glance": skills["skills_at_a_glance"],
            "skills_detailed": skills["skills_detailed"],
            "change_log": change_log,
            "exam_url": EXAM_PAGE_URL.format(code_lower=code.lower()),
            "study_guide_url": STUDY_GUIDE_URL.format(code=code.lower()),
            "practice_assessment_url": f"https://learn.microsoft.com/en-us/credentials/certifications/exams/{code.lower()}/practice/assessment?assessment-type=practice"
        }
        results.append(record)

        # Polite delay
        if i < len(exams_config) - 1:
            time.sleep(REQUEST_DELAY)

    # Save current state
    state = {
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "exam_count": len(results),
        "errors": errors,
        "exams": results
    }
    state_path = os.path.join(SITE_DIR, "current_state.json")
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)

    print(f"\n{'=' * 60}")
    print(f"✅ Fetched {len(results)}/{len(exams_config)} exams")
    if errors:
        print(f"⚠️ Errors: {', '.join(errors)}")
    print(f"💾 Saved to {state_path}")


if __name__ == "__main__":
    main()
