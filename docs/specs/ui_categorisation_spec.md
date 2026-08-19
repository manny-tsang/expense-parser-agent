# Specification: Merchant & Transaction Categorisation UI

## 1. Objective
AS A Personal Tracker User  
I WANT TO manage merchant-to-category mapping rules in SQLite and override categories on individual transactions via the Streamlit UI  
SO THAT I can accurately categorize recurring merchants globally while retaining the flexibility to reclassify unique, one-off transactions.

## 2. Technical Stack & Dependencies
- **Language**: Python 3.x
- **UI Framework**: Streamlit (`src/app.py`), `streamlit-option-menu`
- **Core Engine & Data Processing**: `src/pdf_parser.py` (`HKStatementParser`), `pandas`, `sqlite3`
- **Database Target**: `db/personal-expense-tracker.db`
- **Database Ownership Contract**:
  - `src/pdf_parser.py` owns database schema definitions and initial migrations (`merchant_mapping` table creation).
  - `src/app.py` executes data reads and updates (`UPDATE` / `INSERT`) through `DatabaseRepository` methods without modifying table structures.
---

## 3. Data Model & Architecture

### 3.1 Database Schema Additions (`db/personal-expense-tracker.db`)

Create the `merchant_mapping` table to decouple hardcoded merchant rules from Python code into SQLite:

```sql
CREATE TABLE IF NOT EXISTS "merchant_mapping" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT,
    "pattern" TEXT UNIQUE NOT NULL,
    "category_id" INTEGER NOT NULL,
    "created_at" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY("category_id") REFERENCES "category"("id")
);
```
### 3.2 Parser Refactoring Contract (`src/pdf_parser.py`)
- **Deprecate Hardcoded Dictionaries**: Remove `CATEGORIES_MAP` from `HKStatementParser`.
- **Database-Driven Lookup**: Refactor `_categorise_merchant(cursor, merchant_name)` to query the `merchant_mapping` table using SQL `LIKE` pattern matching.
- **Seeding Migration**: Upon running `_init_db_and_check_log()`, automatically populate `merchant_mapping` with initial keyword rules if the table is empty.

## 4. UI Design Principles & Workflow Layout (`src/app.py`)

### 4.1 Navigation Expansion
Expand sidebar navigation in `render_sidebar()` to include the new view:
- **Menu Options**: `["Dashboard", "Upload", "Categorise", "Charts"]`
- **Icons**: `["house", "cloud-upload", "tag", "bar-chart"]`

### 4.2 Categorise Page Two-Row Layout Structure
The Categorise view layout MUST be organized into **two main rows**:

- **Row 1 (2 Columns)**:
  - **Column 1**: `Global merchant mapping` section.
  - **Column 2**: `Transaction-level category mapping` section.
- **Row 2 (Full Width)**:
  - `Uncategorised merchants` section listing table across full page width.

---

### 4.3 Section 1: Global Merchant Mapping (`Row 1, Column 1`)
- **Section Heading**: `st.subheader("Global merchant mapping")`
- **Description Sub-text**: `st.markdown("Select an uncategorised merchant and a category to create a mapping. Creating this will re-categorise all transactions made at the chosen merchant to the selected category.")`
- **Form Controls**:
  - Dropdown 1 Label: `"Merchant"` (Dropdown listing uncategorised merchants with default option `"-- Custom Pattern --"`).
  - Text Input Label: `"Merchant pattern / keyword"`.
  - Dropdown 2 Label: `"Category"` (Dropdown listing target categories from `category` table).
  - Action Button Label: `"Save mapping"` with `type="primary"` (styled red).
- **Execution**: Inserts pattern into `merchant_mapping` and updates matching transactions in the `transaction` table.

---

### 4.4 Section 2: Transaction-Level Category Mapping (`Row 1, Column 2`)
- **Section Heading**: `st.subheader("Transaction-level category mapping")`
- **Description Sub-text**: `st.markdown("Set the category for a specific transaction where the default category mapping may not be correct, e.g. a transaction at BP was for groceries instead of fuel as no fuel was purchased, only water. Fuel being the default category mapping.")`
- **Form Controls**:
  - Dropdown 1 Label: `"Transaction"` (Dropdown listing individual transactions with display labels).
  - Dropdown 2 Label: `"Category"` (Dropdown listing target categories from `category` table).
  - Action Button Label: `"Update transaction category"` with `type="primary"` (styled red).
- **Execution**: Updates `category_id` for the specific targeted row in `transaction` table without creating a global mapping rule.

---

### 4.5 Section 3: Uncategorised Merchants (`Row 2, Full Width`)
- **Section Heading**: `st.subheader("Uncategorised merchants")`
- **Description Sub-text**: `st.markdown("List of merchants that require mapping to one of the pre-defined categories.")`
- **Table Column Renaming**:
  - Display DataFrame with renamed column headers:
    - `merchant` -> **`Merchant`**
    - `transaction_count` -> **`Instances`**
- **Table Display**: Render full width (`use_container_width=True`, `hide_index=True`).

## 5. Jira Automation & Ticket Generation Rules

- **Project Key**: `PET`
- **Prefix Standard**: `[ TOUCHPOINT_1 | TOUCHPOINT_2 | ... ] Story Title` (Front-to-Back: `UI` -> `PY` -> `API` -> `DB`)
- **Epic Mapping**: All stories link to existing Epic **`PET-3`** (`Categorise Transactions`).

## 6. Story Backlog Definitions

### Story 1
**Target Epic**: `PET-3`  
**Title**: `[ PY | DB ] Database Merchant Mapping Table & Parser Refactoring`

**Description**:
AS A Personal Tracker User  
I WANT TO store merchant-to-category keyword rules in a database table and refactor the PDF parser to use SQLite lookups  
SO THAT new merchant categories can be managed dynamically without modifying hardcoded Python code.

Acceptance Criteria:

Scenario 1: Database Table Creation and Seeding  
GIVEN the database is initialized during parser startup  
WHEN `_init_db_and_check_log()` runs  
THEN the `merchant_mapping` table is created and populated with initial default rules if empty.

Scenario 2: Database-Driven Parser Categorisation  
GIVEN a PDF statement is being parsed  
WHEN `_categorise_merchant()` evaluates a parsed merchant name  
THEN it queries `merchant_mapping` in SQLite to assign the matching `category_id` (or defaults to `Uncategorised`).

---

### Story 2
**Target Epic**: `PET-3`  
**Title**: `[ UI | PY | DB ] Global Merchant Rule Management & Bulk Propagation`

**Description**:
AS A Personal Tracker User  
I WANT TO view uncategorised merchants and create global category mapping rules in the UI  
SO THAT all current and future transactions for a merchant are automatically categorized in bulk.

Acceptance Criteria:

Scenario 1: View Uncategorised Merchants  
GIVEN I am on the Categorise view in Streamlit  
WHEN the page loads  
THEN a list of distinct merchants assigned to 'Uncategorised' displays with their total transaction counts.

Scenario 2: Save and Propagate Global Rule  
GIVEN I select an uncategorised merchant and choose a target category  
WHEN I click 'Save & Apply Rule'  
THEN a new pattern entry is saved to `merchant_mapping`, and all matching existing transactions in the database update to the selected category immediately.

---

### Story 3
**Target Epic**: `PET-3`  
**Title**: `[ UI | PY | DB ] Transaction-Level Category Override`

**Description**:
AS A Personal Tracker User  
I WANT TO edit and override the category of an individual transaction directly in the UI  
SO THAT I can reclassify one-off purchases without altering the global category rule for that merchant.

Acceptance Criteria:

Scenario 1: Individual Transaction Category Update  
GIVEN I am inspecting the transactions list in Streamlit  
WHEN I change the category of a specific transaction row and submit the change  
THEN only that single row's `category_id` is updated in the database while leaving global merchant mappings unchanged.