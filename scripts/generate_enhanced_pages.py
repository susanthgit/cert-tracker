#!/usr/bin/env python3
"""
generate_enhanced_pages.py — Generate rich study guide pages for all remaining exams.

Uses current_state.json + exam metadata to produce enhanced pages with:
- Exam Quick Facts panel
- Official Learning Paths (where available)
- Study Resources table
- Skills at a Glance
- "Who is this exam for?" section
- Descriptive text per domain
- Objectives (linked to official study guide)
"""

import json
import os
import re
import sys

SITE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "site")
CURRENT_STATE = os.path.join(SITE_DIR, "current_state.json")
RELATED_EXAMS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "related_exams.json")
HUGO_CONTENT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "..", "aguidetocloud-revamp", "content", "cert-tracker"
)

# Exams already manually enhanced — skip these
SKIP_EXAMS = {
    "AZ-900", "SC-900", "AI-900", "DP-900", "PL-900",
    "AZ-104", "SC-300", "MS-102", "MD-102",
    "AZ-305", "AZ-400", "SC-200", "PL-300"
}

# Exam-specific metadata
EXAM_META = {
    # Duration + question count + cost
    "beginner":     {"duration": "45 minutes",  "questions": "~40-60", "cost": "$99 USD"},
    "intermediate": {"duration": "100 minutes", "questions": "~40-60", "cost": "$165 USD"},
    "advanced":     {"duration": "100 minutes", "questions": "~40-60", "cost": "$165 USD"},
}

LEVEL_LABELS = {"beginner": "Fundamentals", "intermediate": "Associate", "advanced": "Expert"}

# Category-specific "who is this for" intros
CATEGORY_INTROS = {
    "Azure": "This is a Microsoft Azure certification exam. It tests your practical knowledge of Azure services and your ability to implement, manage, and design solutions on the Azure platform.",
    "AI": "This Microsoft AI certification covers artificial intelligence concepts and Azure AI services. It tests your understanding of AI workloads, machine learning, and how to implement AI solutions using Azure.",
    "Security": "This Microsoft Security certification covers security, compliance, and identity topics. It tests your ability to implement and manage security solutions across Microsoft's cloud platforms.",
    "Microsoft 365": "This Microsoft 365 certification covers the administration and management of M365 services. It tests your ability to deploy, configure, and manage Microsoft 365 workloads.",
    "Power Platform": "This Power Platform certification covers Microsoft's low-code/no-code platform. It tests your ability to build business applications, automate processes, and create solutions using Power Apps, Power Automate, and related services.",
    "Data": "This Microsoft Data certification covers data concepts and Azure data services. It tests your ability to work with relational and non-relational databases, analytics workloads, and data platforms on Azure.",
    "Dynamics 365": "This Dynamics 365 certification covers Microsoft's business applications platform. It tests your ability to configure, customise, and manage Dynamics 365 solutions for specific business functions.",
}

def get_audience_description(exam):
    """Generate a 'Who is this exam for?' paragraph."""
    code = exam["code"]
    title = exam["title"]
    level = exam.get("level", "intermediate")
    category = exam.get("category", "")
    status = exam.get("status", "active")

    level_desc = {
        "beginner": "This is a fundamentals-level exam — no hands-on experience is required, though basic IT knowledge helps.",
        "intermediate": "This is an associate-level exam that expects hands-on experience. You should have practical knowledge of the technologies covered.",
        "advanced": "This is an expert-level exam requiring advanced knowledge and significant hands-on experience."
    }

    intro = CATEGORY_INTROS.get(category, "This Microsoft certification exam validates your technical skills.")

    status_note = ""
    if status == "retiring":
        ret_date = exam.get("retirement_date", "soon")
        replacement = exam.get("replacement", "")
        status_note = f"\n\n**This exam is retiring on {ret_date}.** "
        if replacement:
            status_note += f"The replacement exam is **{replacement}**. "
        status_note += "If you're planning to take this exam, schedule it before the retirement date."
    elif status == "retired":
        ret_date = exam.get("retirement_date", "recently")
        replacement = exam.get("replacement", "")
        status_note = f"\n\n**This exam was retired on {ret_date}.** "
        if replacement:
            status_note += f"Consider **{replacement}** as the replacement path."

    return f"{intro} {level_desc.get(level, '')}{status_note}"


def get_domain_description(domain_name, exam_category):
    """Generate a brief description for a skill domain based on its name."""
    name_lower = domain_name.lower()

    # Common patterns
    if "identity" in name_lower and "governance" in name_lower:
        return "This domain covers identity management, access control, and governance. You need to understand how to manage users, roles, policies, and compliance across the platform."
    if "identity" in name_lower or "authentication" in name_lower:
        return "This domain covers identity and authentication. You need to understand how to manage identities, configure authentication methods, and control access to resources."
    if "storage" in name_lower:
        return "This domain covers data storage solutions. You need to understand the different storage options, when to use each, and how to configure them for performance, security, and cost."
    if "compute" in name_lower:
        return "This domain covers compute resources — the services that run your workloads. You need to know how to deploy, configure, and manage various compute options."
    if "network" in name_lower:
        return "This domain covers networking. You need to understand virtual networks, connectivity, load balancing, DNS, and network security."
    if "monitor" in name_lower or "maintain" in name_lower:
        return "This domain covers monitoring and maintenance. You need to know how to use monitoring tools, configure alerts, and implement backup and recovery solutions."
    if "security" in name_lower and "threat" in name_lower:
        return "This domain covers security threat management. You need to understand how to detect, investigate, and respond to security threats across the environment."
    if "security" in name_lower:
        return "This domain covers security features and capabilities. You need to understand how to implement and manage security controls to protect the environment."
    if "compliance" in name_lower:
        return "This domain covers compliance and data governance. You need to understand regulatory requirements and how to implement compliance solutions."
    if "deploy" in name_lower and "manage" in name_lower:
        return "This domain covers deployment and management. You need to know how to set up, configure, and maintain the environment for day-to-day operations."
    if "data" in name_lower and ("model" in name_lower or "storage" in name_lower):
        return "This domain covers data modelling and storage design. You need to understand how to structure data effectively for performance and usability."
    if "pipeline" in name_lower or "build" in name_lower or "release" in name_lower:
        return "This domain covers CI/CD pipelines. You need to understand how to design, build, and manage automated build and release processes."
    if "migration" in name_lower:
        return "This domain covers migration strategies. You need to understand how to plan and execute migrations from on-premises or other cloud environments."
    if "business continuity" in name_lower or "backup" in name_lower or "disaster" in name_lower:
        return "This domain covers business continuity, backup, and disaster recovery. You need to understand how to design solutions that keep services running when things go wrong."
    if "infrastructure" in name_lower:
        return "This domain covers infrastructure design and implementation. You need to understand how to architect solutions using the right services and patterns."
    if "app" in name_lower and ("protect" in name_lower or "config" in name_lower):
        return "This domain covers application management. You need to understand how to deploy, configure, and protect applications across the platform."
    if "visuali" in name_lower or "analy" in name_lower:
        return "This domain covers data visualisation and analysis. You need to know how to create effective reports, dashboards, and analytical insights."
    if "prepare" in name_lower and "data" in name_lower:
        return "This domain covers data preparation. You need to know how to connect to data sources, clean and transform data, and prepare it for analysis."
    if "workload" in name_lower:
        return "This domain covers workload management and implementation. You need to understand the specific workload requirements and how to configure solutions to meet them."

    # Generic fallback
    return f"This domain covers the skills needed to work with the topics described below. Study each objective carefully and use the linked resources to deepen your understanding."


def generate_page(exam, related_map=None, all_exams=None):
    """Generate an enhanced study guide page for an exam."""
    code = exam["code"]
    title = exam["title"]
    level = exam.get("level", "intermediate")
    status = exam.get("status", "active")
    category = exam.get("category", "")
    skills_date = exam.get("skills_date", "")
    meta = EXAM_META.get(level, EXAM_META["intermediate"])

    lines = []

    # Front matter
    desc_status = ""
    if status == "retiring":
        desc_status = f" Retiring {exam.get('retirement_date', 'soon')}."
    elif status == "retired":
        desc_status = " This exam has been retired."
    elif status == "beta":
        desc_status = " Currently in beta."

    description = f"Free {code} study guide — {title}. Skills measured with weights, practice assessment, and Microsoft Learn resources.{desc_status}"

    lines.append("---")
    lines.append(f'title: "{code}: {title} — Study Guide & Exam Objectives"')
    lines.append(f'description: "{description}"')
    lines.append(f'type: "cert-tracker"')
    lines.append(f'layout: "single"')
    lines.append(f'exam_code: "{code}"')
    lines.append(f'exam_title: "{title}"')
    lines.append(f'exam_level: "{level}"')
    lines.append(f'exam_status: "{status}"')
    lines.append(f'exam_category: "{category}"')
    if exam.get("retirement_date"):
        lines.append(f'retirement_date: "{exam["retirement_date"]}"')
    if exam.get("replacement"):
        lines.append(f'replacement: "{exam["replacement"]}"')
    if exam.get("replaces"):
        lines.append(f'replaces: "{exam["replaces"]}"')
    if exam.get("beta_since"):
        lines.append(f'beta_since: "{exam["beta_since"]}"')
    lines.append(f'manual: true')
    lines.append("---")
    lines.append("")

    # Status banner for retiring/retired/beta
    if status == "retiring":
        ret_date = exam.get("retirement_date", "TBA")
        replacement = exam.get("replacement", "")
        lines.append(f'<div class="cert-status-banner cert-status-retiring">')
        repl_text = f" Replacement: <strong>{replacement}</strong>" if replacement else ""
        lines.append(f'Warning: <strong>This exam is retiring on {ret_date}.</strong>{repl_text}')
        lines.append(f'</div>')
        lines.append("")
    elif status == "retired":
        ret_date = exam.get("retirement_date", "recently")
        replacement = exam.get("replacement", "")
        lines.append(f'<div class="cert-status-banner cert-status-retired">')
        repl_text = f" Replacement: <strong>{replacement}</strong>" if replacement else ""
        lines.append(f'This exam was retired on {ret_date}.{repl_text}')
        lines.append(f'</div>')
        lines.append("")
    elif status == "beta":
        beta_since = exam.get("beta_since", "")
        replaces = exam.get("replaces", "")
        lines.append(f'<div class="cert-status-banner cert-status-beta">')
        since_text = f" since {beta_since}" if beta_since else ""
        repl_text = f" Replaces: <strong>{replaces}</strong>" if replaces else ""
        lines.append(f'This exam is currently in beta{since_text}. Beta exams are typically offered at 80% discount.{repl_text}')
        lines.append(f'</div>')
        lines.append("")

    # Exam Quick Facts
    code_lower = code.lower()
    lines.append("## Exam Quick Facts")
    lines.append("")
    lines.append("| Detail | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| **Exam Code** | {code} |")
    lines.append(f"| **Title** | {title} |")
    lines.append(f"| **Level** | {LEVEL_LABELS.get(level, level)} |")
    lines.append(f"| **Pass Score** | 700 / 1000 |")
    lines.append(f"| **Duration** | {meta['duration']} |")
    lines.append(f"| **Questions** | {meta['questions']} |")
    lines.append(f"| **Cost** | {meta['cost']} (varies by region) |")
    lines.append(f"| **Scheduling** | [Pearson VUE](https://learn.microsoft.com/en-us/credentials/certifications/schedule-through-pearson-vue?examUid=exam.{code}) |")
    if skills_date:
        lines.append(f"| **Skills Updated** | {skills_date} |")
    if status == "retiring":
        lines.append(f"| **Retires** | **{exam.get('retirement_date', 'TBA')}** |")
    lines.append("")

    # Study Resources
    lines.append("## Study Resources")
    lines.append("")
    lines.append("| Resource | Link |")
    lines.append("|----------|------|")
    lines.append(f"| Official Exam Page | [Microsoft Learn — {code}](https://learn.microsoft.com/en-us/credentials/certifications/exams/{code_lower}/) |")
    sg_url = exam.get("study_guide_url", "")
    if sg_url:
        lines.append(f"| Official Study Guide | [Microsoft Study Guide]({sg_url}) |")
    pa_url = exam.get("practice_assessment_url", "")
    if pa_url:
        lines.append(f"| Free Practice Assessment | [Start Practice Assessment]({pa_url}) |")
    lines.append(f"| Exam Sandbox | [Try the exam interface](https://aka.ms/examdemo) |")
    lines.append("")

    # Skills at a Glance
    glance = exam.get("skills_at_a_glance", [])
    if glance:
        lines.append("## Skills at a Glance")
        lines.append("")
        lines.append("| Skill Area | Weight |")
        lines.append("|-----------|--------|")
        for s in glance:
            lines.append(f"| {s['area']} | **{s['weight']}** |")
        lines.append("")

    # Who is this exam for?
    lines.append("---")
    lines.append("")
    lines.append("## Who is this exam for?")
    lines.append("")
    lines.append(get_audience_description(exam))
    lines.append("")

    # Skills Measured
    detailed = exam.get("skills_detailed", {})
    if detailed:
        lines.append("---")
        lines.append("")
        lines.append("## Skills Measured")
        lines.append("")

        sg_base = sg_url if sg_url else f"https://learn.microsoft.com/en-us/certifications/resources/study-guides/{code_lower}"

        for area_name, sub_areas in detailed.items():
            lines.append(f"### {area_name}")
            lines.append("")
            lines.append(get_domain_description(area_name, category))
            lines.append("")

            for sub_area_name, bullets in sub_areas.items():
                lines.append(f"#### {sub_area_name}")
                lines.append("")
                for bullet in bullets:
                    lines.append(f"- {bullet}")
                lines.append("")
    elif status == "beta":
        lines.append("---")
        lines.append("")
        lines.append("## Skills Measured")
        lines.append("")
        lines.append("Skills measured have not been published yet for this beta exam. Check the [official exam page](https://learn.microsoft.com/en-us/credentials/certifications/exams/" + code_lower + "/) for updates.")
        lines.append("")

    # What to Study Next (related exams)
    if related_map and all_exams and code in related_map:
        related_codes = related_map[code]
        related_items = []
        for rc in related_codes:
            if rc in all_exams:
                re_exam = all_exams[rc]
                re_level = LEVEL_LABELS.get(re_exam.get("level", ""), "")
                re_status = re_exam.get("status", "active")
                status_tag = ""
                if re_status == "retiring":
                    status_tag = " ⚠️ Retiring"
                elif re_status == "beta":
                    status_tag = " 🧪 Beta"
                elif re_status == "retired":
                    status_tag = " 🚫 Retired"
                related_items.append(
                    f"- [{rc}: {re_exam.get('title', '')}](/cert-tracker/{rc.lower()}/) — {re_level}{status_tag}"
                )
        if related_items:
            lines.append("---")
            lines.append("")
            lines.append("## What to Study Next")
            lines.append("")
            lines.append("Based on this exam, here are related certifications to consider:")
            lines.append("")
            lines.extend(related_items)
            lines.append("")

    # Quick Links
    lines.append("---")
    lines.append("")
    lines.append("## Quick Links")
    lines.append("")
    lines.append(f"- [Official Exam Page](https://learn.microsoft.com/en-us/credentials/certifications/exams/{code_lower}/)")
    if sg_url:
        lines.append(f"- [Microsoft Study Guide]({sg_url})")
    if pa_url:
        lines.append(f"- [Practice Assessment]({pa_url})")
    lines.append("")

    return "\n".join(lines)


def main():
    print("Cert Tracker - Generate Enhanced Pages")
    print("=" * 60)

    with open(CURRENT_STATE, "r", encoding="utf-8") as f:
        state = json.load(f)

    # Load related exams mapping
    related_map = {}
    if os.path.exists(RELATED_EXAMS_PATH):
        with open(RELATED_EXAMS_PATH, "r", encoding="utf-8") as f:
            related_map = json.load(f)
        print(f"Loaded related exams: {len(related_map)} mappings")

    # Build lookup of all exams by code
    all_exams = {e["code"]: e for e in state.get("exams", [])}

    output_dir = os.path.abspath(HUGO_CONTENT_DIR)
    generated = 0
    skipped = 0

    for exam in state.get("exams", []):
        code = exam["code"]

        if code in SKIP_EXAMS:
            skipped += 1
            continue

        slug = code.lower()
        filepath = os.path.join(output_dir, f"{slug}.md")
        content = generate_page(exam, related_map=related_map, all_exams=all_exams)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        obj_count = sum(len(b) for a in exam.get("skills_detailed", {}).values() for b in a.values())
        status = exam.get("status", "active")
        print(f"  {code:8s} [{status:8s}] {obj_count:3d} obj  -> {slug}.md")
        generated += 1

    print(f"\n{'=' * 60}")
    print(f"Generated: {generated}  |  Skipped (already enhanced): {skipped}")


if __name__ == "__main__":
    main()
