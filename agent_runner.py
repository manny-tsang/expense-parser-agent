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


def run_agent(spec_path: str, output_path: str, commit_message: str, context_paths: list = None):
    print(f"🤖 Agent initialized using spec: '{spec_path}'...")

    if not os.path.exists(spec_path):
        raise FileNotFoundError(f"Could not find specification file at {spec_path}")

    with open(spec_path, "r", encoding="utf-8") as f:
        spec_content = f.read()

    # Read target file if it already exists (to update in-place rather than overwrite completely)
    existing_target_code = ""
    if os.path.exists(output_path):
        with open(output_path, "r", encoding="utf-8") as f:
            existing_target_code = f.read()

    # Read context files if provided
    context_contents = []
    if context_paths:
        for cpath in context_paths:
            if os.path.exists(cpath):
                with open(cpath, "r", encoding="utf-8") as f:
                    context_contents.append(f"--- CONTEXT FILE: {cpath} ---\n{f.read()}\n")
            else:
                print(f"⚠️ Warning: Context file '{cpath}' not found. Skipping.")

    combined_context = "\n\n".join(context_contents)

    # Dynamic role guidance and strict scoping based on target file
    if output_path.endswith("app.py"):
        role_desc = "expert Streamlit UI developer"
        scope_instruction = """
STRICT SCOPE BOUNDARY:
- You are writing/updating ONLY the Streamlit UI presentation layer (`src/app.py`).
- DO NOT define database table schemas or initial migration logic in this file.
- Call existing backend repository methods or parser methods for data operations.
"""
    else:
        role_desc = "expert Python backend software engineer"
        scope_instruction = """
STRICT SCOPE BOUNDARY:
- You are writing/updating ONLY the data processing, parsing, and database repository layer (`src/pdf_parser.py`).
- DO NOT write any Streamlit UI components, `st.title`, `st.sidebar`, page renderers, or Streamlit imports in this file.
- Implement strictly backend classes like `HKStatementParser` and `DatabaseRepository`.
"""

    prompt = f"""
You are an {role_desc} building and updating software from formal specifications.

{scope_instruction}

STRICT INSTRUCTIONS:
- Return ONLY valid executable Python code wrapped inside a ```python ``` block.
- Do NOT include additional conversational text, explanations, or commentary.
- Update and refactor the TARGET FILE below to fulfill the SPECIFICATION while preserving existing necessary methods and structure.
- Respect module boundaries established in the CONTEXT FILES (if provided).
- Ensure all instance methods inside classes explicitly declare `self` as their first parameter.
- If a class method does not read or modify instance state, decorate it with `@staticmethod`.
- Follow PEP 8 standards and typing hints.

SPECIFICATION:
{spec_content}

TARGET FILE TO MODIFY ({output_path}):
\"\"\"python
{existing_target_code}
\"\"\"

{'REFERENCE CONTEXT FILES:' if combined_context else ''}
{combined_context}
"""

    print("🧠 Sending spec and target context to Gemini API for code generation...")
    client = genai.Client()

    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.1,
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
        help="Path to input markdown specification file (e.g., docs/specs/ui_categorisation_spec.md)"
    )
    parser.add_argument(
        "--target",
        required=True,
        help="Target path where generated Python file will be saved (e.g., src/pdf_parser.py)"
    )
    parser.add_argument(
        "--context",
        nargs="*",
        help="Optional list of reference context files (e.g., --context src/app.py)"
    )
    parser.add_argument(
        "--commit-msg",
        required=True,
        help="Git commit message for automatic GitHub push (e.g., 'PET-12: Update parser schema')"
    )

    parsed_args = parser.parse_args(args)
    run_agent(parsed_args.spec, parsed_args.target, parsed_args.commit_msg, parsed_args.context)


if __name__ == "__main__":
    main()