import argparse
import os
import sys
from dotenv import load_dotenv
from google import genai
from google.genai import types
from github import Github, Auth

# Load environment variables from root .env
load_dotenv(override=True)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
GITHUB_PAT = os.environ.get("GITHUB_PAT", "").strip()
GITHUB_REPO = os.environ.get("GITHUB_REPO", "").strip()

if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY is missing or empty in your .env file!")

# Explicitly ensure GEMINI_API_KEY is set in environment for Google GenAI SDK
os.environ["GEMINI_API_KEY"] = GEMINI_API_KEY


def run_agent(spec_path: str, output_path: str, commit_message: str):
    print(f"🤖 Agent initialized using spec: '{spec_path}'...")

    if not os.path.exists(spec_path):
        raise FileNotFoundError(f"Could not find specification file at {spec_path}")

    with open(spec_path, "r", encoding="utf-8") as f:
        spec_content = f.read()

    # Dynamic role guidance based on target file extension
    role_desc = "expert Streamlit UI & Python engineer" if output_path.endswith("app.py") else "expert Python software engineer"

    prompt = f"""
You are an {role_desc} building software from formal specs.

STRICT INSTRUCTIONS:
- Implement the Python module strictly adhering to the specification below.
- Return ONLY valid executable Python code wrapped inside a ```python ``` block.
- Do NOT include additional conversational text, explanations, or commentary.
- Ensure all instance methods inside classes explicitly declare `self` as their first parameter.
- If a class method does not read or modify instance state, decorate it with `@staticmethod`.
- Ensure the code handles errors gracefully, uses standard Python typing hints, and follows PEP 8.
- If generating Streamlit code, ensure proper file upload handling, temporary file cleanup, and state management.

SPECIFICATION:
{spec_content}
"""

    print("🧠 Sending spec to Gemini API for code generation...")
    client = genai.Client()

    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.2,
        ),
    )

    generated_code = response.text

    # Extract clean code block from response
    if "```python" in generated_code:
        clean_code = generated_code.split("```python")[1].split("```")[0].strip()
    elif "```" in generated_code:
        clean_code = generated_code.split("```")[1].split("```")[0].strip()
    else:
        clean_code = generated_code.strip()

    # Save generated code locally
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(clean_code)

    print(f"✅ Generated code successfully written to {output_path}")

    # Push generated code to GitHub (if credentials provided)
    if GITHUB_PAT and GITHUB_REPO:
        print("🚀 Committing and pushing generated code to GitHub...")
        g = Github(auth=Auth.Token(GITHUB_PAT))
        repo = g.get_repo(GITHUB_REPO)

        try:
            contents = repo.get_contents(output_path, ref="main")
            repo.update_file(contents.path, commit_message, clean_code, contents.sha, branch="main")
            print(f"🎉 Updated {output_path} on GitHub main branch.")
        except Exception:
            repo.create_file(output_path, commit_message, clean_code, branch="main")
            print(f"🎉 Created {output_path} on GitHub main branch.")


def main(args=None):
    parser = argparse.ArgumentParser(description="Spec-Driven Code Generation Agent Engine")
    
    parser.add_argument(
        "--spec",
        required=True,
        help="Path to input markdown specification file (e.g., docs/specs/ui_ingestion_spec.md)"
    )
    parser.add_argument(
        "--target",
        required=True,
        help="Target path where generated Python file will be saved (e.g., src/app.py)"
    )
    parser.add_argument(
        "--commit-msg",
        required=True,
        help="Git commit message for automatic GitHub push (e.g., 'PET-10: Generate Streamlit UI')"
    )

    parsed_args = parser.parse_args(args)
    run_agent(parsed_args.spec, parsed_args.target, parsed_args.commit_msg)


if __name__ == "__main__":
    main()