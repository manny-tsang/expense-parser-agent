# Specification: Statement Ingestion & Operational Dashboard UI

## 1. Objective
Build a modular, multi-page ready Streamlit web application (`src/app.py`) managed by the primary application class `PersonalExpenseTracker`. It features styled sidebar navigation using `streamlit-option-menu`. The primary views focus on **Upload** and **Categorise**, featuring a high-density layout with aligned top margins, uniform 215px-height 3-column bordered cards with scaled typography, followed by an explicitly paginated 10-row transaction table.

## 2. Technical Stack & Dependencies
- **Language**: Python 3.x
- **UI Framework**: Streamlit (`streamlit`), `streamlit-option-menu`
- **Data & Processing**: `pandas`, `sqlite3`, `re`, `os`, `math`
- **Core Engine**: `src/pdf_parser.py` (`parse_statement()`)
- **Database Target**: `db/personal-expense-tracker.db`
- **Database Ownership Contract**: 
  - `src/app.py` MUST NOT execute `CREATE TABLE` queries or manage database schemas.
  - Database table creation, normalized `merchant` table management, and schema migrations are exclusively owned by `src/pdf_parser.py`.

---

## 3. UI Design Principles & Responsive Layout

### 3.1 Main Application Structure & Naming
- **Application Class**: The primary Streamlit application class inside `src/app.py` MUST be named `PersonalExpenseTracker`.

### 3.2 Sticky Header & Flex Height Equalization (CSS Injection)
Inject strict CSS via `inject_css(page_title)` to maintain top margin offset, solid sticky header alignment, active page title display, and equal card border stretching:

- **Sidebar Flush Alignment**:
  - Hide Streamlit's native sidebar header and toggle container using `[data-testid="stSidebarHeader"] { display: none !important; }`.
  - Set `section[data-testid="stSidebar"] > div:first-child` padding to `0.5rem !important` and `[data-testid="stSidebarContent"]` top padding to `0rem !important`.

- **Solid Left-Aligned Sticky Header & Title Injection**:
  - Target `[data-testid="stHeader"]` with `background-color: #0e1117 !important; z-index: 999 !important;`.
  - Render the active page title (e.g., "Dashboard", "Upload", "Categorise", "Charts") inside the fixed top sticky header bar using `.sticky-page-title`:
    ```css
    .sticky-page-title {
        position: fixed;
        top: 0.2rem;
        left: 14.5rem;
        z-index: 1000 !important;
        pointer-events: none;
        font-size: 2rem;
        font-weight: 600;
        color: #FFFFFF;
    }
    ```

- **Main Content Padding**:
  - `.block-container { padding-top: 4rem !important; padding-bottom: 1rem !important; padding-left: 2rem !important; padding-right: 2rem !important; }`

- **Equal Card Dimensions & Border Wrapper Lock**:
  - Target `div[data-testid="stVerticalBlockBorderWrapper"] > div` and set `min-height: 215px !important;` alongside `flex: 1 !important;` so Cards 2 and 3 expand to match Card 1 exactly.

- **Content Typography & Card Sizing**:
  - `.metric-large`: `font-size: 8.8rem !important; font-weight: bold !important; line-height: 1.1 !important; color: #FFFFFF !important; margin-top: 0.5rem !important;`
  - `.period-val`: `font-size: 2rem !important; font-weight: 600 !important; color: #FFFFFF !important; margin-bottom: 0.25rem !important;`
  - `.period-label`: `font-size: 0.85rem !important; color: #808495 !important; margin-top: 0.25rem !important;`

### 3.3 Sidebar Navigation
- **No Sidebar Title**: Do not render `st.sidebar.title()` or heading labels in the sidebar.
- **Option Menu Control**: Render `option_menu` inside the sidebar (`streamlit_option_menu.option_menu`) flush with top padding:
  - Menu Items: `["Dashboard", "Upload", "Categorise", "Charts"]`
  - Icons: `["house", "cloud-upload", "tag", "bar-chart"]`
  - Default Index: `1` (Upload)
  - Custom Styles:
    - Sidebar background: transparent / inherited sidebar background color.
    - Text color: `#FFFFFF` (white).
    - Selected background highlight & icons: `#31333F` / matching transaction table header grey.

### 3.4 Upload View Screen Layout & Equal 3-Column Card Row
- **Header Title**: Active page title rendered inside sticky top header via `inject_css(selected)`.
- **Subtitle**: `st.markdown("Upload a PDF statement to process into anonymised transactions to be stored and used for budget planning.")`

- **3-Column Flex Card Row (`st.columns(3)`)**:
  - Columns wrapped in `st.container(border=True, height="stretch")` flex-stretch dynamically:
    - **Card 1 (File Picker)**:
      - Helper label: `"Upload a PDF statement"`.
      - Widgets: `st.file_uploader` (PDFs only, `label_visibility="collapsed"`) and `st.button("Process Statement", type="primary", use_container_width=True)`.
    - **Card 2 (Total Transactions Uploaded)**:
      - Content inside `<div class="metric-card-container">`:
        - Top-aligned Label: `"Total transactions uploaded"`
        - Count display: `<div class="metric-large">{total_txns}</div>` (8.8rem font size).
    - **Card 3 (Statement Period Uploaded)**:
      - Content inside `<div class="metric-card-container">`:
        - Label: `"Statement period uploaded"`
        - Date values rendered on separate lines:
          - "From:" label (`.period-label`), followed by minimum date (`Month YYYY`, e.g., `June 2026`) formatted with `.period-val` (2rem font size).
          - "To:" label (`.period-label`), followed by maximum date (`Month YYYY`, e.g., `July 2026`) formatted with `.period-val` (2rem font size).
- **Status Feedback**: Visual spinner (`st.spinner`) during processing. If duplicate or invalid, display clear error alert. Upon successful ingestion, display: `"Statement processed successfully!"`.

### 3.5 Main Data Area (Paginated Transaction Table)
1. **Grid Section Header**: `st.subheader("Transactions uploaded")`
2. **Section Subtext**: `st.markdown("This is a list of the raw transactions as they've been imported from the uploaded PDF statement.")`
3. **Database Repository Method Contract**:
   - `DatabaseRepository.get_transactions_dataframe(self)` queries raw transactions and returns a Pandas DataFrame.
4. **Normalized Query Strategy**:
   - Queries transactions using normalized entity joins:
     ```sql
     SELECT 
         t.id,
         t.trans_date, 
         m.merchant_name AS merchant, 
         COALESCE(override_cat.category_name, default_cat.category_name) AS category_name, 
         t.txn_amount, 
         curr.currency_code AS purchase_currency, 
         t.hkd_amount, 
         t.fx_rate,
         t.category_id
     FROM "transaction" t
     JOIN merchant m ON t.merchant_id = m.id
     LEFT JOIN category default_cat ON m.category_id = default_cat.id
     LEFT JOIN category override_cat ON t.category_id = override_cat.id
     LEFT JOIN currency curr ON t.purchase_currency_id = curr.id
     ORDER BY t.trans_date DESC, t.id DESC
     ```
5. **Explicit Page Size Pagination Logic**:
   - Page size configuration set to `page_size = 5` (or configurable).
   - Maintain `current_page` in `st.session_state`.
   - Slice DataFrame: `df.iloc[(page - 1) * page_size : page * page_size]`.
   - Display pagination control bar below the table with **Previous Page**, **Page X of Y**, and **Next Page** buttons.
6. **Dataframe Display Columns**: `trans_date`, `merchant`, `category_name`, `txn_amount`, `purchase_currency`, `hkd_amount`, `fx_rate`.

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
**Title**: `[ UI | PY | DB ] Top Margin Alignment & Scaled Metric Card Typography`

**Description**:
AS A Personal Tracker User  
I WANT TO view aligned top margins, static sticky page header titles, and equal-height 215px metric cards  
SO THAT the application layout is clean, balanced, and visually consistent.  

Acceptance Criteria:

Scenario 1: Sidebar Header Removal & Static Header Title  
GIVEN the Streamlit dashboard is open  
WHEN the page renders  
THEN native sidebar header buttons are hidden, and the active page title displays cleanly in the top-left of the sticky header bar.  

Scenario 2: Scaled Typography and Equal Heights  
GIVEN I am on the Upload screen  
WHEN the metric cards render  
THEN Total Transactions displays in 8.8rem font, and all three bordered cards match 215px height.  

---

### Story 2
**Target Epic**: `PET-4` (`Tabular UI`) 
**Title**: `[ UI | PY | DB ] Explicit Paginated Table Navigation`

**Description**:
AS A Personal Tracker User  
I WANT TO navigate historical transactions in configurable row chunks using explicit page controls  
SO THAT I can inspect records cleanly without infinite vertical scrolling.  

Acceptance Criteria:

Scenario 1: Explicit Page Slice Controls  
GIVEN historical transactions exist in SQLite  
WHEN the table renders  
THEN transactions display in sliced chunks per page with Previous/Next page controls updating the view.