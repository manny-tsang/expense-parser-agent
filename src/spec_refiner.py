import argparse
import os
import sys
import time
from typing import Optional
from dotenv import load_dotenv
from google import genai
from google.genai import types

SYSTEM_PROMPT = """You are an expert Agile Delivery Lead and Technical Specification Refiner.
Your task is to refine the provided raw feature specification markdown according to strict Definition of Ready (DoR) standards and Cucumber Gherkin guidelines.

Follow these strict transformation rules:
1. Questions & Clarifications Block:
   Inject a section `## 0. Questions & Clarification Needed for Human Sign-Off` at the very top highlighting ambiguous parameters, missing edge cases, or unstated business assumptions.

2. Advanced Gherkin Hardening (Cucumber.io Standard):
   - Evaluate user stories against official Cucumber Gherkin reference constructs (https://cucumber.io/docs/gherkin/reference/).
   - Convert basic, single-line scenarios into comprehensive acceptance criteria sets.
   - Scenario Outlines & Examples: Mandate the use of `Scenario Outline` paired with `Examples:` data tables strictly for dynamic business logic permutations and boundary value inputs.
   - Data Tables & Doc Strings: Mandate inline Gherkin `Data Tables` for complex entity inputs and step preconditions.
   - Multi-Outcome Coverage: Ensure every story includes a Happy Path scenario, a Boundary/Edge Case scenario, and an Explicit Error/Failure state.

3. Edge Case & Module Boundary Expansion:
   - Automatically insert processing logic for zero-spend states, missing reference data, and boundary limits while verifying compliance with `ARCHITECTURE.md`.

4. Clean Markdown Output:
   - Guarantee clean Markdown output without wrapping the top-level document in markdown code fences (e.g., ```markdown ... ```). Output raw markdown directly.
"""


class SpecRefiner:
    """Agent that refines raw feature specification markdown files using Gemini AI."""

    def __init__(self, model_name: str = "gemini-3.6-flash") -> None:
        """Initialize SpecRefiner with target Gemini model and API client."""
        self.model_name = model_name
        self.client = genai.Client()

    @staticmethod
    def _derive_staging_path(input_path: str) -> str:
        """Derive the .refined.md staging output path from the input file path."""
        if input_path.endswith(".md"):
            return input_path[:-3] + ".refined.md"
        base, _ = os.path.splitext(input_path)
        return f"{base}.refined.md"

    @staticmethod
    def _strip_outer_code_fences(markdown_content: str) -> str:
        """Strip top-level markdown code fences if present in output."""
        cleaned = markdown_content.strip()
        if cleaned.startswith("```markdown") and cleaned.endswith("```"):
            return cleaned[11:-3].strip()
        if cleaned.startswith("```") and cleaned.endswith("```"):
            return cleaned[3:-3].strip()
        return cleaned

    def refine_spec(self, spec_content: str) -> str:
        """Refine raw spec markdown content using the gemini-3.6-flash model with backoff retry."""
        config = types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=0.2,
        )
        delays = [2, 4, 8, 16, 32]
        for attempt in range(len(delays) + 1):
            try:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=spec_content,
                    config=config,
                )
                refined_text = response.text or ""
                return self._strip_outer_code_fences(refined_text)
            except Exception as e:
                err_msg = str(e)
                code = getattr(e, "code", None) or getattr(e, "status_code", None)
                is_503 = (
                    code == 503
                    or "503" in err_msg
                    or "UNAVAILABLE" in err_msg.upper()
                    or "HIGH DEMAND" in err_msg.upper()
                )
                if is_503 and attempt < len(delays):
                    time.sleep(delays[attempt])
                    continue
                raise

    def refine_file(self, input_path: str) -> str:
        """Read source file, generate refined specification, and write to staging output file."""
        with open(input_path, "r", encoding="utf-8") as f:
            raw_content = f.read()

        refined_content = self.refine_spec(raw_content)
        output_path = self._derive_staging_path(input_path)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(refined_content)

        return output_path


def main() -> None:
    """CLI entry point for spec refiner quality gate."""
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Run quality gate refinement on raw feature specification markdown files."
    )
    parser.add_argument(
        "input_spec_path",
        type=str,
        help="Path to the raw specification markdown file.",
    )
    args = parser.parse_args()

    input_path = args.input_spec_path

    if not os.path.exists(input_path) or not os.path.isfile(input_path):
        print(
            f"Error: Specification file not found at '{input_path}'.",
            file=sys.stderr,
        )
        sys.exit(1)

    refiner = SpecRefiner(model_name="gemini-3.6-flash")
    staging_file = refiner.refine_file(input_path)
    print(f"Refined specification successfully created at: {staging_file}")


if __name__ == "__main__":
    main()