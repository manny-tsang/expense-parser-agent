# Specification: Transaction Search & Remediation Workbench UI

## 1. Objective
AS A Personal Tracker User  
I WANT TO search historical transactions, select a record directly from the results table, and review/remediate its details in a split action card below  
SO THAT I can audit spending anomalies, resolve foreign currency inaccuracies, and adjust line-item categories in a seamless, top-to-bottom master-detail workflow.

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

### 3.2 Page Header & Descriptor Text
- **Header Title**: `Search`
- **Page Descriptor Text**: `st.markdown("Search historical transactions across merchant, amount, or date, and select any record from the results table to view its full details and perform category or FX rate overrides.")`

### 3.3 Three-Row Master-Detail Layout

#### Row 1: Search Criteria Card (`st.container(border=True)`)
- `st.subheader("Search criteria")`
- **Input Controls (`st.columns(3)`)**:
  - **Merchant Search**: `st.text_input("Merchant name", key="search_merchant_input")` (Supports partial or full merchant name matching).
  - **Transaction Amount**: `st.number_input("Transaction amount", value=None, step=10.0, key="search_amount_input")` (Filters for specific transaction amount matching).
  - **Transaction Date**: `st.date_input("Transaction date", value=None, key="search_date_input")` (Filters by specific transaction date).

#### Row 2: Search Results Table (Full Width, 5 Rows Per Page)
- Full-width DataFrame displaying filtered transaction hits sliced at **5 rows per page** with Previous/Next page controls.
- Columns: `Transaction date`, `Merchant name`, `Category`, `Transaction amount`, `HKD amount`, `FX rate`.
- **Missing Value Representation**: Null or missing values (e.g. FX rate for DCC fees) MUST be consistently rendered as `"None"` across all table cells and detail fields (never `NaN` or `NoneType`).
- **Row Selection Event (`on_select="rerun"`, `selection_mode="single-row"`)**:
  - Clicking any row in the table automatically selects that record and populates Row 3 with its full details.
  - By default (or on search query rerun), Row 0 of the active page is auto-selected.
- **Empty State**: Displays clear info message (`st.info("No matching records were found.")`) when no transactions match the active criteria.

#### Row 3: Edit Transaction Card (`st.container(border=True)`)
- `st.subheader("Edit transaction")`
- **Split Bordered Columns (`st.columns(2)`)**:
  - Both sub-columns MUST be wrapped in `st.container(border=True)` to create distinct, bordered card containers.

  - **Column 1 Container (`st.container(border=True)`) - Transaction details**:
    - Section Heading: `st.subheader("Transaction details")`
    - Read-only disabled text displays showing selected line-item properties:
      - `Transaction date`: Read-only value from selected row.
      - `Merchant`: Read-only value from selected row.
      - `Transaction amount`: Read-only value formatted in AUD.
      - `HKD amount`: Read-only value formatted in HKD (or `"None"` if null).
      - `FX rate`: Read-only FX rate value (or `"None"` if null, strictly avoiding `NaN`).

  - **Column 2 Container (`st.container(border=True)`) - Update transaction**:
    - Section Heading: `st.subheader("Update transaction")`
    - **Category Dropdown**: `st.selectbox("Category", options=["Select a new category"] + category_list, key="search_edit_cat_select")`
    - **Transaction Amount Input**: `st.text_input("Transaction amount ($AUD)", placeholder="Enter $AUD amount", key="search_edit_aud")`
    - **FX Rate Input**: `st.text_input("FX rate", placeholder="Enter exchange rate", key="search_edit_fx")`
    
    - **Button Enablement Matrix & Validation Rules**:
      - The **Update transaction** button (`type="primary"`) MUST remain **disabled** by default until one of these valid update states is achieved:
        1. **Category Only**: `Category` != `"Select a new category"` AND (`Amount` is empty AND `FX rate` is empty).
        2. **Amount + FX Pair Only**: `Category` == `"Select a new category"` AND (`Amount` is valid non-empty numeric AND `FX rate` is valid non-empty numeric).
        3. **Category + Amount + FX Pair**: `Category` != `"Select a new category"` AND (`Amount` is valid non-empty numeric AND `FX rate` is valid non-empty numeric).
      
      - **In-Line Validation Warnings (`st.error`)**:
        - If only one of `Transaction amount ($AUD)` or `FX rate` is entered (partial pair): Display `st.error("Transaction amount ($AUD) and FX rate must be updated together.")`.
        - If Category input contains invalid characters: Display `st.error("Input must contain ONLY letters, spaces, ampersands (&), hyphens (-), or slashes (/).")`.
        - If Amount or FX rate contain non-numeric characters: Display `st.error("Input must contain ONLY numbers and periods ( . )")`.

### 3.4 Dialog Confirmation Modal (`@st.dialog`)
- Title: `"Confirm transaction update"`
- Description: Displays a concise summary asking to confirm updating the selected transaction with the new category, $AUD amount, or FX rate entered.
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
THEN DatabaseRepository.search_transactions() returns matching records displayed in a 5-row paginated table with the columns of “Transaction date”
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
I WANT TO select a transaction directly from the search results table  
SO THAT I can view its full details and modify its category, transaction amount, or FX rate to ensure they represent expenses in AUD to better aid budget planning.

Acceptance Criteria:

Scenario Outline 1: Master-detail row selection and update
GIVEN transactions are returned in the search results table  
WHEN I click a row in the table  
THEN its uneditable details populate in the "Transaction details" bordered container AND its editable fields populate in the "Update transaction" bordered container for <field>

Examples:
| field |
| Category |
| Transaction amount ($AUD) |
| FX rate |

Scenario Outline 2: Input Field & Pair Validation  
GIVEN I am updating a transaction record  
WHEN I enter <condition> into <field> field  
THEN an in-line message states <message>  
AND disables the "Update transaction" button until valid inputs are provided.

Examples:
| conditon | field | outcome |
| partial pair entry | Transaction amount ($AUD) OR FX rate | “Transaction amount ($AUD) and FX rate must be updated together.” |
| invalid characters | Category | “Input must contain ONLY letters, spaces, ampersands (&), hyphens (-), or slashes (/).” |
| non-numeric characters | Transaction amount ($AUD) | “Input must contain ONLY numbers and periods ( . )” |
| non-numeric characters | FX rate | “Input must contain ONLY numbers and periods ( . )” |

Scenario 3: Present confirmation modal dialog  
GIVEN I have entered a valid update values  
WHEN I click "Update transaction"  
THEN the confirmation modal dialog is presented asking me to confirm that I wish to update the transaction  
AND provides an "Update" button which confirms the change and executes DatabaseRepository.update_transaction_details()  
AND provides a "Cancel" button which returns me to the "Search" screen without applying changes.