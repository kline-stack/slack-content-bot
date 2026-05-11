"""
Generates a content brief using Claude (claude-sonnet-4-6).
Uses the structural brief template + active company profile.
"""
import os
import re
from pathlib import Path
import anthropic

CONFIG_DIR = Path(__file__).parent.parent / "config"
TEMPLATE_PATH = CONFIG_DIR / "brief_template.txt"


def load_company_profile() -> tuple[str, str, str]:
    """Returns (company_name, company_profile_text, quote_bank_text)"""
    profile_file = os.environ.get("COMPANY_PROFILE_FILE", "company_profile_crhh.txt")
    profile_path = CONFIG_DIR / profile_file
    text = profile_path.read_text()

    # Extract company name from first heading
    m = re.search(r"##\s*(.+?)\s*—\s*Company Profile", text)
    company_name = m.group(1).strip() if m else "the company"

    # Split profile and quote bank
    if "## QUOTE BANK" in text:
        parts = text.split("## QUOTE BANK", 1)
        profile_text = parts[0].strip()
        quote_bank = "## QUOTE BANK\n" + parts[1].strip()
    else:
        profile_text = text.strip()
        quote_bank = "No quote bank provided."

    return company_name, profile_text, quote_bank


def build_system_prompt() -> str:
    template = TEMPLATE_PATH.read_text()
    company_name, company_profile, quote_bank = load_company_profile()

    # Use simple replacement instead of .format() to avoid KeyErrors
    # from curly braces in the template (e.g. {domain}, {keyword})
    result = template.replace("{company_name}", company_name)
    result = result.replace("{company_profile}", company_profile)
    result = result.replace("{quote_bank}", quote_bank)
    return result


def generate_brief(keyword: str, freelancer_name: str, due_date: str) -> str:
    """
    Calls Claude to generate a full brief.
    Returns the brief as a string.
    """
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    system_prompt = build_system_prompt()

    user_message = (
        f"Generate a complete content brief for the following:\n\n"
        f"**Main Keyword:** {keyword}\n"
        f"**Assigned to:** {freelancer_name}\n"
        f"**Due Date:** {due_date}\n\n"
        f"Fill in every section of the brief template fully. "
        f"Do not leave any placeholders. "
        f"Make the angle, outline, and related keywords specific to this topic."
    )

    message = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=4096,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )

    return message.content[0].text
