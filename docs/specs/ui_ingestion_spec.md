# Specification: Statement Ingestion & Operational Dashboard UI

## 1. Objective
Build a modular, multi-page ready Streamlit web application (`src/app.py`) featuring single-word sidebar navigation ("Dashboard", "Upload", "Charts"). The initial implementation focuses on the **Upload** view, allowing users to select/upload downloadable PDF credit card statements directly on the main page, trigger the core parser (`src/pdf_parser.py`), ingest transactions into SQLite (`db/personal-expense-tracker.db`), and inspect a full raw transaction preview grid.

## 2. Technical Stack & Dependencies
- **Language**: Python 3.x
- **UI Framework**: Streamlit (`streamlit`)
- **Data & Processing**: `pandas`, `sqlite3`
- **Core Engine**: `src/pdf_parser.py` (`parse_statement()`)
- **Database Target**: `db/personal-expense-tracker.db`
- **Database Ownership Contract**: 
  - `src/app.py` MUST NOT execute `CREATE TABLE` queries or manage database schemas.
  - Database table creation and normalized schema management are exclusively owned by `src/pdf_parser.py`.

---

## 3. UI Design Principles & Navigation Structure

### 3.1 Sidebar Navigation
- **Sidebar Role**: Dedicated exclusively to application navigation (`st.sidebar.radio` or `st.navigation`).
- **Navigation Options**:
  1. `Dashboard` (Placeholder view for future category averages & statement overviews)
  2. `Upload` (Active target view for statement selection, batch ingestion, and raw grid)
  3. `Charts` (Placeholder view for future real-time interactive charting and filtering)

### 3.2 Upload View Screen Layout
- **Page Title**: `st.title("Upload")`
- **Subtitle**: `st.markdown("Select PDF credit card statement to process into anonymised transactions to be stored and used for budget planning.")`
- **Main Page Ingestion Section**:
  - File uploader widget: `st.file_uploader("Select PDF Statement", type=["pdf"])`
  - Processing button: `st.button("Process Statement", type="primary")`
  - Status Feedback: Visual spinner (`st.spinner`) during processing and toast/alert notification upon completion (`"Statement processed successfully!"`).

### 3.3 Main Data Area (Raw Transaction Preview)
1. **Schema & Query Strategy**:
   - `src/app.py` queries raw transactions directly from the normalized schema:
     ```sql
     SELECT 
         t.trans_date, 
         t.merchant, 
         c.category_name, 
         t.txn_amount, 
         curr.currency_code AS purchase_currency, 
         t.hkd_amount, 
         t.fx_rate
     FROM "transaction" t
     LEFT JOIN category c ON t.category_id = c.id
     LEFT JOIN currency curr ON t.purchase_currency_id = curr.id
     ORDER BY t.trans_date DESC, t.id DESC
     ```
2. **Raw Transaction Grid (`st.dataframe`)**:
   - Displays all ingested transactions in a paginated/scrollable table.
   - Filtering and search controls are explicitly removed from this view (reserved for the `Charts` view).
   - Columns: `trans_date`, `merchant`, `category_name`, `txn_amount`, `purchase_currency`, `hkd_amount`, `fx_rate`.

---

## 4. Jira Automation & Ticket Generation Rules

- **Project Key**: `PET`
- **Prefix Standard**: `[ TOUCHPOINT_1 | TOUCHPOINT_2 | ... ] Story Title` (Front-to-Back: `UI` -> `PY` -> `API` -> `DB`)
- **Initial Story Transition**: `Defining` (Keyword: `design`)

### 4.1 Epic Mapping Summary
- **New Epic**: `Statement Ingestion UI` (Initial Status: `Implementing`, Keyword: `implementing`)
- **Existing Epic**: `PET-4` (`Tabular UI`)

---

## 5. Story Backlog Definitions

### Story 1
**Target Epic**: `Statement Ingestion UI` (New Epic)  
**Title**: `[ UI | PY | DB ] Main-Page PDF Statement Selector & Batch Ingestion`

**Description**:
AS A Personal Tracker User  
I WANT TO select downloadable PDF credit card statements directly on the Upload screen  
SO THAT I can ingest transaction records into my SQLite database without using sidebar form inputs.  

Acceptance Criteria:

Scenario 1: Main-Page PDF Ingestion  
GIVEN the Streamlit app is on the "Upload" screen  
WHEN I upload a valid PDF statement and click "Process Statement"  
THEN `parse_statement()` executes, records populate `personal-expense-tracker.db`, and `"Statement processed successfully!"` is displayed.  

Scenario 2: Invalid File Error Handling  
GIVEN the Streamlit app is on the "Upload" screen  
WHEN I attempt to process an invalid file  
THEN the application halts processing gracefully and displays a clear error message.  

---

### Story 2
**Target Epic**: `PET-4` (`Tabular UI`)  
**Title**: `[ UI | PY | DB ] Real-Time Ingestion Preview & Raw Transaction Grid`

**Description**:
AS A Personal Tracker User  
I WANT TO view a raw transaction data grid on the Upload screen immediately following statement processing  
SO THAT I can verify that all transactions were cleanly extracted and stored in SQLite.  

Acceptance Criteria:

Scenario 1: Real-Time Raw Grid Refresh  
GIVEN a PDF statement has just been processed  
WHEN the ingestion completes  
THEN the Upload screen automatically updates to display all historical transactions from SQLite in a raw data grid.