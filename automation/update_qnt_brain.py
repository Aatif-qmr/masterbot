#!/usr/bin/env python3
import glob
import os

QNT_MD_PATH = "QNT.md"
STRATEGIES_DIR = "strategies/active"
AUTOMATION_DIR = "automation"


def get_active_strategies():
    files = glob.glob(os.path.join(STRATEGIES_DIR, "*.py"))
    return [os.path.basename(f) for f in files]


def get_automation_scripts():
    files = glob.glob(os.path.join(AUTOMATION_DIR, "*"))
    return [os.path.basename(f) for f in files]


def update_qnt_brain():
    strategies = get_active_strategies()
    scripts = get_automation_scripts()

    with open(QNT_MD_PATH) as f:
        content = f.read()

    # Simple replacement for dynamic sections (could be more robust with regex)
    # For now, we just append or update the "Key Directories" section or similar

    # We will look for placeholders or just overwrite specific lines
    # Let's add an "Active Components" section at the end if it doesn't exist

    dynamic_section = "\n## Current State (Auto-Generated)\n\n"
    dynamic_section += "### Active Strategies\n"
    for s in strategies:
        dynamic_section += f"- {s}\n"
    if not strategies:
        dynamic_section += "- None found\n"

    dynamic_section += "\n### Available Automation\n"
    for s in scripts:
        dynamic_section += f"- {s}\n"

    if "## Current State (Auto-Generated)" in content:
        # Replace existing section
        parts = content.split("## Current State (Auto-Generated)")
        new_content = parts[0] + dynamic_section
    else:
        new_content = content + dynamic_section

    with open(QNT_MD_PATH, "w") as f:
        f.write(new_content)

    print("QNT Brain updated successfully.")


if __name__ == "__main__":
    update_qnt_brain()
