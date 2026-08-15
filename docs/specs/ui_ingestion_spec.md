# Specification: Statement Ingestion & Operational Dashboard UI

## 1. Objective
Build a modular, multi-page ready Streamlit web application (`src/app.py`) featuring single-word physical button navigation ("Dashboard", "Upload", "Charts") in the sidebar. The primary view focuses on **Upload**, allowing users to select/upload downloadable PDF credit card statements on the main page, trigger the core parser (`src/pdf_parser.py`), ingest transactions into SQLite (`db/personal-expense-tracker.db`), inspect aggregate metrics (total transactions & uploaded statement date range derived from `statement_log`), and view a full raw transaction grid.

## 2. Technical Stack & Dependencies
- **Language**: Python 3.x
- **UI Framework**: Streamlit (`streamlit`)
- **Data & Processing**: `pandas`, `sqlite3`, `re`, `os`
- **Core Engine**: `src/pdf_parser.py` (`parse_statement()`)
- **Database Target**: `db/personal-expense-tracker.db`
- **Database Ownership Contract**: 
  - `src/app.py` MUST NOT execute `CREATE TABLE` queries or manage database schemas.
  - Database table creation and normalized schema management are exclusively owned by `src/pdf_parser.py`.

---

## 3. UI Design Principles & Navigation Structure

### 3.1 Sidebar Navigation
- **Sidebar Role**: Render single-word physical action buttons (`st.sidebar.button`) to toggle active page state (`st.session_state`).
- **Navigation Options**:
  1. `Dashboard` (Placeholder view for future category averages & statement overviews)
  2. `Upload` (Active target view for main-page statement selection, summary metrics, and raw grid)
  3. `Charts` (Placeholder view for future real-time interactive charting and filtering)

### 3.2 Upload View Screen Layout & Summary Metrics
- **Page Title**: `st.title("Upload")`
- **Subtitle**: `st.markdown("Select PDF credit card statement to process into anonymised transactions to be stored and used for budget planning.")`
- **Main Page Ingestion Section**:
  - File uploader widget: `st.file_uploader("Select PDF Statement", type=["pdf"])`
  - Processing button: `st.button("Process Statement", type="primary")`
  - Status Feedback: Visual spinner (`st.spinner`) during processing. If duplicate or invalid, display clear error alert. Upon successful ingestion, display: `"Statement processed successfully!"`.

- **Upload Summary Cards (`st.metric`)**:
  - Card 1: **Total Transactions Uploaded** (`SELECT COUNT(*) FROM "transaction"`).
  - Card 2: **Statements Uploaded Date Range** (Queries `SELECT filename FROM statement_log`; parses filenames formatted `YYYY-MM-DD_Statement.pdf` to find minimum and maximum dates and formats as `"From Month YYYY to Month YYYY"`, e.g., `"From January 2026 to July 2026"`). If `statement_log` is empty, displays `"No statements uploaded"`.

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
   - Displays all ingested transactions in a scrollable/paginated table (`st.dataframe(..., height=500)`).
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
**Title**: `[ UI | PY | DB ] Main-Page PDF Statement Selector & Duplicate Log Prevention`

**Description**:
AS A Personal Tracker User  
I WANT TO upload statements on the main Upload screen and prevent duplicate file processing  
SO THAT my transaction data remains accurate and free from duplicated records.  

Acceptance Criteria:

Scenario 1: Main-Page PDF Ingestion & Log Tracking  
GIVEN the Streamlit app is on the "Upload" screen  
WHEN I upload a new valid PDF statement and click "Process Statement"  
THEN `parse_statement()` executes, the filename is logged to `statement_log`, and `"Statement processed successfully!"` is displayed.  

Scenario 2: Duplicate Statement Prevention  
GIVEN a statement file has already been processed previously  
WHEN I attempt to upload the same statement filename again  
THEN processing halts early and displays an error indicating the statement has already been ingested.  

---

### Story 2
**Target Epic**: `PET-4` (`Tabular UI`)  
**Title**: `[ UI | PY | DB ] Upload Summary Metrics & Raw Transaction Grid`

**Description**:
AS A Personal Tracker User  
I WANT TO view overall transaction counts, statement date ranges, and a raw transaction grid on the Upload screen  
SO THAT I can immediately verify statement ingestion totals and historical date ranges.  

Acceptance Criteria:

Scenario 1: Real-Time Summary & Grid Refresh  
GIVEN a PDF statement has been ingested  
WHEN the Upload screen loads  
THEN the Total Transactions metric, Statement Date Range metric (queried directly from `statement_log`), and raw transaction grid populate dynamically from SQLite.