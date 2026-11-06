import argparse
import os
import re
import sys
import time
from typing import Optional

from dotenv import load_dotenv
from google import genai
from google.genai import errors


SYSTEM_PROMPT = """You are an expert Delivery Lead and Technical Writer. Your task is to refine and harden raw feature specification markdown files according to Definition of Ready (DoR) standards.

You MUST enforce the following strict transformation rules:

1. **Top-Level Header & Pass Count Tracking**:
   - Every refined specification MUST start with top-level pass metadata header `Refinement Pass: X` (where X is the current refinement pass number provided in the input).

2. **Questions & Clarifications Block (3-Part Schema & 3-Pass Cap)**:
   - Inject a section titled `## 0. Questions & Clarification Needed for Human Sign-Off` at the very top (immediately following `Refinement Pass: X`) highlighting ambiguous parameters, missing edge cases, unstated business assumptions, or architectural risks requiring human decision.
   - **Standardized 3-Part Question Schema**: Every question generated in Section 0 MUST strictly follow a structured 3-part format, separated into distinct bullet points (DO NOT put into a table format, this is difficult to read in an IDE like VS Code):
     - **Question**: Clear, concise description of the specific requirement or ambiguity.
     - **Justification & Impact**: Explanation of why clarification is required and which system component or business rule is affected.
     - **Proposed Default / Response**: Concrete recommended assumption or fallback logic for immediate human sign-off.
   - **3-Pass Cap & Backlog Overflow Rule**: Refinement is strictly capped at a maximum of 3 iteration passes. When the current pass count is 3 or higher (Refinement Pass >= 3), all remaining unresolved non-critical or edge-case questions MUST automatically spill over into a section at the bottom titled `## 5. Deferred Questions & Backlog Candidate Items` instead of blocking DoR sign-off in Section 0.

3. **Advanced Gherkin Hardening (Cucumber.io Standard)**:
   - Evaluate and harden user stories against official Cucumber Gherkin reference constructs (https://cucumber.io/docs/gherkin/reference/).
   - Convert basic, single-line scenarios into comprehensive acceptance criteria sets.
   - **Scenario Outlines & Examples**: Reserve `Scenario Outline` paired with `Examples:` data tables specifically for explicit entry/exit boundary values, threshold limits, and data permutations. Standard declarative `Scenario:` blocks must be used for straightforward behavioral flows.
   - **Concrete Data Isolation**: Strict prohibition against hardcoding specific arbitrary numbers, transaction IDs, or static mock data directly inside standard `Scenario:` step sentences unless tied to a defined `Examples:` table or `Data Table` precondition.
   - **Data Tables & Doc Strings**: Mandate inline Gherkin `Data Tables` for complex entity preconditions and initial state setups.
   - **Comprehensive Multi-Outcome Coverage**: Ensure user stories exhaustively capture ALL happy path scenarios, ALL applicable boundary and edge case scenarios, and ALL failure or error state scenarios.

4. **Edge Case & Module Boundary Expansion**:
   - Automatically insert processing logic and scenarios for zero-spend states, missing reference data, unhandled exceptions, and boundary limits.
   - Verify and ensure compliance with module boundaries and architectural guidelines specified in ARCHITECTURE.md.

5. **Clean Markdown Output**:
   - Return clean, well-structured Markdown output directly.
   - DO NOT wrap the entire document in top-level triple backtick code fences (e.g., do not use ```markdown ... ```).
"""


class SpecRefiner:
    """Agentic spec refiner using Gemini 3.6 Flash for quality gate enforcement."""

    def __init__(self, api_key: Optional[str] = None, model_name: str = "gemini-3.6-flash") -> None:
        load_dotenv()
        self.model_name = model_name
        if api_key:
            self.client = genai.Client(api_key=api_key)
        else:
            self.client = genai.Client()

    @staticmethod
    def extract_pass_count(spec_text: str) -> int:
        """Detect existing 'Refinement Pass: X' metadata header."""
        match = re.search(r"Refinement Pass:\s*(\d+)", spec_text, re.IGNORECASE)
        if match:
            return int(match.group(1))
        return 0

    @staticmethod
    def inject_pass_header(content: str, pass_count: int) -> str:
        """Inject or update 'Refinement Pass: X' as top-level metadata header."""
        header_pattern = r"^Refinement Pass:\s*\d+.*$"
        new_header = f"Refinement Pass: {pass_count}"

        if re.search(header_pattern, content, re.MULTILINE | re.IGNORECASE):
            return re.sub(header_pattern, new_header, content, flags=re.MULTILINE | re.IGNORECASE)
        return f"{new_header}\n\n{content}"

    @staticmethod
    def get_output_path(input_path: str) -> str:
        """Derive the .refined.md staging output path from input path."""
        if input_path.endswith(".refined.md"):
            return input_path
        if input_path.endswith(".md"):
            return input_path[:-3] + ".refined.md"
        base, _ = os.path.splitext(input_path)
        return f"{base}.refined.md"

    @staticmethod
    def _clean_markdown(text: str) -> str:
        """Strip wrapping top-level code fences if present."""
        cleaned = text.strip()
        if cleaned.startswith("```markdown"):
            cleaned = cleaned[11:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
        return cleaned.strip()

    def _execute_with_retry(self, content: str, max_retries: int = 5) -> str:
        """Executes Gemini API request with exponential backoff on server errors or 503s."""
        print(f"Submitting payload to Gemini API model '{self.model_name}'...")
        last_exception: Optional[Exception] = None
        for attempt in range(0, max_retries + 1):
            if attempt > 0:
                delay = 2 ** attempt
                print(
                    f"Warning: Gemini API call failed with temporary error. Retrying in {delay}s "
                    f"(attempt {attempt}/{max_retries})...",
                    file=sys.stderr,
                )
                time.sleep(delay)
            try:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=content,
                    config=genai.types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT
                    ),
                )
                if response.text:
                    return response.text
                return ""
            except errors.ServerError as e:
                last_exception = e
            except Exception as e:
                is_503 = (
                    "503" in str(e)
                    or getattr(e, "code", None) == 503
                    or getattr(e, "status_code", None) == 503
                )
                if is_503 or isinstance(e, errors.APIError):
                    last_exception = e
                else:
                    raise e

        raise TimeoutError(
            f"Max retries ({max_retries}) exceeded due to Gemini server or API errors."
        ) from last_exception

    def refine_spec(self, spec_text: str, pass_count: Optional[int] = None) -> str:
        """Refines spec markdown text using LLM system prompt and updates pass metadata."""
        if pass_count is None:
            pass_count = self.extract_pass_count(spec_text) + 1

        prompt_content = (
            f"Refinement Pass: {pass_count}\n\n"
            f"Please refine the following raw feature specification markdown file:\n\n"
            f"{spec_text}"
        )
        raw_output = self._execute_with_retry(prompt_content)
        cleaned_output = self._clean_markdown(raw_output)
        return self.inject_pass_header(cleaned_output, pass_count)

    def refine_file(self, input_path: str) -> str:
        """Reads input spec file, refines content, and writes staging output file."""
        if not os.path.exists(input_path):
            print(f"Error: Specification file not found at path '{input_path}'", file=sys.stderr)
            sys.exit(1)

        print(f"Starting specification refinement for target path: {input_path}")
        with open(input_path, "r", encoding="utf-8") as f:
            raw_content = f.read()

        output_path = self.get_output_path(input_path)

        # Inspect pass count in both raw input and staging output file if present
        current_pass = self.extract_pass_count(raw_content)
        if os.path.exists(output_path) and output_path != input_path:
            try:
                with open(output_path, "r", encoding="utf-8") as f:
                    staging_content = f.read()
                staging_pass = self.extract_pass_count(staging_content)
                current_pass = max(current_pass, staging_pass)
            except Exception:
                pass

        next_pass = current_pass + 1
        print(f"Active Refinement Pass: {next_pass}")

        refined_content = self.refine_spec(raw_content, pass_count=next_pass)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(refined_content)

        print(f"Refined specification created successfully at: {output_path}")
        return output_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run quality gate refinement on raw feature specification markdown files."
    )
    parser.add_argument(
        "input_spec_path",
        type=str,
        help="Path to the input markdown feature specification file.",
    )
    args = parser.parse_args()

    refiner = SpecRefiner()
    refiner.refine_file(args.input_spec_path)


if __name__ == "__main__":
    main()