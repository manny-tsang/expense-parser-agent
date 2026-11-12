# Feature Specification: Jira Agent Runner

## 1. Module Overview & Primary Intent
- **Epic Title**: Jira Agent Runner
- **Epic Description**: As a Delivery Lead, I want to automate the parsing of refined Markdown specifications into structured Jira Epics and BDD User Stories via the Jira REST API v3, so that backlog creation is deterministic, standardized, and synchronized with our Spec-Driven Development (SDD) workflow.

## 2. Module Boundaries & Ownership Contracts
- **Primary Source File**: `jira_agent_runner.py`
- **Allowed Dependencies**: `google-genai`, `python-dotenv`, `requests`, `argparse`, `json`, `os`, `re`
- **Forbidden Operations**: 
  - Must not modify local application source code (`src/*.py`) or SQLite databases (`db/personal-expense-tracker.db`).
  - Must not execute Git commits or push changes to GitHub.
  - Must never re-create an Epic if the spec references an existing Jira Epic key pattern (`PET-[0-9]+`).

## 3. Detailed Technical Requirements & Business Rules

### 3.1 Environment & Credential Validation
1. **Environment Loading**: Loads environment variables from `.env` using `load_dotenv(override=True)` prior to reading configuration values.
2. **Required Variables**: Validates that `GEMINI_API_KEY`, `JIRA_BASE_URL`, `JIRA_USER_EMAIL`, and `JIRA_API_TOKEN` are non-empty; raises a `ValueError` immediately if any required credential is missing.
3. **Target Project Scope**: All generated Epics and Stories target Jira project key `PET`.

### 3.2 CLI Execution & Dry-Run Pipeline
1. **CLI Arguments**:
   - `--spec` (required `str`): Path to the input specification Markdown file (e.g., `docs/specs/budget_projection_spec.refined.md`).
   - `--dry-run` (optional flag): Parses the specification via Gemini and outputs the structured JSON payload to stdout without invoking Jira REST API mutation endpoints.
2. **Input Path Validation**: Verifies that `--spec` exists and is a regular file (not a directory) before invoking the Gemini API.

### 3.3 Gemini Spec Parsing & Strict Story Prefix Mapping
1. **Model Configuration**: Uses `gemini-3.6-flash` via `google-genai` SDK with `temperature=0.1` for deterministic structured JSON extraction.
2. **Epic Resolution Rules**:
   - Inspects the specification for existing Jira Epic keys (e.g., `PET-4`, `PET-7`). Existing Epic keys MUST NOT be added to `new_epics`.
   - Populates `new_epics` ONLY when the specification defines a new Epic without an assigned `PET-<number>` key.
   - Maps `target_epic_key_or_name` on every child story to either the existing `PET-<number>` key or the newly defined Epic `summary`.
3. **Composable Story Component Prefix Rules**:
   Every generated Story `title` MUST begin with a bracketed component tag composed of one or more applicable stack layers, separated by pipes (` | `) in canonical order (`UI` -> `PY` -> `DB`):
   - **Atomic Layer Definitions**:
     - **`UI`**: Streamlit presentation components, layouts, CSS styling, user input controls, charts, or UI state/formatting residing in `src/app.py`.
     - **`PY`**: Python business logic, calculations, input validation, PDF parsing, CLI runners, or data transformations (e.g., `src/pdf_parser.py`, `spec_refiner.py`, or Python processing within `src/app.py` / `src/repository.py`).
     - **`DB`**: SQLite schema changes, DDL/DML SQL queries, database aggregations, or persistence contracts residing in `src/repository.py` (`DatabaseRepository`).
   - **Composition & Formatting Rules**:
     - Tags are **not** mutually exclusive; combine all layers touched by the story's acceptance criteria using ` | ` inside square brackets with single outer padding spaces (e.g., `[ UI | PY | DB ] Story Title`).
     - **Common Patterns**:
       - `[ UI ]`: Pure layout, CSS, or static visual rendering changes.
       - `[ UI | PY ]`: Interactive Streamlit widgets requiring client-side Python validation, session state handling, or DataFrame formatting.
       - `[ PY | DB ]`: Backend data queries and SQL aggregations paired with Python calculation or filtering logic.
       - `[ UI | PY | DB ]`: Full-stack vertical slices spanning Streamlit UI controls, Python business logic, and SQLite repository operations.
4. **JSON Output Sanitization**: Strips wrapping ` ```json ` and ` ``` ` markdown code fences from the model response prior to `json.loads()` parsing.

### 3.4 Jira REST API v3 Issue Creation & Initial Transition
1. **Authentication**: Authenticates against `{JIRA_BASE_URL}/rest/api/3/issue` using HTTP Basic Auth (`(JIRA_USER_EMAIL, JIRA_API_TOKEN)`).
2. **Atlassian Document Format (ADF)**: Wraps story and epic descriptions in valid Jira API v3 ADF JSON (`{"type": "doc", "version": 1, ...}`).
3. **Parent Linking**: Links child `Story` issues to their parent Epic via `fields.parent = {"key": parent_key}`.
4. **Automatic Initial Workflow Transition**: Immediately after creating each Story, queries `/rest/api/3/issue/{issue_key}/transitions` and executes the transition matching keyword `"define"` (moving the story to `IN DESIGN`).

## 4. User Stories & BDD Acceptance Criteria

### Story 1: Dry-Run Specification Parsing with Deterministic Prefixes
**AS A** Delivery Lead,  
**I WANT TO** run `jira_agent_runner.py` with `--dry-run` against a refined specification,  
**SO THAT** I can verify Epic mapping and `[ DB | PY | UI ]` story prefixes before creating live Jira tickets.

#### Acceptance Criteria (Gherkin):

**Scenario 1: Previewing parsed Epics and prefixed Stories in dry-run mode**
- **GIVEN** a valid specification markdown file exists at `<spec_path>`
- **AND** valid `GEMINI_API_KEY`, `JIRA_BASE_URL`, `JIRA_USER_EMAIL`, and `JIRA_API_TOKEN` values are configured in `.env`
- **WHEN** `python3 jira_agent_runner.py --spec <spec_path> --dry-run` is executed
- **THEN** `jira_agent_runner.py` parses the specification using `gemini-3.6-flash`
- **AND** assigns `[ DB ]` to stories targeting `src/repository.py`, `[ PY ]` to standalone backend processors, and `[ UI ]` to stories targeting `src/app.py`
- **AND** prints the formatted JSON payload to the terminal
- **AND** makes zero `POST` requests to the Jira REST API

### Story 2: Live Jira Epic and Story Creation with Initial Transition
**AS A** Delivery Lead,  
**I WANT TO** execute `jira_agent_runner.py` without `--dry-run`,  
**SO THAT** new Epics and linked Stories are created in Jira project `PET` and automatically transitioned to `IN DESIGN`.

#### Acceptance Criteria (Gherkin):

**Scenario 1: Creating a new Epic and transitioning child Stories**
- **GIVEN** a valid specification markdown file defining a new Epic and child Stories
- **WHEN** `python3 jira_agent_runner.py --spec <spec_path>` is executed
- **THEN** a new `Epic` issue is created in Jira project `PET` via `/rest/api/3/issue`
- **AND** each child `Story` is created with `fields.parent.key` set to the new Epic key
- **AND** each child `Story` is automatically transitioned using the `"define"` transition keyword

**Scenario 2: Guardrail against duplicating existing Jira Epics**
- **GIVEN** a specification referencing an existing Epic key matching `PET-[0-9]+`
- **WHEN** `python3 jira_agent_runner.py --spec <spec_path>` is executed
- **THEN** `jira_agent_runner.py` skips Epic creation for that key
- **AND** links child Stories directly to the existing `PET-[0-9]+` parent key