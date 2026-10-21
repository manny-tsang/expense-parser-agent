# Feature Specification: Spec Refiner

## 1. Module Overview & Primary Intent
- **Epic Title**: Spec Refiner
- **Epic Description**: As a Delivery Lead, I want to run an automated quality gate on raw feature specification markdown files, so that I can enforce Definition of Ready (DoR) standards, expand edge cases, and harden Gherkin scenarios before creating Jira backlog items.

## 2. Module Boundaries & Ownership Contracts
- **Primary Source File**: `spec_refiner.py`
- **Allowed Dependencies**: `google-genai`, `python-dotenv`, `argparse`, `os`, `sys`, `time`
- **Forbidden Operations**: Must not modify production database `db/personal-expense-tracker.db` or invoke Jira REST APIs directly.

## 3. Detailed Technical Requirements & Business Rules

### 3.1 Input & Staging Output Pipeline
1. **CLI Execution Contract**: Takes a required positional argument pointing to any valid raw markdown spec file path (e.g., `python3 spec_refiner.py <input_spec_path>`).
2. **Staging File Creation**: Reads input `[name].md` and outputs refined contents strictly to `[name].refined.md` in the same directory.
3. **Immutable Source Safety**: The original raw `[name].md` file must remain untouched during refinement execution.
4. **Resilience & Exponential Backoff Retry**: 
   - Wraps Gemini API requests in a dedicated retry function catching `google.genai.errors.ServerError` and 503 status errors.
   - Executes up to 5 retries (`max_retries=5`) calculating delay as `2 ** attempt` seconds (2s, 4s, 8s, 16s, 32s) before raising a `TimeoutError`.

### 3.2 Refinement System Prompt & Advanced Gherkin Linting Rules
The internal LLM prompt (utilizing model `gemini-3.6-flash` via `google-genai` SDK) must enforce five strict transformation rules:

1. **Model Specification**: Explicitly configured to use `gemini-3.6-flash` for high-speed, structured markdown reasoning.
2. **Questions & Clarifications Block**: Injects a section `## 0. Questions & Clarification Needed for Human Sign-Off` at the very top highlighting ambiguous parameters, missing edge cases, or unstated business assumptions.
3. **Advanced Gherkin Hardening (Cucumber.io Standard)**:
   - Evaluates user stories against official Cucumber Gherkin reference constructs (`https://cucumber.io/docs/gherkin/reference/`).
   - Converts basic, single-line scenarios into comprehensive acceptance criteria sets.
   - **Scenario Outlines & Examples**: Reserves `Scenario Outline` paired with `Examples:` data tables specifically for explicit entry/exit boundary values, threshold limits, and data permutations. Standard declarative `Scenario:` blocks must be used for straightforward behavioral flows.
   - **Concrete Data Isolation**: Strict prohibition against hardcoding arbitrary numbers or static mock data directly inside standard step sentences unless tied to a defined `Examples:` table or `Data Table` precondition.
   - **Data Tables & Doc Strings**: Mandates inline Gherkin `Data Tables` for complex entity preconditions and initial state setups.
   - **Comprehensive Multi-Outcome Coverage**: Ensures user stories exhaustively capture ALL happy path scenarios, ALL applicable boundary and edge case scenarios, and ALL failure or error state scenarios.
4. **Edge Case & Module Boundary Expansion**: Automatically inserts processing logic for zero-spend states, missing reference data, and boundary limits while verifying compliance with `ARCHITECTURE.md`.
5. **Clean Markdown Output**: Guarantees clean Markdown output without wrapping the document in top-level code fences.

## 4. User Stories & BDD Acceptance Criteria

### Story 1: Process Spec-Agnostic Markdown Input to Staging Output
**As a** Delivery Lead,  
**I want to** pass any valid markdown spec file path into the refiner script,  
**So that** a `.refined.md` staging file is automatically generated for human review without altering the source spec.

#### Acceptance Criteria (Gherkin):

**Scenario 1: Agentic refinement of feature specification markdown file**
- **GIVEN** a feature specification markdown file with file format of `.md` is created in the `docs/specs` directory
- **AND** the specification explicitly indicates the use of model `gemini-3.6-flash` via `google-genai` SDK
- **AND** the `spec_refiner.py` agent has been generated, reviewed, validated, and approved for use
- **WHEN** the command `python3 spec_refiner.py <input_spec_path>` is executed in the terminal
- **THEN** `spec_refiner.py` initializes `gemini-3.6-flash`
- **AND** executes the request using exponential backoff retries (`2 ** attempt`) for 503 server demand spikes
- **AND** generates a refined staging file labeled as `<original_file_name>.refined.md` in the `docs/specs` directory
- **AND** the original `.md` specification remains completely unmodified

**Scenario 2: Handling invocation with a non-existent specification file path**
- **GIVEN** a target file path passed as a CLI argument does not exist in the filesystem
- **AND** the `spec_refiner.py` script has been generated, reviewed, validated, and approved for use
- **WHEN** the command `python3 spec_refiner.py <invalid_file_path>` is executed in the terminal
- **THEN** `spec_refiner.py` detects that no file exists at `<invalid_file_path>`
- **AND** displays an error message indicating the specification file was not found
- **AND** terminates execution immediately with exit code 1
- **AND** does not issue a request to the Gemini API