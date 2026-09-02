import argparse
import json
import os
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


def get_jira_auth():
    """Return Basic Auth tuple for Jira REST API calls."""
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
    client = genai.Client(api_key=GEMINI_API_KEY)

    prompt = f"""
    You are an expert Agile Product Owner assistant. Parse the following specification document and return a structured JSON object containing the Epics and Stories to be created in Jira.

    Specification Document:
    \"\"\"
    {spec_content}
    \"\"\"

    CRITICAL RULES FOR EPICS vs STORIES:
    1. Look closely at the "Epic Mapping" or "Target Epic" section in the spec.
    2. If the spec references existing Jira Epic Keys (e.g., "PET-4", "PET-7", "PET-3"), DO NOT include them in "new_epics". They ALREADY exist in Jira!
    3. Include entries in "new_epics" ONLY if the spec explicitly defines a BRAND NEW Epic that does not have an assigned Jira key (e.g., "PET-X").
    4. For every story, "target_epic_key_or_name" MUST be the exact Jira Epic key (e.g., "PET-7" or "PET-4") if specified in the text.

    Strict JSON Schema Output Format:
    {{
      "new_epics": [
        {{
          "summary": "Brand New Epic Title",
          "description": "Short description of the new Epic"
        }}
      ],
      "stories": [
        {{
          "title": "[ UI | PY | DB ] Story Title",
          "target_epic_key_or_name": "PET-7",
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


def transition_jira_issue(issue_key: str, transition_name_keyword: str = "define") -> bool:
    """Transition a Jira issue status matching a transition name keyword (e.g. 'design', 'defining')."""
    transitions_url = f"{JIRA_BASE_URL}/rest/api/3/issue/{issue_key}/transitions"
    
    res = requests.get(transitions_url, auth=get_jira_auth(), headers=get_jira_headers())
    if res.status_code != 200:
        print(f"  └─ Warning: Could not fetch transitions for {issue_key}")
        return False

    transitions = res.json().get("transitions", [])
    target_transition = None

    for t in transitions:
        if transition_name_keyword.lower() in t["name"].lower():
            target_transition = t
            break

    if not target_transition:
        print(f"  └─ Note: No transition matching '{transition_name_keyword}' available for {issue_key}")
        return False

    payload = {"transition": {"id": target_transition["id"]}}
    post_res = requests.post(transitions_url, auth=get_jira_auth(), headers=get_jira_headers(), json=payload)

    if post_res.status_code in (200, 204):
        print(f"  └─ Transitioned {issue_key} to '{target_transition['name']}'")
        return True
    else:
        print(f"  └─ Warning: Failed to transition {issue_key} ({post_res.status_code}): {post_res.text}")
        return False


# =========================================================================
# MAIN EXECUTION FLOW
# =========================================================================
def main():
    parser = argparse.ArgumentParser(description="Jira Spec Automation Runner")
    parser.add_argument(
        "--spec",
        type=str,
        required=True,
        help="Path to the specification markdown file (e.g., docs/specs/ui_charts_spec.md)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print generated payload without creating Jira issues"
    )
    args = parser.parse_args()

    spec_path = args.spec

    if not os.path.exists(spec_path):
        print(f"Error: Provided path '{spec_path}' does not exist.")
        return

    if not os.path.isfile(spec_path):
        print(f"Error: Path '{spec_path}' is a directory, not a valid markdown file.")
        return

    try:
        with open(spec_path, "r", encoding="utf-8") as f:
            spec_content = f.read()
    except Exception as e:
        print(f"Error reading file '{spec_path}': {e}")
        return

    print(f"Parsing specification file '{spec_path}' using Gemini API...")
    structured_data = parse_spec_with_gemini(spec_content)

    if args.dry_run:
        print("\n--- DRY RUN: PROPOSED JIRA PAYLOAD ---")
        print(json.dumps(structured_data, indent=2))
        print("--------------------------------------\n")
        print("Dry run complete. No tickets were created in Jira.")
        return

    created_epics = {}

    # 1. Create New Epics (with safety check against existing PET keys)
    for epic in structured_data.get("new_epics", []):
        summary = epic["summary"]
        
        # Guardrail: Never re-create an Epic if its title/summary matches an existing key (e.g. PET-4 or PET-7)
        if re.search(r'PET-[0-9]+', summary, re.IGNORECASE):
            print(f"Skipping Epic creation for '{summary}' — matches existing Epic Key pattern.")
            continue

        print(f"Creating New Epic: '{summary}'...")
        res = create_jira_issue(
            summary=summary,
            description=epic.get("description", summary),
            issue_type="Epic"
        )
        epic_key = res["key"]
        created_epics[summary] = epic_key
        print(f"  └─ Created Epic {epic_key}")

    # 2. Create Stories under respective Parents & Transition Status
    for story in structured_data.get("stories", []):
        target_epic = story["target_epic_key_or_name"]
        
        # If target_epic is already an existing key (e.g., PET-7), use it directly. Otherwise use newly created key.
        parent_key = created_epics.get(target_epic, target_epic)

        print(f"Creating Story: '{story['title']}' under Parent '{parent_key}'...")
        res = create_jira_issue(
            summary=story["title"],
            description=story["description"],
            issue_type="Story",
            parent_key=parent_key
        )
        story_key = res["key"]
        print(f"  └─ Created Story {story_key}")

        # Transition Story status (e.g., 'design' or 'defining')
        transition_jira_issue(story_key, transition_name_keyword="define")

    print("\nAll Jira tickets created successfully!")


if __name__ == "__main__":
    main()