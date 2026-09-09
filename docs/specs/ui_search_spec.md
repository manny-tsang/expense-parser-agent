# Specification: Transaction Search & Remediation Workbench UI

## 1. Objective
AS A Personal Tracker User  
I WANT TO search and filter historical transactions in a results table and remediate line-item details in an action card directly below the table  
SO THAT I can audit spending anomalies, resolve foreign currency inaccuracies, and adjust line-item categories in a natural, top-to-bottom accessible workflow.

## 2. Technical Stack & Dependencies
- **Language**: Python 3.x
- **UI Framework**: Streamlit (`src/app.py`), `streamlit-option-menu`
- **Data Engine & Repository**: `src/repository.py` (`DatabaseRepository`)
- **Database Target**: `db/personal-expense-tracker.db`

---

## 3. UI Design & Layout Architecture (`src/app.py`)

### 3.1 Sidebar Navigation Standard
- Navigation menu options: `["Dashboard", "Upload", "Categorise", "Charts", "Search"]`
- Icons: `["house", "cloud-upload", "tag", "bar-chart", "search"]`

### 3.2 Three-Row Accessible Sequential Layout

#### Row 1: Search & Filter Card (`st.container(border=True)`)
- `st.subheader("Filter Transactions")`
- **Input Controls (`st.columns(3)`)**:
  - **Merchant Search**: `st.text_input("Merchant name", key="search_merchant_input")` (Supports partial or full merchant name matching).
  - **Transaction Amount**: `st.number_input("Transaction amount", value=None, step=10.0, key="search_amount_input")` (Filters for specific transaction amount matching).
  - **Transaction Date**: `st.date_input("Transaction date", value=None, key="search_date_input")` (Filters by specific transaction date).

#### Row 2: Search Results Table (Full Width)
- Full-width DataFrame displaying filtered transaction hits sliced at 10 rows per page with Previous/Next page controls.
- Columns: `Transaction date`, `Merchant name`, `Category`, `Transaction amount`, `HKD amount`, `FX rate`.
- **Empty State**: Displays clear info message (`st.info("No matching records were found.")`) when no transactions match the active criteria.

#### Row 3: Transaction Remediation Card (`st.container(border=True)`)
- `st.subheader("Edit Selected Transaction")`
- `st.markdown("Select a transaction from the search results above to remediate its category, amounts, or exchange rate.")`
- Selectbox: `st.selectbox("Select Transaction", options=matching_tx_ids, format_func=..., key="search_edit_tx_select")`
- Readout: Read-only summary showing raw merchant description, date, and original currency.
- Form Inputs (`st.columns(3)`):
  - `st.selectbox("Category", options=category_list, key="search_edit_cat_select")`
  - `st.text_input("Transaction amount ($AUD)", key="search_edit_aud")`
  - `st.text_input("FX rate", key="search_edit_fx")`
- Field Validation Rules:
  - Empty fields strictly block updates and display inline error message: `"Update cannot be performed with empty values."`
  - Category field input MUST contain ONLY letters, spaces, ampersands (&), hyphens (-), or slashes (/). Otherwise display: `"Input must contain ONLY letters, spaces, ampersands (&), hyphens (-), or slashes (/)."`.
  - Transaction amount ($AUD) and FX rate inputs MUST contain ONLY numbers and periods (.). Otherwise display: `"Input must contain ONLY numbers and periods ( . )"`.
  - Disable the **Update transaction** action button whenever validation rules are violated.
- Action Button: `st.button("Update transaction", type="primary")` triggering `@st.dialog("Confirm transaction update")`.

### 3.3 Dialog Confirmation Modal (`@st.dialog`)
- Title: `"Confirm transaction update"`
- Description: Displays a concise summary asking to confirm updating the transaction with the values entered.
- Buttons:
  - **Cancel**: Closes the modal dialog and returns the user to the "Search" screen without applying changes.
  - **Update**: Executes `DatabaseRepository.update_transaction_details()`, persists updates in SQLite, and refreshes the view.

---

## 4. Jira Automation & Story Backlog Definitions

- **Project Key**: `PET`
- **Prefix Standard**: `[ TOUCHPOINT_1 | TOUCHPOINT_2 | ... ] Story Title` (Front-to-Back: `UI` -> `PY` -> `API` -> `DB`)
- **Initial Story Transition**: `Defining` (Keyword: `design`)

### 4.1 Epic Mapping Summary
- **Target Epic**: `Search UI`

---

## 5. Story Backlog Definitions

### Story 1
**Jira ID**: `PET-22`  
**Target Epic**: `Search UI`  
**Title**: `[ UI | PY | DB ] Transaction search`

**Description**:
AS A Personal Tracker User  
I WANT TO search for transactions that have been successfully imported  
SO THAT I can dig into the details of individual transactions easily

Acceptance Criteria:  

Scenario Outline 1: Search criteria
GIVEN transactions have been successfully imported
WHEN I enter the “Search” function
THEN I am able to search based on <criteria>

Examples:
| criteria |
| partial or full merchant name |
| transaction amount |
| transaction date |

Scenario 2: Result output
GIVEN I have entered search criteria
WHEN there are transactions that match the search criteria
THEN DatabaseRepository.search_transactions() returns matching records displayed in a 10-row paginated table with the columns of “Transaction date”
AND “Merchant name”
AND “Category”
AND “Transaction amount”
AND “HKD amount”
AND “FX rate”

Scenario 3: No result output
GIVEN I have entered search criteria
WHEN there are no transactions that match the search criteria
THEN the table displays a clear info message indicating no matching records were found.

---

### Story 2
**Jira ID**: `PET-23`  
**Target Epic**: `Search UI`  
**Title**: `[ UI | PY | DB ] Update individual transaction details`

**Description**:
AS A Personal Tracker User  
I WANT TO select a transaction from the search results  
SO THAT I can modify its category, transaction amount, or FX rate to ensure they represent expenses in AUD to better aid budget planning.

Acceptance Criteria:

Scenario Outline 1: Update selected transaction's transaction amount and FX rate  
GIVEN transactions are returned based on the provided search criteria  
WHEN I select a transaction  
THEN that transaction is populated into the "Update transaction" card with the ability to update the <field>

Examples:
| field |
| Category |
| Transaction amount ($AUD) |
| FX rate |

Scenario Outline 2: Input Field & Non-Empty Validation  
GIVEN I have selected a transaction to amend
WHEN I enter <condition> into <field> field
THEN an in-line message states <message>
AND disables the "Update transaction" button until valid, non-empty positive numeric values are provided.

Examples:
| conditon | field | outcome |
| no characters | any | “Update cannot be performed with empty values.” |
| invalid characters | Category | “Input must contain ONLY letters, spaces, ampersands (&), hyphens (-), or slashes (/).” |
| non-numeric characters | Transaction amount ($AUD) | “Input must contain ONLY numbers and periods ( . )” |
| non-numeric characters | FX rate | “Input must contain ONLY numbers and periods ( . )” |

Scenario 3: Present confirmation modal dialog  
GIVEN I have entered a valid values to update the transaction with
WHEN I click "Update transaction"  
THEN the confirmation modal dialog is presented asking me to confirm that I wish to update the transaction with the values entered
AND provides an "Update" button which confirms the change and executes DatabaseRepository.update_transaction_details()  
AND provides a "Cancel" button which returns me to the "Search" screen without applying changes.