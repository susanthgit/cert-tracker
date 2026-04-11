#!/usr/bin/env python3
"""
generate_data.py — Generate frontend JSON data files and RSS feed.

Produces:
- site/latest.json     — slim index for the main listing page
- site/exams/{code}.json — per-exam detail (skills, study links, change history)
- site/rss.xml          — RSS feed for exam changes
"""

import json
import os
import sys
import time
from datetime import datetime
from xml.etree.ElementTree import Element, SubElement, tostring, indent

SITE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "site")
CURRENT_STATE = os.path.join(SITE_DIR, "current_state.json")
CHANGELOG = os.path.join(SITE_DIR, "changelog.json")
EXAMS_DIR = os.path.join(SITE_DIR, "exams")

SITE_URL = "https://www.aguidetocloud.com"
TRACKER_URL = f"{SITE_URL}/cert-tracker"


def load_json(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: str, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def generate_index(state: dict, changelog: dict) -> dict:
    """Generate slim index JSON for the listing page."""
    exams = []
    for e in state.get("exams", []):
        # Count objectives
        total_objectives = sum(
            len(bullets)
            for area in e.get("skills_detailed", {}).values()
            for bullets in area.values()
        )
        exams.append({
            "code": e["code"],
            "title": e["title"],
            "level": e["level"],
            "roles": e["roles"],
            "products": e["products"],
            "category": e["category"],
            "status": e.get("status", "active"),
            "retirement_date": e.get("retirement_date", ""),
            "replacement": e.get("replacement", ""),
            "replaces": e.get("replaces", ""),
            "beta_since": e.get("beta_since", ""),
            "updated_at": e.get("updated_at", ""),
            "skills_date": e.get("skills_date", ""),
            "skill_areas": len(e.get("skills_at_a_glance", [])),
            "total_objectives": total_objectives,
            "skills_at_a_glance": e.get("skills_at_a_glance", []),
            "has_changes": any(
                c["code"] == e["code"]
                for c in changelog.get("entries", [])
            ),
            "exam_url": e.get("exam_url", ""),
            "study_guide_url": e.get("study_guide_url", "")
        })

    # Sort: active first, then retiring, beta, retired. Within each: by category then code.
    status_order = {"active": 0, "retiring": 1, "beta": 2, "upcoming": 3, "retired": 4}
    level_order = {"beginner": 0, "intermediate": 1, "advanced": 2}
    exams.sort(key=lambda x: (status_order.get(x.get("status", "active"), 5), x["category"], level_order.get(x["level"], 1), x["code"]))

    return {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "exam_count": len(exams),
        "categories": sorted(set(e["category"] for e in exams)),
        "last_change_detected": changelog.get("last_checked", ""),
        "total_changes": changelog.get("total_entries", 0),
        "exams": exams
    }


def generate_exam_detail(exam: dict, changelog: dict, related_map: dict = None, all_exams: dict = None) -> dict:
    """Generate per-exam detail JSON."""
    # Get change history for this exam
    exam_changes = [
        c for c in changelog.get("entries", [])
        if c["code"] == exam["code"]
    ]
    exam_changes.sort(key=lambda x: x.get("detected_at", ""), reverse=True)

    # Build related exams list
    related = []
    code = exam["code"]
    if related_map and all_exams and code in related_map:
        for rc in related_map[code]:
            if rc in all_exams:
                re = all_exams[rc]
                related.append({
                    "code": rc,
                    "title": re.get("title", ""),
                    "level": re.get("level", ""),
                    "status": re.get("status", "active"),
                    "category": re.get("category", "")
                })

    return {
        "code": code,
        "title": exam["title"],
        "level": exam["level"],
        "roles": exam["roles"],
        "products": exam["products"],
        "category": exam["category"],
        "status": exam.get("status", "active"),
        "updated_at": exam.get("updated_at", ""),
        "skills_date": exam.get("skills_date", ""),
        "skills_at_a_glance": exam.get("skills_at_a_glance", []),
        "skills_detailed": exam.get("skills_detailed", {}),
        "change_log_official": exam.get("change_log", []),
        "change_history": exam_changes,
        "related_exams": related,
        "exam_url": exam.get("exam_url", ""),
        "study_guide_url": exam.get("study_guide_url", ""),
        "practice_assessment_url": exam.get("practice_assessment_url", "")
    }


def generate_rss(changelog: dict) -> str:
    """Generate RSS feed for exam changes."""
    rss = Element("rss", version="2.0")
    rss.set("xmlns:atom", "http://www.w3.org/2005/Atom")
    channel = SubElement(rss, "channel")

    SubElement(channel, "title").text = "Microsoft Cert Exam Changes — A Guide to Cloud"
    SubElement(channel, "link").text = TRACKER_URL
    SubElement(channel, "description").text = "Track changes to Microsoft certification exam objectives. Never study outdated material again."
    SubElement(channel, "language").text = "en-us"

    atom_link = SubElement(channel, "{http://www.w3.org/2005/Atom}link")
    atom_link.set("href", f"{TRACKER_URL}/rss.xml")
    atom_link.set("rel", "self")
    atom_link.set("type", "application/rss+xml")

    # Add recent changes (last 50)
    entries = sorted(
        changelog.get("entries", []),
        key=lambda x: x.get("detected_at", ""),
        reverse=True
    )[:50]

    for entry in entries:
        item = SubElement(channel, "item")
        SubElement(item, "title").text = f"{entry['code']} exam updated: {entry['summary']}"
        SubElement(item, "link").text = f"{TRACKER_URL}/{entry['code'].lower()}/"
        SubElement(item, "guid").text = f"{TRACKER_URL}/{entry['code'].lower()}/#{entry.get('detected_at', '')}"

        # Build description
        desc_parts = [f"<p><strong>{entry['code']}: {entry.get('title', '')}</strong></p>"]
        desc_parts.append(f"<p>{entry['summary']}</p>")
        if entry.get("changes"):
            desc_parts.append("<ul>")
            for c in entry["changes"][:10]:
                items = c.get("items", c.get("bullets", []))
                desc_parts.append(f"<li>{c['type']}: {c['area']} ({len(items)} items)</li>")
            desc_parts.append("</ul>")
        SubElement(item, "description").text = "\n".join(desc_parts)

        if entry.get("detected_at"):
            try:
                dt = datetime.fromisoformat(entry["detected_at"].replace("Z", "+00:00"))
                SubElement(item, "pubDate").text = dt.strftime("%a, %d %b %Y %H:%M:%S +0000")
            except (ValueError, AttributeError):
                pass

    indent(rss, space="  ")
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + tostring(rss, encoding="unicode")


def main():
    print("📊 Cert Tracker — Generate Data")
    print("=" * 60)

    state = load_json(CURRENT_STATE)
    changelog = load_json(CHANGELOG)

    if not state:
        print("❌ No current state found. Run fetch_exams.py first.")
        sys.exit(1)

    # Generate index
    index = generate_index(state, changelog)
    index_path = os.path.join(SITE_DIR, "latest.json")
    save_json(index_path, index)
    print(f"✅ Index: {index['exam_count']} exams → {index_path}")

    # Load related exams mapping
    related_path = os.path.join(os.path.dirname(os.path.dirname(SITE_DIR)), "cert-tracker", "scripts", "related_exams.json")
    related_map = {}
    if os.path.exists(related_path):
        related_map = load_json(related_path)
    all_exams = {e["code"]: e for e in state.get("exams", [])}

    # Generate per-exam details
    os.makedirs(EXAMS_DIR, exist_ok=True)
    for exam in state.get("exams", []):
        detail = generate_exam_detail(exam, changelog, related_map=related_map, all_exams=all_exams)
        detail_path = os.path.join(EXAMS_DIR, f"{exam['code'].lower()}.json")
        save_json(detail_path, detail)
    print(f"✅ Exam details: {len(state.get('exams', []))} files → {EXAMS_DIR}")

    # Generate RSS
    rss_xml = generate_rss(changelog)
    rss_path = os.path.join(SITE_DIR, "rss.xml")
    with open(rss_path, "w", encoding="utf-8") as f:
        f.write(rss_xml)
    print(f"✅ RSS feed → {rss_path}")

    print(f"\n📊 Summary:")
    print(f"  Exams tracked: {index['exam_count']}")
    print(f"  Categories: {', '.join(index['categories'])}")
    print(f"  Total changes in history: {index['total_changes']}")


if __name__ == "__main__":
    main()
