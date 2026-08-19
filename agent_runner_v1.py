import os
from dotenv import load_dotenv
from google import genai
from google.genai import types
from github import Github, Auth

# Load environment variables from root .env
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GITHUB_PAT = os.getenv("GITHUB_PAT")
GITHUB_REPO = os.getenv("GITHUB_REPO")

def run_agent():
    print("🤖 Agent initialized. Reading specification...")
    
    # 1. Read spec file locally (Zero financial data exposure)
    spec_path = "docs/specs/pdf_parser_spec.md"
    if not os.path.exists(spec_path):
        raise FileNotFoundError(f"Could not find specification file at {spec_path}")
        
    with open(spec_path, "r", encoding="utf-8") as f:
        spec_content = f.read()

    # 2. Build explicit, air-gapped prompt
    prompt = f"""
You are an expert Python software engineer building a modular PDF parser.

STRICT INSTRUCTIONS:
- Implement the Python module strictly adhering to the specification below.
- Return ONLY valid executable Python code wrapped inside a ```python ``` block.
- Do NOT include additional conversational text, explanations, or commentary.
- Ensure all instance methods inside classes explicitly declare `self` as their first parameter.
- If a class method does not read or modify instance state, decorate it with `@staticmethod`.
- Ensure the code handles errors gracefully and uses standard Python typing hints.

SPECIFICATION:
{spec_content}
"""

    # 3. Call Gemini API using google-genai SDK
    print("🧠 Sending spec to Gemini API for code generation...")
    client = genai.Client(api_key=GEMINI_API_KEY)
    
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

    # 4. Save generated code locally
    output_path = "src/pdf_parser.py"
    os.makedirs("src", exist_ok=True)
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(clean_code)
        
    print(f"✅ Generated code successfully written to {output_path}")

    # 5. Push generated code to GitHub
    if GITHUB_PAT and GITHUB_REPO:
        print("🚀 Committing and pushing generated code to GitHub...")
        g = Github(auth=Auth.Token(GITHUB_PAT))
        repo = g.get_repo(GITHUB_REPO)
        
        commit_message = "PET-5: Generate initial PDF parser module from specification"
        
        try:
            contents = repo.get_contents("src/pdf_parser.py", ref="main")
            repo.update_file(contents.path, commit_message, clean_code, contents.sha, branch="main")
            print("🎉 Updated src/pdf_parser.py on GitHub main branch.")
        except Exception:
            repo.create_file("src/pdf_parser.py", commit_message, clean_code, branch="main")
            print("🎉 Created src/pdf_parser.py on GitHub main branch.")

if __name__ == "__main__":
    run_agent()