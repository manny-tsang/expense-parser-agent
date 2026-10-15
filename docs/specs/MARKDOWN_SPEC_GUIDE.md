# Markdown & Gherkin Specification Drafting Guide

## 1. Core Markdown Formatting Syntax

### Headings & Hierarchy
Use `#` symbols at the start of a line to define document structure. Always leave a blank line after headings.
- `# Document Title` (H1 — Use once at the top for document title)
- `## Major Section` (H2 — Core feature modules or major topics)
- `### Component / Rule` (H3 — Specific rules, schemas, or acceptance criteria)
- `#### Sub-rule` (H4 — Fine-grained technical details)

### Text Formatting & Bolding
- **Bold**: Surround text with double asterisks (`**important term**`). Use this for key parameters, table columns, and system states.
- *Italics*: Surround text with single asterisks (`*note*`).
- **Code / File Names**: Surround inline terms, variables, paths, or function names with single backticks (e.g., `src/app.py`, `category_id`).

### Lists & Sequential Workflow
- **Unordered Lists** (Bullet points): Use a dash `-` or asterisk `*` followed by a space.
- **Ordered Lists** (Sequential steps): Use `1.`, `2.`, `3.` for chronological execution flows.
- **Nested Lists**: Indent bullet points by 2 or 4 spaces underneath a parent bullet.

### Tables for Schemas & Mappings
Tables keep data models, API parameter contracts, and status mappings clean:

| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `merchant_name` | String | Yes | Cleaned string title of the merchant |
| `category_id` | Integer | Yes | Foreign key mapping to category table |

### Blockquotes & Important Guardrails
Use `>` to highlight critical system constraints, module boundary rules, or security guardrails:

> **Module Boundary Constraint**: No raw SQL queries may be executed directly inside `src/app.py`. All database interactions must use `DatabaseRepository`.

---

## 2. Writing User Stories in BDD Gherkin Syntax

To ensure AI Spec Linters can validate requirements for automated testing, acceptance criteria within specs should always follow **Gherkin format**:

- **GIVEN**: The initial state or precondition of the system.
- **WHEN**: The specific action or event executed by the user or system.
- **THEN**: The observable, deterministic outcome that must occur.
- **AND / BUT**: Conjunctions to extend preconditions or outcomes cleanly.

### Example Gherkin Block:
**Scenario: Successfully overriding a single transaction category**
- **GIVEN** a transaction exists with `id = 42` and `category_id = 1` ('Uncategorised')
- **WHEN** the user selects 'Groceries' (`category_id = 5`) from the transaction category dropdown
- **AND** clicks the 'Confirm Update' button
- **THEN** `transaction.category_id` for `id = 42` is updated to `5` in SQLite
- **AND** the parent `merchant.category_id` remains unchanged

---

## 3. Reusable Master Feature Spec Template

When drafting a new specification file under `docs/specs/`, you can copy and fill out this standardized blueprint:

# Feature Specification: [Feature Name]

## 1. Module Overview & Primary Intent
Brief 2–3 sentence summary of what this feature accomplishes, which user problem it solves, and which system files it affects.

## 2. Module Boundaries & Ownership Contracts
- **Primary Source File**: `src/[module_name].py`
- **Allowed Dependencies**: [e.g., `DatabaseRepository`, `pandas`]
- **Forbidden Imports / Operations**: [e.g., No direct SQLite connection inside presentation layer]

## 3. Detailed Technical Requirements & Business Rules
### 3.1 Data Schema / Inputs
Detailed description of inputs, parameters, or database schema additions.

### 3.2 Processing Logic & Edge Cases
1. **Rule 1**: [Specific execution logic]
2. **Rule 2**: [Handling null inputs or API failures]

## 4. User Stories & BDD Acceptance Criteria

### Story 1: [Short Actionable Summary]
**As a** [user role],  
**I want to** [execute specific action],  
**So that** [achieve specific value/outcome].

#### Acceptance Criteria (Gherkin):
**Scenario 1: Happy Path Execution**
- **GIVEN** [precondition]
- **WHEN** [action]
- **THEN** [expected result]

**Scenario 2: Edge Case / Validation Error**
- **GIVEN** [invalid state]
- **WHEN** [action]
- **THEN** [error response or fallback]