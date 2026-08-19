# Specification: Statement Ingestion & Operational Dashboard UI

## 1. Objective
Build a modular, multi-page ready Streamlit web application (`src/app.py`) managed by the primary application class `PersonalExpenseTracker`[cite: 7, 8]. It features styled sidebar navigation using `streamlit-option-menu`[cite: 7, 8]. The primary views focus on **Upload** and **Categorise**, featuring a high-density layout with aligned top margins, uniform 215px-height 3-column bordered cards with scaled typography, followed by an explicitly paginated 10-row transaction table[cite: 7, 8].

## 2. Technical Stack & Dependencies
- **Language**: Python 3.x[cite: 7, 8]
- **UI Framework**: Streamlit (`streamlit`), `streamlit-option-menu`[cite: 7, 8]
- **Data & Processing**: `pandas`, `sqlite3`, `re`, `os`, `math`[cite: 7, 8]
- **Core Engine**: `src/pdf_parser.py` (`parse_statement()`)[cite: 7, 8]
- **Database Target**: `db/personal-expense-tracker.db`[cite: 7, 8]
- **Database Ownership Contract**: 
  - `src/app.py` MUST NOT execute `CREATE TABLE` queries or manage database schemas[cite: 7, 8].
  - Database table creation and normalized schema management are exclusively owned by `src/pdf_parser.py`[cite: 7, 8].

---

## 3. UI Design Principles & Responsive Layout

### 3.1 Main Application Structure & Naming
- **Application Class**: The primary Streamlit application class inside `src/app.py` MUST be named `PersonalExpenseTracker`[cite: 7, 8].

### 3.2 Sticky Header & Flex Height Equalization (CSS Injection)
Inject strict CSS via `inject_css(page_title)` to maintain top margin offset, solid sticky header alignment, active page title display, and equal card border stretching[cite: 7, 8]:

- **Sidebar Flush Alignment**:
  - Hide Streamlit's native sidebar header and toggle container using `[data-testid="stSidebarHeader"] { display: none !important; }`[cite: 7, 8].
  - Set `section[data-testid="stSidebar"] > div:first-child` padding to `0.5rem !important` and `[data-testid="stSidebarContent"]` top padding to `0rem !important`[cite: 7, 8].

- **Solid Left-Aligned Sticky Header & Title Injection**:
  - Target `[data-testid="stHeader"]` with `background-color: #0e1117 !important; z-index: 999 !important;`.
  - Render the active page title (e.g., "Dashboard", "Upload", "Categorise", "Charts") inside the fixed top sticky header bar using `.sticky-page-title`:
    ```css
    .sticky-page-title {
        position: fixed;
        top: 0.85rem;
        left: 14.5rem;
        z-index: 1000 !important;
        pointer-events: none;
        font-size: 1.25rem;
        font-weight: 600;
        color: #FFFFFF;
    }
    ```

- **Main Content Padding**:
  - `.block-container { padding-top: 4rem !important; padding-bottom: 1rem !important; padding-left: 2rem !important; padding-right: 2rem !important; }`[cite: 7, 8]

- **Equal Card Dimensions & Border Wrapper Lock**:
  - Target `div[data-testid="stVerticalBlockBorderWrapper"] > div` and set `min-height: 215px !important;` alongside `flex: 1 !important;` so Cards 2 and 3 expand to match Card 1 exactly[cite: 7, 8].

- **Content Typography & Card Sizing**:
  - `.metric-large`: `font-size: 8.8rem !important; font-weight: bold !important; line-height: 1.1 !important; color: #FFFFFF !important; margin-top: 0.5rem !important;`[cite: 7, 8]
  - `.period-val`: `font-size: 2rem !important; font-weight: 600 !important; color: #FFFFFF !important; margin-bottom: 0.25rem !important;`[cite: 7, 8]
  - `.period-label`: `font-size: 0.85rem !important; color: #808495 !important; margin-top: 0.25rem !important;`[cite: 7, 8]

### 3.3 Sidebar Navigation
- **No Sidebar Title**: Do not render `st.sidebar.title()` or heading labels in the sidebar[cite: 7, 8].
- **Option Menu Control**: Render `option_menu` inside the sidebar (`streamlit_option_menu.option_menu`) flush with top padding[cite: 7, 8]:
  - Menu Items: `["Dashboard", "Upload", "Categorise", "Charts"]`[cite: 7, 8]
  - Icons: `["house", "cloud-upload", "tag", "bar-chart"]`[cite: 7, 8]
  - Default Index: `1` (Upload)[cite: 7, 8]
  - Custom Styles:
    - Sidebar background: transparent / inherited sidebar background color[cite: 7, 8].
    - Text color: `#FFFFFF` (white)[cite: 7, 8].
    - Selected background highlight & icons: `#31333F` / matching transaction table header grey[cite: 7, 8].

### 3.4 Upload View Screen Layout & Equal 3-Column Card Row
- **Header Title**: Active page title rendered inside sticky top header via `inject_css(selected)`[cite: 7, 8].
- **Subtitle**: `st.markdown("Upload a PDF statement to process into anonymised transactions to be stored and used for budget planning.")`[cite: 7, 8]

- **3-Column Flex Card Row (`st.columns(3)`)**:
  - Columns wrapped in `st.container(border=True)` flex-stretch dynamically with top-aligned headers[cite: 7, 8]:
    - **Card 1 (File Picker)**:
      - Helper label: `"Upload a PDF statement"`[cite: 7, 8].
      - Widgets: `st.file_uploader` (PDFs only, `label_visibility="collapsed"`) and `st.button("Process Statement", type="primary", use_container_width=True)`[cite: 7, 8].
    - **Card 2 (Total Transactions Uploaded)**:
      - Content inside `<div class="metric-card-container">`:
        - Top-aligned Label: `"Total transactions uploaded"`[cite: 7, 8]
        - Count display: `<div class="metric-large">{total_txns}</div>` (8.8rem font size)[cite: 7, 8].
    - **Card 3 (Statement Period Uploaded)**:
      - Content inside `<div class="metric-card-container">`:
        - Label: `"Statement period uploaded"`[cite: 7, 8]
        - Date values rendered on separate lines:
          - "From:" label (`.period-label`), followed by minimum date (`Month YYYY`, e.g., `June 2026`) formatted with `.period-val` (2rem font size)[cite: 7, 8].
          - "To:" label (`.period-label`), followed by maximum date (`Month YYYY`, e.g., `July 2026`) formatted with `.period-val` (2rem font size)[cite: 7, 8].
- **Status Feedback**: Visual spinner (`st.spinner`) during processing[cite: 7, 8]. If duplicate or invalid, display clear error alert[cite: 7, 8]. Upon successful ingestion, display: `"Statement processed successfully!"`[cite: 7, 8].

### 3.5 Main Data Area (Paginated 10-Row Transaction Table)
1. **Grid Section Header**: `st.subheader("Transactions uploaded")`[cite: 7, 8]
2. **Database Repository Method Contract**:
   - `DatabaseRepository.get_transactions_dataframe(self)` queries raw transactions and returns a Pandas DataFrame[cite: 7, 8].
3. **Query Strategy**:
   - Queries transactions directly from the normalized schema[cite: 7, 8]:
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
4. **Explicit 10-Row Pagination Logic**:
   - Implement explicit page controls for the DataFrame in `app.py`[cite: 7, 8]:
     - Calculate total pages: `math.ceil(total_rows / 10)`[cite: 7, 8].
     - Maintain `current_page` in `st.session_state`[cite: 7, 8].
     - Slice DataFrame: `df.iloc[(page - 1) * 10 : page * 10]`[cite: 7, 8].
     - Display pagination control bar below the table with **Previous Page**, **Page X of Y**, and **Next Page** buttons[cite: 7, 8].
5. **Dataframe Columns**: `trans_date`, `merchant`, `category_name`, `txn_amount`, `purchase_currency`, `hkd_amount`, `fx_rate`[cite: 7, 8].

---

## 4. Jira Automation & Ticket Generation Rules

- **Project Key**: `PET`[cite: 7, 8]
- **Prefix Standard**: `[ TOUCHPOINT_1 | TOUCHPOINT_2 | ... ] Story Title` (Front-to-Back: `UI` -> `PY` -> `API` -> `DB`)[cite: 7, 8]
- **Initial Story Transition**: `Defining` (Keyword: `design`)[cite: 7, 8]

### 4.1 Epic Mapping Summary
- **New Epic**: `Statement Ingestion UI` (Initial Status: `Implementing`, Keyword: `implementing`)[cite: 7, 8]
- **Existing Epic**: `PET-4` (`Tabular UI`)[cite: 7, 8]

---

## 5. Story Backlog Definitions

### Story 1
**Target Epic**: `Statement Ingestion UI` (New Epic)[cite: 7, 8] 
**Title**: `[ UI | PY | DB ] Top Margin Alignment & Scaled Metric Card Typography`[cite: 7, 8]

**Description**:
AS A Personal Tracker User  
I WANT TO view aligned top margins, static sticky page header titles, and equal-height 215px metric cards  
SO THAT the application layout is clean, balanced, and visually consistent[cite: 7, 8].  

Acceptance Criteria:

Scenario 1: Sidebar Header Removal & Static Header Title  
GIVEN the Streamlit dashboard is open  
WHEN the page renders  
THEN native sidebar header buttons are hidden, and the active page title displays cleanly in the top-left of the sticky header bar[cite: 7, 8].  

Scenario 2: Scaled Typography and Equal Heights  
GIVEN I am on the Upload screen  
WHEN the metric cards render  
THEN Total Transactions displays in 8.8rem font, and all three bordered cards match 215px height[cite: 7, 8].  

---

### Story 2
**Target Epic**: `PET-4` (`Tabular UI`)[cite: 7, 8] 
**Title**: `[ UI | PY | DB ] Explicit 10-Row Table Pagination`[cite: 7, 8]

**Description**:
AS A Personal Tracker User  
I WANT TO navigate historical transactions in chunks of 10 rows using explicit page controls  
SO THAT I can inspect records cleanly without infinite vertical scrolling[cite: 7, 8].  

Acceptance Criteria:

Scenario 1: Explicit Page Slice Controls  
GIVEN historical transactions exist in SQLite  
WHEN the table renders  
THEN exactly 10 rows display per page with Previous/Next page controls updating the view[cite: 7, 8].