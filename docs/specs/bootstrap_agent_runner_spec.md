# Feature Specification: Bootstrap Agent Runner Engine

## 1. Module Overview & Primary Intent
- **Epic Title**: Spec-Driven Code Generation Agent Engine
- **Epic Description**: As a Delivery Lead, I want an automated code generation engine that reads formal markdown specifications and target files to produce role-scoped, executable Python code and sync it automatically to version control.

## 2. Module Boundaries & Ownership Contracts
- **Primary Source File**: `agent_runner.py`
- **Allowed Dependencies**: `google-genai`, `python-dotenv`, `argparse`, `github`, `os`, `sys`, `time`
- **Forbidden Operations**: Must not modify database schemas directly or invoke Jira REST endpoints directly (managed via GitHub Smart Commit hooks).

## 3. Detailed Technical Requirements & Business Rules

### 3.1 Input & Execution Pipeline
1. **CLI Execution Contract**: Takes required flags `--spec`, `--target`, and `--commit-msg`, with an optional `--context` list of reference files.
2. **Context & In-Place Code Parsing**:
   - Reads the input spec markdown file.
   - Reads existing code in the target path if present to allow in-place updates.
   - Appends contents of all specified context files to supply cross-module interface awareness.
3. **Role-Scoped Prompt Isolation**:
   - Assigns a specialized system prompt based on target file type (`src/app.py` UI developer vs. backend software engineer).

### 3.2 Resiliency & API Handling
1. **Model Specification**: Primary execution utilizes `gemini-3.6-flash` at `temperature=0.1`.
2. **Exponential Backoff & 503 Retry**: Wraps Gemini API requests in an exponential backoff loop (retrying on HTTP 503 high demand spikes up to 5 attempts).
3. **Robust Fence Parsing**: Extracts generated Python code using outer `rsplit` logic to prevent string truncation when specs or prompts contain nested code block references.
4. **Automated Version Control Sync**: Uses `PyGithub` to commit and push updated target code directly to the GitHub `main` branch with the provided smart commit message.

## 4. User Stories & BDD Acceptance Criteria

### Story 1: Execute Spec-Driven Code Generation with Fault-Tolerant Retries
**As a** Delivery Lead,  
**I want to** pass a specification, target path, and commit message to `agent_runner.py`,  
**So that** executable Python code is generated and committed to GitHub even during temporary Gemini API demand spikes.

#### Acceptance Criteria (Gherkin):

**Scenario 1: Successful code generation and remote commit**
- **GIVEN** a valid specification exists at `docs/specs/meta_spec_refiner_spec.md`
- **WHEN** `python3 agent_runner.py --spec docs/specs/meta_spec_refiner_spec.md --target src/spec_refiner.py --commit-msg "PET-33 #devcomplete: Generate Async Spec Refiner"` is executed
- **THEN** `agent_runner.py` sends the prompt to `gemini-3.6-flash`
- **AND** writes the clean Python code to `src/spec_refiner.py`
- **AND** pushes the commit to the GitHub `main` branch triggering workflow transitions

**Scenario 2: Handling 503 Server Unavailable Spikes**
- **GIVEN** the Gemini API returns a 503 High Demand error
- **WHEN** `agent_runner.py` executes code generation
- **THEN** the script catches the 503 error, logs a retry message, and waits with exponential backoff (2s, 4s, 8s, 16s, 32s) before retrying
- **AND** successfully completes generation upon server availability# Feature Specification: Meta-Tooling Agent Runner Engine

## 1. Module Overview & Primary Intent
- **Epic Title**: Spec-Driven Code Generation Agent Engine
- **Epic Description**: As a Delivery Lead, I want an automated code generation engine that reads formal markdown specifications and target files to produce role-scoped, executable Python code and sync it automatically to version control.

## 2. Module Boundaries & Ownership Contracts
- **Primary Source File**: `agent_runner.py`
- **Allowed Dependencies**: `google-genai`, `python-dotenv`, `argparse`, `github`, `os`, `sys`, `time`
- **Forbidden Operations**: Must not modify database schemas directly or invoke Jira REST endpoints directly (managed via GitHub Smart Commit hooks).

## 3. Detailed Technical Requirements & Business Rules

### 3.1 Input & Execution Pipeline
1. **CLI Execution Contract**: Takes required flags `--spec`, `--target`, and `--commit-msg`, with an optional `--context` list of reference files.
2. **Context & In-Place Code Parsing**:
   - Reads the input spec markdown file.
   - Reads existing code in the target path if present to allow in-place updates.
   - Appends contents of all specified context files to supply cross-module interface awareness.
3. **Role-Scoped Prompt Isolation**:
   - Assigns a specialized system prompt based on target file type (`src/app.py` UI developer vs. backend software engineer).

### 3.2 Resiliency & API Handling
1. **Model Specification**: Primary execution utilizes `gemini-3.6-flash` at `temperature=0.1`.
2. **Exponential Backoff & 503 Retry**: Wraps Gemini API requests in an exponential backoff loop (retrying on HTTP 503 high demand spikes up to 5 attempts).
3. **Robust Fence Parsing**: Extracts generated Python code using outer `rsplit` logic to prevent string truncation when specs or prompts contain nested code block references.
4. **Automated Version Control Sync**: Uses `PyGithub` to commit and push updated target code directly to the GitHub `main` branch with the provided smart commit message.

## 4. User Stories & BDD Acceptance Criteria

### Story 1: Execute Spec-Driven Code Generation with Fault-Tolerant Retries
**As a** Delivery Lead,  
**I want to** pass a specification, target path, and commit message to `agent_runner.py`,  
**So that** executable Python code is generated and committed to GitHub even during temporary Gemini API demand spikes.

#### Acceptance Criteria (Gherkin):

**Scenario 1: Successful code generation and remote commit**
- **GIVEN** a valid specification exists at `docs/specs/meta_spec_refiner_spec.md`
- **WHEN** `python3 agent_runner.py --spec docs/specs/meta_spec_refiner_spec.md --target src/spec_refiner.py --commit-msg "PET-33 #devcomplete: Generate Async Spec Refiner"` is executed
- **THEN** `agent_runner.py` sends the prompt to `gemini-3.6-flash`
- **AND** writes the clean Python code to `src/spec_refiner.py`
- **AND** pushes the commit to the GitHub `main` branch triggering workflow transitions

**Scenario 2: Handling 503 Server Unavailable Spikes**
- **GIVEN** the Gemini API returns a 503 High Demand error
- **WHEN** `agent_runner.py` executes code generation
- **THEN** the script catches the 503 error, logs a retry message, and waits with exponential backoff (2s, 4s, 8s, 16s, 32s) before retrying
- **AND** successfully completes generation upon server availability