import argparse
import os
import json
import re
import requests
from dotenv import load_dotenv

# 1. MUST BE CALLED FIRST to populate environment variables from .env
load_dotenv(override=True)

# 2. Extract and sanitize environment variables
JIRA_BASE_URL = os.environ.get("JIRA_BASE_URL", "").rstrip("/")
JIRA_USER_EMAIL = os.environ.get("JIRA_USER_EMAIL", "").strip()
JIRA_API_TOKEN = os.environ.get("JIRA_API_TOKEN", "").strip()
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()

PROJECT_KEY = "PET"
SPEC_PATH = "docs/specs/ui_ingestion_spec.md"

# Safety checks
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY is missing or empty in your .env file!")

if not JIRA_USER_EMAIL or not JIRA_API_TOKEN:
    raise ValueError("JIRA_USER_EMAIL and JIRA_API_TOKEN must be set in your .env file!")

if not JIRA_BASE_URL:
    raise ValueError("JIRA_BASE_URL is missing or empty in your .env file!")

# Explicitly ensure GEMINI_API_KEY is set in environment for Google GenAI SDK
os.environ["GEMINI_API_KEY"] = GEMINI_API_KEY

from google import genai
from google.genai import types

# =========================================================================
# CONFIGURATION & ENVIRONMENT
# =========================================================================
JIRA_BASE_URL = os.environ.get("JIRA_BASE_URL", "").rstrip("/")
JIRA_USER_EMAIL = os.environ.get("JIRA_USER_EMAIL", "")
JIRA_API_TOKEN = os.environ.get("JIRA_API_TOKEN", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

PROJECT_KEY = "PET"
SPEC_PATH = "docs/specs/ui_ingestion_spec.md"


def get_jira_auth():
    """Return Basic Auth tuple for Jira REST API calls."""
    if not JIRA_USER_EMAIL or not JIRA_API_TOKEN:
        raise ValueError("JIRA_USER_EMAIL and JIRA_API_TOKEN environment variables must be set.")
    return (JIRA_USER_EMAIL, JIRA_API_TOKEN)


def get_jira_headers():
    return {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }


# =========================================================================
# STEP 1: GEMINI SPEC PARSER
# =========================================================================
def parse_spec_with_gemini(spec_content: str) -> dict:
    """Pass specification document to Gemini to extract structured Epic and Story objects."""
    client = genai.Client(api_key=GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY"))

    prompt = f"""
    You are an expert Agile Product Owner assistant. Parse the following specification document and return a structured JSON object containing the Epics and Stories to be created in Jira.

    Specification Document:
    \"\"\"
    {spec_content}
    \"\"\"

    Strict JSON Schema Output Format:
    {{
      "new_epics": [
        {{
          "summary": "Epic Title",
          "description": "Short description of the Epic"
        }}
      ],
      "stories": [
        {{
          "title": "[ UI | PY | DB ] Story Title",
          "target_epic_key_or_name": "PET-4" or "Statement Ingestion UI",
          "description": "Full BDD description including AS A / I WANT / SO THAT and Acceptance Criteria GIVEN/WHEN/THEN"
        }}
      ]
    }}

    Return ONLY raw JSON. Do not wrap in markdown code blocks.
    """

    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.1
        )
    )

    clean_text = response.text.strip()
    clean_text = re.sub(r'^```json\s*', '', clean_text)
    clean_text = re.sub(r'\s*```$', '', clean_text)

    return json.loads(clean_text)


# =========================================================================
# STEP 2: JIRA REST API HELPERS
# =========================================================================
def create_jira_issue(summary: str, description: str, issue_type: str, parent_key: str = None) -> dict:
    """Create an Issue (Epic or Story) in Jira via v3 REST API."""
    url = f"{JIRA_BASE_URL}/rest/api/3/issue"
    
    # Atlassian Document Format (ADF) for rich text description
    adf_description = {
        "type": "doc",
        "version": 1,
        "content": [
            {
                "type": "paragraph",
                "content": [
                    {
                        "type": "text",
                        "text": description
                    }
                ]
            }
        ]
    }

    payload = {
        "fields": {
            "project": {"key": PROJECT_KEY},
            "summary": summary,
            "description": adf_description,
            "issuetype": {"name": issue_type}
        }
    }

    if parent_key:
        payload["fields"]["parent"] = {"key": parent_key}

    response = requests.post(
        url,
        auth=get_jira_auth(),
        headers=get_jira_headers(),
        json=payload
    )

    if response.status_code not in (200, 201):
        raise RuntimeError(f"Failed to create Jira issue ({response.status_code}): {response.text}")

    return response.json()


# =========================================================================
# MAIN EXECUTION FLOW
# =========================================================================
def main():
    parser = argparse.ArgumentParser(description="Jira Spec Automation Runner")
    parser.add_argument("--dry-run", action="store_true", help="Print generated payload without creating Jira issues")
    args = parser.parse_args()

    if not os.path.exists(SPEC_PATH):
        print(f"Error: Spec file '{SPEC_PATH}' not found.")
        return

    with open(SPEC_PATH, "r", encoding="utf-8") as f:
        spec_content = f.read()

    print("Parsing specification using Gemini API...")
    structured_data = parse_spec_with_gemini(spec_content)

    if args.dry_run:
        print("\n--- DRY RUN: PROPOSED JIRA PAYLOAD ---")
        print(json.dumps(structured_data, indent=2))
        print("--------------------------------------\n")
        print("Dry run complete. No tickets were created in Jira.")
        return

    created_epics = {}

    # 1. Create New Epics
    for epic in structured_data.get("new_epics", []):
        print(f"Creating Epic: '{epic['summary']}'...")
        res = create_jira_issue(
            summary=epic["summary"],
            description=epic.get("description", epic["summary"]),
            issue_type="Epic"
        )
        epic_key = res["key"]
        created_epics[epic["summary"]] = epic_key
        print(f"  └─ Created Epic {epic_key}")

    # 2. Create Stories under respective Parents
    for story in structured_data.get("stories", []):
        target_epic = story["target_epic_key_or_name"]
        
        # Resolve target epic key (either existing key like PET-4 or newly created key)
        parent_key = created_epics.get(target_epic, target_epic)

        print(f"Creating Story: '{story['title']}' under Parent '{parent_key}'...")
        res = create_jira_issue(
            summary=story["title"],
            description=story["description"],
            issue_type="Story",
            parent_key=parent_key
        )
        print(f"  └─ Created Story {res['key']}")

    print("\nAll Jira tickets created successfully!")


if __name__ == "__main__":
    main()