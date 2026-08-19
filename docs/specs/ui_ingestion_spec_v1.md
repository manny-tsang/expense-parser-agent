# Specification: Statement Ingestion & Operational Dashboard UI

## 1. Objective
Build a functional, intuitive, and responsive Streamlit web application (`src/app.py`) that serves as a local operational interface. The interface allows users to select/upload downloadable PDF credit card statements, execute the parser and auto-categorisation engine (`src/pdf_parser.py`), ingest transactions into SQLite (`db/personal-expense-tracker.db`), and inspect transaction grids and aggregate spending metrics.

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

## 3. UI Design Principles & Responsive Layout

### 3.1 Responsiveness & Page Titles
- **Page Configuration**: Set `st.set_page_config(page_title="Transaction History", page_icon="💳", layout="wide")`.
- **Main Header**: `st.title("Transaction History")`.
- **Page Subtitle**: `st.markdown("Amalgamation of credit card transactions uploaded successfully, with the ability to filter and search on available transactions.")`.
- **Mobile & Desktop Compatibility**: Components must degrade gracefully and stack vertically on mobile device screens.

### 3.2 Sidebar / Control Panel
- **Sidebar Title**: `st.sidebar.title("Upload Statement")`.
- **File Selection**: `st.file_uploader` accepting `.pdf` files.
- **Ingestion Trigger**: A prominent "Process Statement" action button (`st.button`).
- **Processing Status & Toast**: Display a visual spinner during processing (`st.spinner`). Upon successful ingestion, display the exact success message: `"Statement processed successfully!"` via toast and sidebar alert.

### 3.3 Main Data Area, Sticky Containers & Collapsible Layout
1. **Sticky Top Header Container**:
   - Wrap `st.title("Transaction History")`, `st.markdown(...)`, and Summary Metrics Cards inside a sticky container or fixed top-level layout block so title and key totals remain visible while scrolling down the transaction table.

2. **Collapsible Filtering Toolbar**:
   - Wrap all filtering controls (Category Selector and Merchant Search) inside a collapsible expander component: `st.expander("Filters & Search", expanded=False)`.
   - Category Filter: Dropdown selector (`st.selectbox`) populated dynamically from the `category` table (`SELECT category_name FROM category ORDER BY category_name`).
   - Search Bar: Text input (`st.text_input`) filtering the `merchant` column using SQL `LIKE`.

3. **Schema & Query Strategy**:
   - `src/app.py` queries transactions by joining normalized relational tables created by `src/pdf_parser.py`:
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
     ```

4. **Summary Metrics Cards (`st.metric`)**:
   - Total Spend (Formatted in AUD currency: `$X,XXX.XX`).
   - Total Transaction Count.
   - Top Spending Category.

5. **Real-Time Transaction Grid (`st.dataframe`)**:
   - Displays parsed transactions queried directly from `personal-expense-tracker.db`.
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
**Title**: `[ UI | PY | DB ] PDF Statement Selector & Batch Ingestion`

**Description**:
AS A Personal Tracker User  
I WANT A local, responsive web interface to select downloadable PDF credit card statements and trigger parsing  
SO THAT I can ingest transaction records into my SQLite database without running terminal commands.  

Acceptance Criteria:

Scenario 1: Successful PDF Selection and Processing  
GIVEN the Streamlit dashboard is running locally  
WHEN I select a valid PDF credit card statement and click "Process Statement"  
THEN `parse_statement()` executes, transaction records are stored in `personal-expense-tracker.db`, and `"Statement processed successfully!"` is displayed.  

Scenario 2: Invalid File Error Handling  
GIVEN the Streamlit dashboard is open  
WHEN I attempt to process an invalid or corrupted file  
THEN the application halts processing gracefully and displays a clear error message on the UI.  

---

### Story 2
**Target Epic**: `PET-4` (`Tabular UI`)  
**Title**: `[ UI | PY | DB ] Real-Time Ingestion Preview & Transaction Grid`

**Description**:
AS A Personal Tracker User  
I WANT TO view summary metrics and an interactive transaction grid immediately following statement ingestion  
SO THAT I can instantly verify categorisation accuracy and spending totals on desktop or mobile.  

Acceptance Criteria:

Scenario 1: Real-Time Grid and Metric Refresh  
GIVEN a PDF statement has just been processed and ingested  
WHEN the ingestion completes  
THEN the dashboard automatically updates to display Total Spend, Transaction Count, Top Category, and populates the transaction table from SQLite.  

Scenario 2: Category Filtering  
GIVEN parsed transactions are displayed in the data grid  
WHEN I select a specific category from the dropdown filter inside the collapsed filters view  
THEN the table dynamically updates to show only transactions matching that category.