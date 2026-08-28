# Specification: Merchant & Transaction Categorisation UI

## 1. Objective
AS A Personal Tracker User  
I WANT TO manage canonical merchant entities in SQLite and map them to categories or override individual transactions via the Streamlit UI  
SO THAT I can accurately categorize recurring merchants globally while retaining the flexibility to reclassify unique, one-off transactions.

## 2. Technical Stack & Dependencies
- **Language**: Python 3.x
- **UI Framework**: Streamlit (`src/app.py`), `streamlit-option-menu`
- **Data Engine & Repository**: `src/repository.py` (`DatabaseRepository`), `src/pdf_parser.py` (`parse_statement`), `pandas`
- **Database Target**: `db/personal-expense-tracker.db`
- **Database Ownership Contract**:
  - `src/repository.py` exclusively owns database schema definitions, table migrations, connection management, and reference data seeds.
  - `src/app.py` executes data reads and updates strictly through `DatabaseRepository` methods without defining table structures or mock fallback classes.

---

## 3. Data Model & Architecture

### 3.1 Database Schema Reference (`db/personal-expense-tracker.db`)
The schema relies on the canonical `merchant` table created during parser initialization:

- **`category` Table**: Stores category entities (`id`, `category_name`).
- **`merchant` Table**: Stores unique merchant entities (`id`, `merchant_name`, `category_id`).
- **`transaction` Table**: Links each record to `merchant.id` via `merchant_id`. `transaction.category_id` serves purely as an optional explicit override (`NULL` indicates no override).

### 3.2 UI Query Contracts (`src/app.py`)
- **Add New Category**: Inserts a new unique record into the `category` table via `INSERT INTO "category" ("category_name") VALUES (?)`.
- **Global Merchant Mapping**: Updates `category_id` directly on the `merchant` record via `UPDATE merchant SET category_id = ? WHERE id = ?`.
- **Transaction Override**: Updates `category_id` directly on the specific `transaction` row via `UPDATE "transaction" SET category_id = ? WHERE id = ?`.

## 4. UI Design Principles & Workflow Layout (`src/app.py`)

### 4.1 Navigation Expansion
Expand sidebar navigation in `render_sidebar()` to include the new view:
- **Menu Options**: `["Dashboard", "Upload", "Categorise", "Charts"]`
- **Icons**: `["house", "cloud-upload", "tag", "bar-chart"]`

### 4.2 Categorise Page Two-Row Layout Structure
The Categorise view layout MUST be organized into **two main rows**:

- **Row 1 (3 Equal Columns)**:
  - **Column 1**: `Add new category` section.
  - **Column 2**: `Merchant mapping` section.
  - **Column 3**: `Update transaction category` section.
- **Row 2 (Full Width)**:
  - `Uncategorised merchants` section listing table across full page width.

---

### 4.3 Section 1: Add New Category (`Row 1, Column 1`)
- **Container Wrapper**: Enclosed inside `st.container(border=True, height="stretch")`.
- **Section Heading**: `st.subheader("Add new category")`
- **Description Text**: `st.markdown("Adding a new category for merchants that do not fit pre-defined categories enables more accurate financial statistics.")`
- **UI Input Components**:
  - **Category Name Input**: `st.text_input("Category name", max_chars=50, key="new_category_name_input")`
  - **Action Button**: `st.button("Add category", type="primary", key="add_new_category_btn")`
- **Validation Rules (Executed on Button Click)**:
  1. **Non-Empty Check**: Input must not be empty or whitespace-only.
  2. **Character Set Restrictions**: Input must contain ONLY letters, spaces, ampersands (`&`), hyphens (`-`), or slashes (`/`). (Regex: `^[A-Za-z\s&\-\/]+$`).
  3. **Duplicate Check**: Case-insensitive check against existing database category names.
  - If any validation fails, render `st.error(...)` with the specific error message and halt.
- **Modal Confirmation (`@st.dialog(title="Confirm new category", width="small")`)**:
  - Signature: `def confirm_add_category_dialog(category_name: str) -> None:`
  - **Repository Instantiation**: Must instantiate `DatabaseRepository(DB_PATH)` directly inside the dialog function body prior to calling database methods (e.g., `repo = DatabaseRepository(DB_PATH)`). Do NOT pass `DatabaseRepository` instance objects as parameters into `@st.dialog` functions.
  - When `"Add category"` passes validation, trigger the confirmation dialog directly:
    - **Modal Title**: `"Confirm new category"`
    - **Modal Width**: `width="small"`
    - **Modal Body Text**: `Please confirm the addition of the new '<category_name>' category.`
    - **Action Buttons (`col1, col2`)**:
      - **"Cancel"** (`use_container_width=True`): Closes modal and returns to page without changes (`st.rerun()`).
      - **"Add"** (`type="primary"`, `use_container_width=True`): Inserts new record into `category` table and invokes `st.rerun()`.

---

### 4.4 Section 2: Merchant Mapping (`Row 1, Column 2`)
- **Container Wrapper**: Enclosed inside `st.container(border=True, height="stretch")`.
- **Section Heading**: `st.subheader("Merchant mapping")`
- **Description Text**: `st.markdown("Select an uncategorised merchant and a category to create a new mapping, re-categorising ALL transactions made at the selected merchant.")`
- **UI Input Components**:
  - **Merchant Selector**: `st.selectbox("Merchant", options=["Select a merchant"] + uncat_list, key="global_merchant_select")`
    - Default selection MUST be `"Select a merchant"`.
  - **Category Selector**: `st.selectbox("Category", options=["Select a category"] + category_list, key="global_category_select")`
    - Default selection MUST be `"Select a category"`.
  - **Action Button**: `st.button("Save mapping", type="primary", key="save_global_mapping")`
- **Validation & Modal Confirmation Logic (`@st.dialog(title="Confirm mapping", width="small")`)**:
  - Signature: `def confirm_merchant_mapping_dialog(selected_merchant: str, selected_category: str, target_id: Any, cat_id: int) -> None:`
  - **Repository Instantiation**: Must instantiate `DatabaseRepository(DB_PATH)` directly inside the dialog function body.
  - When `"Save mapping"` is clicked:
    - Check that `Merchant` != `"Select a merchant"` AND `Category` != `"Select a category"`.
    - If either is unselected, render `st.error("Please select both a merchant and a category before saving.")` and halt.
    - If both are valid, invoke the modal dialog directly:
      - **Modal Title**: `"Confirm mapping"`
      - **Modal Width**: `width="small"`
      - **Modal Body Text**: `Please confirm that all transactions for '<selected_merchant>' are to be mapped to the '<selected_category>' category.`
      - **Action Buttons Layout (`col1, col2`)**:
        - **"Cancel"** (`use_container_width=True`): Closes modal and returns to page without changes (`st.rerun()`).
        - **"Save"** (`type="primary"`, `use_container_width=True`): Executes `update_merchant_category(...)` in repository and invokes `st.rerun()`.
      - **State Leak Prevention Rule**: Do NOT store sticky boolean flags in `st.session_state` (e.g., `show_global_dialog = True`) that persist across unrelated widget interactions. Call `@st.dialog` functions directly or reset state flags immediately upon invocation.

---

### 4.5 Section 3: Update Transaction Category (`Row 1, Column 3`)
- **Container Wrapper**: Enclosed inside `st.container(border=True, height="stretch")`.
- **Section Heading**: `st.subheader("Update transaction category")`
- **Description Text**: `st.markdown("Update the category for a single transaction where the default category is not suitable. Example: 'BP' transaction not for 'Fuel'.")`
- **UI Input Components**:
  - **Transaction Selector**: `st.selectbox("Transaction", options=tx_ids, format_func=lambda tx_id: tx_display_map.get(tx_id, "Select a transaction"), key="selected_tx_dropdown")`
    - `tx_ids`: List of primitive IDs starting with `None` for placeholder: `[None] + tx_df["id"].tolist()`.
    - `tx_display_map`: Dictionary mapping `tx_id` -> formatted label string (`<trans_date> | <merchant> | <purchase_currency> <txn_amount>`). Placeholder `None` maps to `"Select a transaction"`.
    - `tx_cat_map`: Dictionary mapping `tx_id` -> current category name (`category_name`). Placeholder `None` maps to `""`.
  - **Category Selection Layout (2 Sub-Columns)**:
    - **Sub-column 1 (`Current category`)**:
      - Read-only text input dynamically keyed to avoid Streamlit state locking:
        `st.text_input("Current category", value=tx_cat_map.get(selected_tx_id, ""), disabled=True, key=f"current_cat_display_{selected_tx_id}")`.
      - When `selected_tx_id` is `None`, value MUST be `""`.
    - **Sub-column 2 (`New category`)**: `st.selectbox("New category", options=["Select a category"] + category_list, key="tx_cat_select")`
      - Default selection MUST be `"Select a category"`.
  - **Action Button**: `st.button("Update transaction category", type="primary", key="update_tx_category")`
- **Validation & Modal Confirmation Logic (`@st.dialog(title="Confirm transaction category update", width="small")`)**:
  - Signature: `def confirm_tx_category_dialog(current_cat_name: str, selected_new_cat: str, selected_tx_id: int, new_cat_id: int) -> None:`
  - **Repository Instantiation**: Must instantiate `DatabaseRepository(DB_PATH)` directly inside the dialog function body.
  - When `"Update transaction category"` is clicked:
    - **Selection Check**: Validate that `selected_tx_id` is not `None` AND `New category` != `"Select a category"`. If either is unselected, render `st.error("Please select both a transaction and a new category before updating.")` and halt.
    - **Same Category Check**: Check if `selected_new_cat` is equal to `current_cat_name`. If equal, render `st.error("'Current category' and 'New category' must not be the same.")` and halt.
    - If all validations pass, invoke the modal dialog directly:
      - **Modal Title**: `"Confirm transaction category update"`
      - **Modal Width**: `width="small"`
      - **Modal Body Text**: `Please confirm that this transaction's category is to be updated from '<current_cat_name>' to '<selected_new_cat>'?`
      - **Action Buttons Layout (`col1, col2`)**:
        - **"Cancel"** (`use_container_width=True`): Closes modal and returns to page without changes (`st.rerun()`).
        - **"Update"** (`type="primary"`, `use_container_width=True`): Executes `update_transaction_category(int(selected_tx_id), new_cat_id)` in repository and invokes `st.rerun()`.
      - **State Leak Prevention Rule**: Do NOT store sticky boolean flags in `st.session_state` (e.g., `show_tx_dialog = True`) that persist across unrelated widget interactions. Call `@st.dialog` functions directly or reset state flags immediately upon invocation.

---

### 4.6 Section 4: Uncategorised Merchants (`Row 2, Full Width`)
- **Section Heading**: `st.subheader("Uncategorised merchants")`
- **Description Sub-text**: `st.markdown("List of merchants currently assigned to 'Uncategorised' requiring mapping.")`
- **Query Strategy**: Group transactions by `merchant_id` where `m.category_id = 1` and `t.category_id IS NULL`.
- **Table Column Renaming**:
  - Display DataFrame with renamed column headers:
    - `merchant_name` -> **`Merchant`**
    - `transaction_count` -> **`Instances`**
- **Explicit Page Size Pagination Logic**:
  - Page size configuration set to `page_size = 5` (or configurable).
  - Maintain `current_page` in `st.session_state`.
  - Slice DataFrame: `df.iloc[(page - 1) * page_size : page * page_size]`.
  - Display pagination control bar below the table with **Previous Page**, **Page X of Y**, and **Next Page** buttons.
- **Table Display**: Render full width (`use_container_width=True`, `hide_index=True`).

---

### 4.7 Streamlit Dialog Architecture & Scope Contract
- **Module-Level Declaration**: All `@st.dialog` functions MUST be declared as top-level functions outside the `PersonalExpenseTracker` class to satisfy Streamlit fragment execution rules.
- **Parameter Restrictions**: `@st.dialog` functions MUST NOT accept `self` or `DatabaseRepository` class instances as arguments.
- **Internal Database Instantiation**: Dialog functions must import `DatabaseRepository` from `src.repository` (or `repository`) and instantiate `DatabaseRepository(DB_PATH)` locally inside the function body to execute updates cleanly across reruns.

## 5. Jira Automation & Ticket Generation Rules

- **Project Key**: `PET`
- **Prefix Standard**: `[ TOUCHPOINT_1 | TOUCHPOINT_2 | ... ] Story Title` (Front-to-Back: `UI` -> `PY` -> `API` -> `DB`)
- **Epic Mapping**: All stories link to existing Epic **`PET-3`** (`Categorise Transactions`)

## 6. Story Backlog Definitions

### Story 1
**Target Epic**: `PET-3`  
**Title**: `[ PY | DB ] Database Merchant Entity Table & Parser Ingestion Refactoring`

**Description**:
AS A Personal Tracker User  
I WANT TO store canonical merchant entities in a dedicated database table and refactor the PDF parser to insert/retrieve merchant records  
SO THAT merchant categorization is managed centrally without redundant duplicate pattern parsing.

Acceptance Criteria:

Scenario 1: Merchant Table Creation  
GIVEN the database is initialized during parser startup  
WHEN database migrations execute  
THEN the `merchant` table is created with unique `merchant_name` constraints and default `category_id = 1` ('Uncategorised').

Scenario 2: Entity Resolution During Ingestion  
GIVEN a PDF statement is being parsed  
WHEN a new merchant name is encountered  
THEN it is saved to the `merchant` table and its generated `merchant_id` is linked to the ingested `transaction` record.

---

### Story 2
**Target Epic**: `PET-3`  
**Title**: `[ UI | PY | DB ] Global Merchant Category Management & Paginated List`

**Description**:
AS A Personal Tracker User  
I WANT TO view uncategorised merchants in a paginated table and update their default categories in the UI  
SO THAT all transactions for a merchant inherit the updated category globally.

Acceptance Criteria:

Scenario 1: Paginated Uncategorised Merchants Table  
GIVEN I am on the Categorise view in Streamlit  
WHEN the page loads  
THEN distinct merchants assigned to 'Uncategorised' display in a full-width table paginated at 5 records per page with working controls.

Scenario 2: Update Global Merchant Category  
GIVEN I select an uncategorised merchant and choose a target category  
WHEN I click 'Save mapping'  
THEN `category_id` updates directly on the `merchant` record, categorizing its transactions immediately.

---

### Story 3
**Target Epic**: `PET-3`  
**Title**: `[ UI | PY | DB ] Transaction-Level Category Override`

**Description**:
AS A Personal Tracker User  
I WANT TO edit and override the category of an individual transaction directly in the UI  
SO THAT I can reclassify one-off purchases without altering the global category for that merchant.

Acceptance Criteria:

Scenario 1: Individual Transaction Category Update  
GIVEN I am inspecting the transactions override control in Streamlit  
WHEN I change the category of a specific transaction row and submit the change  
THEN only that single row's `category_id` in the `transaction` table is updated while leaving the parent `merchant` default category unchanged.

---

### Story 4
**Target Epic**: `PET-3`  
**Title**: `[ UI | PY | DB ] Dynamic Custom Category Creation & Validation`

**Description**:
AS A Personal Tracker User  
I WANT TO create new, custom spending categories directly from the Categorise UI  
SO THAT I can accurately classify merchants and transactions that do not fit into the default pre-defined categories.

Acceptance Criteria:

Scenario 1: Custom Category Creation & Input Validation  
GIVEN I am on the Categorise view in Streamlit  
WHEN I enter a valid new category name (max 50 characters, letters/spaces/ampersands/hyphens/slashes only) and click 'Add category'  
THEN a modal confirmation dialog is presented asking for confirmation before inserting the new record into the `category` table.

Scenario 2: Duplicate & Special Character Guardrails  
GIVEN I attempt to add a category name that already exists (case-insensitive) or contains invalid special characters  
WHEN I click 'Add category'  
THEN an inline error message is displayed and database insertion is prevented.