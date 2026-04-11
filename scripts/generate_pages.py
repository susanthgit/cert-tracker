#!/usr/bin/env python3
"""
generate_pages.py — Generate Hugo content files for individual exam study guide pages.

For each exam in current_state.json, creates:
  content/cert-tracker/{code-lower}.md

These become static SEO pages at /cert-tracker/az-900/, /cert-tracker/sc-300/, etc.
"""

import json
import os
import sys
import re

SITE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "site")
CURRENT_STATE = os.path.join(SITE_DIR, "current_state.json")

# Output goes to the main Hugo site (can be overridden by env var)
HUGO_CONTENT_DIR = os.environ.get(
    "HUGO_CONTENT_DIR",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                 "..", "aguidetocloud-revamp", "content", "cert-tracker")
)

STATUS_LABELS = {
    "active": "Active",
    "retiring": "⚠️ Retiring",
    "retired": "🚫 Retired",
    "beta": "🧪 Beta",
    "upcoming": "🔜 Upcoming"
}

LEVEL_LABELS = {
    "beginner": "Fundamentals",
    "intermediate": "Associate",
    "advanced": "Expert"
}


def generate_description(exam: dict) -> str:
    """Generate SEO-optimized meta description for exam page."""
    code = exam["code"]
    title = exam["title"]
    status = exam.get("status", "active")
    total = sum(
        len(b)
        for a in exam.get("skills_detailed", {}).values()
        for b in a.values()
    )

    if status == "retired":
        return f"{code} ({title}) has been retired. See replacement exams and what you need to know."
    if status == "beta":
        return f"{code}: {title} is in beta. Learn about this new Microsoft certification exam and what to expect."
    if status == "retiring":
        ret_date = exam.get("retirement_date", "soon")
        return f"{code} study guide — {title}. ⚠️ Retiring {ret_date}. {total} objectives, skills measured, and Microsoft Learn resources."

    return f"{code} study guide — {title}. Current exam objectives ({total} topics), skills measured with weights, practice assessment, and Microsoft Learn study resources. Updated weekly."


def generate_skills_markdown(exam: dict) -> str:
    """Generate markdown content for the skills measured section."""
    lines = []
    status = exam.get("status", "active")

    # Status banner
    if status == "retiring":
        ret_date = exam.get("retirement_date", "TBA")
        replacement = exam.get("replacement", "")
        lines.append(f'<div class="cert-status-banner cert-status-retiring">')
        lines.append(f'⚠️ <strong>This exam is retiring on {ret_date}.</strong> {("Replacement: <strong>" + replacement + "</strong>") if replacement else "Check Microsoft Learn for replacement options."}')
        lines.append(f'</div>')
        lines.append("")
    elif status == "retired":
        replacement = exam.get("replacement", "")
        lines.append(f'<div class="cert-status-banner cert-status-retired">')
        lines.append(f'🚫 <strong>This exam has been retired</strong> as of {exam.get("retirement_date", "recently")}. {("Replacement: <strong>" + replacement + "</strong>") if replacement else ""}')
        lines.append(f'</div>')
        lines.append("")
    elif status == "beta":
        beta_since = exam.get("beta_since", "")
        replaces = exam.get("replaces", "")
        lines.append(f'<div class="cert-status-banner cert-status-beta">')
        lines.append(f'🧪 <strong>This exam is currently in beta</strong>{(" since " + beta_since) if beta_since else ""}. Beta exams are typically offered at 80% discount. {("Replaces: <strong>" + replaces + "</strong>") if replaces else ""}')
        lines.append(f'</div>')
        lines.append("")

    # Skills at a glance
    glance = exam.get("skills_at_a_glance", [])
    if glance:
        lines.append("## Skills at a Glance")
        lines.append("")
        lines.append("| Skill Area | Weight |")
        lines.append("|-----------|--------|")
        for s in glance:
            lines.append(f"| {s['area']} | **{s['weight']}** |")
        lines.append("")

    # Detailed skills
    detailed = exam.get("skills_detailed", {})
    if detailed:
        lines.append("## Skills Measured")
        lines.append("")
        for area, sub_areas in detailed.items():
            lines.append(f"### {area}")
            lines.append("")
            for sub_area, bullets in sub_areas.items():
                lines.append(f"#### {sub_area}")
                lines.append("")
                for bullet in bullets:
                    lines.append(f"- {bullet}")
                lines.append("")

    return "\n".join(lines)


def generate_exam_page(exam: dict) -> str:
    """Generate a complete Hugo markdown page for an exam."""
    code = exam["code"]
    title = exam["title"]
    status = exam.get("status", "active")
    level = exam.get("level", "intermediate")
    description = generate_description(exam)
    skills_content = generate_skills_markdown(exam)

    # Front matter
    fm_lines = [
        "---",
        f'title: "{code}: {title} — Study Guide & Exam Objectives"',
        f'description: "{description}"',
        f'type: "cert-tracker"',
        f'layout: "single"',
        f'exam_code: "{code}"',
        f'exam_title: "{title}"',
        f'exam_level: "{level}"',
        f'exam_status: "{status}"',
        f'exam_category: "{exam.get("category", "")}"',
    ]
    if exam.get("retirement_date"):
        fm_lines.append(f'retirement_date: "{exam["retirement_date"]}"')
    if exam.get("replacement"):
        fm_lines.append(f'replacement: "{exam["replacement"]}"')
    if exam.get("replaces"):
        fm_lines.append(f'replaces: "{exam["replaces"]}"')
    if exam.get("beta_since"):
        fm_lines.append(f'beta_since: "{exam["beta_since"]}"')

    fm_lines.append("---")
    fm_lines.append("")

    # Page content
    content_lines = [skills_content]

    # Quick links section
    links = []
    if exam.get("exam_url"):
        links.append(f"- [📝 Official Exam Page]({exam['exam_url']})")
    if exam.get("study_guide_url"):
        links.append(f"- [📖 Microsoft Study Guide]({exam['study_guide_url']})")
    if exam.get("practice_assessment_url"):
        links.append(f"- [🎯 Practice Assessment]({exam['practice_assessment_url']})")

    if links:
        content_lines.append("## Quick Links")
        content_lines.append("")
        content_lines.extend(links)
        content_lines.append("")

    return "\n".join(fm_lines) + "\n".join(content_lines)


def main():
    print("📊 Cert Tracker — Generate Study Guide Pages")
    print("=" * 60)

    state_path = CURRENT_STATE
    if not os.path.exists(state_path):
        print(f"❌ No current state found at {state_path}")
        sys.exit(1)

    with open(state_path, "r", encoding="utf-8") as f:
        state = json.load(f)

    exams = state.get("exams", [])
    output_dir = os.path.abspath(HUGO_CONTENT_DIR)
    os.makedirs(output_dir, exist_ok=True)

    print(f"📁 Output: {output_dir}")
    print(f"📊 Exams: {len(exams)}")
    print()

    generated = 0
    for exam in exams:
        code = exam["code"]
        slug = code.lower()
        filepath = os.path.join(output_dir, f"{slug}.md")

        content = generate_exam_page(exam)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        status_icon = STATUS_LABELS.get(exam.get("status", "active"), "Active")
        total = sum(len(b) for a in exam.get("skills_detailed", {}).values() for b in a.values())
        print(f"  ✅ {code} [{status_icon}] — {total} objectives → {slug}.md")
        generated += 1

    print(f"\n{'=' * 60}")
    print(f"✅ Generated {generated} study guide pages")


if __name__ == "__main__":
    main()
