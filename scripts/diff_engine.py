#!/usr/bin/env python3
"""
diff_engine.py — Compare current exam state vs previous state.

Detects changes in skills measured objectives and generates structured diffs.
Uses content hashes for fast detection, then detailed tree-diff for changed exams.
"""

import json
import os
import sys
import time
from datetime import datetime

SITE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "site")
CURRENT_STATE = os.path.join(SITE_DIR, "current_state.json")
PREVIOUS_STATE = os.path.join(SITE_DIR, "previous_state.json")
CHANGELOG = os.path.join(SITE_DIR, "changelog.json")


def load_json(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: str, data: dict):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def flatten_skills(skills_detailed: dict) -> dict[str, list[str]]:
    """Flatten skills_detailed into {area > sub_area: [bullets]} for easy comparison."""
    flat = {}
    for area, sub_areas in skills_detailed.items():
        for sub_area, bullets in sub_areas.items():
            key = f"{area} > {sub_area}"
            flat[key] = sorted(bullets)
    return flat


def diff_exam(prev_exam: dict, curr_exam: dict) -> dict | None:
    """
    Compare two exam records and return a diff entry if changed.
    Returns None if unchanged.
    """
    if prev_exam.get("content_hash") == curr_exam.get("content_hash"):
        return None

    prev_flat = flatten_skills(prev_exam.get("skills_detailed", {}))
    curr_flat = flatten_skills(curr_exam.get("skills_detailed", {}))

    all_keys = set(prev_flat.keys()) | set(curr_flat.keys())

    changes = []
    for key in sorted(all_keys):
        prev_bullets = set(prev_flat.get(key, []))
        curr_bullets = set(curr_flat.get(key, []))

        added = curr_bullets - prev_bullets
        removed = prev_bullets - curr_bullets

        if key not in prev_flat:
            changes.append({
                "type": "area_added",
                "area": key,
                "bullets": sorted(curr_bullets)
            })
        elif key not in curr_flat:
            changes.append({
                "type": "area_removed",
                "area": key,
                "bullets": sorted(prev_bullets)
            })
        else:
            if added:
                changes.append({
                    "type": "objectives_added",
                    "area": key,
                    "items": sorted(added)
                })
            if removed:
                changes.append({
                    "type": "objectives_removed",
                    "area": key,
                    "items": sorted(removed)
                })

    if not changes:
        return None

    # Count summary
    added_count = sum(
        len(c.get("items", c.get("bullets", [])))
        for c in changes if c["type"] in ("objectives_added", "area_added")
    )
    removed_count = sum(
        len(c.get("items", c.get("bullets", [])))
        for c in changes if c["type"] in ("objectives_removed", "area_removed")
    )

    # Weights change?
    prev_glance = {g["area"]: g["weight"] for g in prev_exam.get("skills_at_a_glance", [])}
    curr_glance = {g["area"]: g["weight"] for g in curr_exam.get("skills_at_a_glance", [])}
    weight_changes = []
    for area in set(prev_glance.keys()) | set(curr_glance.keys()):
        pw = prev_glance.get(area)
        cw = curr_glance.get(area)
        if pw != cw:
            weight_changes.append({
                "area": area,
                "previous_weight": pw,
                "current_weight": cw
            })

    return {
        "code": curr_exam["code"],
        "title": curr_exam["title"],
        "detected_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "previous_skills_date": prev_exam.get("skills_date", ""),
        "current_skills_date": curr_exam.get("skills_date", ""),
        "summary": f"{added_count} added, {removed_count} removed",
        "added_count": added_count,
        "removed_count": removed_count,
        "weight_changes": weight_changes,
        "changes": changes
    }


def main():
    print("📊 Cert Tracker — Diff Engine")
    print("=" * 60)

    current = load_json(CURRENT_STATE)
    previous = load_json(PREVIOUS_STATE)

    if not current:
        print("❌ No current state found. Run fetch_exams.py first.")
        sys.exit(1)

    # Load existing changelog
    changelog = load_json(CHANGELOG)
    if not isinstance(changelog, dict):
        changelog = {}
    if "entries" not in changelog:
        changelog["entries"] = []

    curr_exams = {e["code"]: e for e in current.get("exams", [])}
    prev_exams = {e["code"]: e for e in previous.get("exams", [])}

    if not prev_exams:
        print("ℹ️ No previous state — this is the first run. Creating baseline.")
        # Copy current to previous for next run
        save_json(PREVIOUS_STATE, current)
        save_json(CHANGELOG, changelog)
        print(f"💾 Baseline saved ({len(curr_exams)} exams)")
        return

    new_diffs = []
    new_exams = []
    removed_exams = []

    # Detect changes
    for code, curr in curr_exams.items():
        if code not in prev_exams:
            new_exams.append(code)
            continue

        diff = diff_exam(prev_exams[code], curr)
        if diff:
            new_diffs.append(diff)

    for code in prev_exams:
        if code not in curr_exams:
            removed_exams.append(code)

    # Report
    if new_diffs:
        print(f"\n🔄 {len(new_diffs)} exams changed:")
        for d in new_diffs:
            print(f"  {d['code']}: {d['summary']}")
        changelog["entries"].extend(new_diffs)

    if new_exams:
        print(f"\n🆕 {len(new_exams)} new exams: {', '.join(new_exams)}")

    if removed_exams:
        print(f"\n🗑️ {len(removed_exams)} removed exams: {', '.join(removed_exams)}")

    if not new_diffs and not new_exams and not removed_exams:
        print("\n✅ No changes detected")

    # Update changelog metadata
    changelog["last_checked"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    changelog["total_entries"] = len(changelog["entries"])

    # Save
    save_json(CHANGELOG, changelog)
    save_json(PREVIOUS_STATE, current)

    print(f"\n💾 Changelog: {changelog['total_entries']} total entries")
    print(f"💾 Previous state updated")


if __name__ == "__main__":
    main()
