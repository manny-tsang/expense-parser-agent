# Specification: Statement Ingestion & Operational Dashboard UI

## 1. Objective
Build a modular, multi-page ready Streamlit web application (`src/app.py`) featuring styled sidebar navigation using `streamlit-option-menu`. The primary view focuses on **Upload**, featuring a high-density layout with aligned top margins, uniform 240px-height 3-column bordered cards with scaled typography, followed by an explicitly paginated 10-row transaction table.

## 2. Technical Stack & Dependencies
- **Language**: Python 3.x
- **UI Framework**: Streamlit (`streamlit`), `streamlit-option-menu`
- **Data & Processing**: `pandas`, `sqlite3`, `re`, `os`, `math`
- **Core Engine**: `src/pdf_parser.py` (`parse_statement()`)
- **Database Target**: `db/personal-expense-tracker.db`
- **Database Ownership Contract**: 
  - `src/app.py` MUST NOT execute `CREATE TABLE` queries or manage database schemas.
  - Database table creation and normalized schema management are exclusively owned by `src/pdf_parser.py`.

---

## 3. UI Design Principles & Responsive Layout
### 3.1 Sticky Header & Flex Height Equalization (CSS Injection)
Inject strict CSS via `st.markdown("<style>...</style>", unsafe_allow_html=True)` to fix sidebar top margin offset, solid sticky header alignment, and equal card border stretching:

- **Sidebar Flush Top Alignment**:
  - `[data-testid="stSidebarHeader"] { display: none !important; }`
  - `section[data-testid="stSidebar"] > div:first-child { padding-top: 0.5rem !important; }`
  - `[data-testid="stSidebarContent"] { padding-top: 0rem !important; margin-top: 0rem !important; }`

- **Solid Left-Aligned Sticky Header**:
  - Target `[data-testid="stHeader"]` with `background-color: #0e1117 !important; z-index: 999 !important; display: flex !important; justify-content: flex-start !important; padding-left: 2rem !important;`
  - Inject sticky page title ("Upload") flush left using `::before`.

- **Main Content Padding**:
  - `.block-container { padding-top: 4rem !important; padding-bottom: 1rem !important; padding-left: 2rem !important; padding-right: 2rem !important; }`

- **Equal Card Dimensions & Border Wrapper Lock**:
  - Target `div[data-testid="stVerticalBlockBorderWrapper"] > div` and set `min-height: 215px !important;` alongside `flex: 1 !important;` so Cards 2 and 3 expand to match Card 1 exactly.

- **Content Typography & Card Sizing**:
  - `.metric-large`: `font-size: 8.8rem !important; font-weight: bold !important; line-height: 1.1 !important; color: #FFFFFF !important; margin-top: 0.5rem !important;`
  - `.period-val`: `font-size: 2rem !important; font-weight: 600 !important; color: #FFFFFF !important; margin-bottom: 0.25rem !important;`
  - `.period-label`: `font-size: 0.85rem !important; color: #808495 !important; margin-top: 0.25rem !important;`

### 3.2 Sidebar Navigation
- **No Sidebar Title**: Do not render `st.sidebar.title()` or heading labels in the sidebar.
- **Option Menu Control**: Render `option_menu` inside the sidebar (`streamlit_option_menu.option_menu`) flush with the top padding:
  - Menu Items: `["Dashboard", "Upload", "Charts"]`
  - Icons: `["house", "cloud-upload", "bar-chart"]`
  - Default Index: `1` (Upload)
  - Custom Styles:
    - Sidebar background: transparent / inherited sidebar background color.
    - Text color: `#FFFFFF` (white).
    - Selected background highlight & icons: `#31333F` / matching transaction table header grey.

### 3.3 Upload View Screen Layout & Equal 3-Column Card Row
- **Header Title**: Rendered via solid sticky header CSS in `[data-testid="stHeader"]` (no `st.title()` call in body).
- **Subtitle**: `st.markdown("Upload a PDF statement to process into anonymised transactions to be stored and used for budget planning.")`

- **3-Column Flex Card Row (`st.columns(3)`)**:
  - Columns wrapped in `st.container(border=True)` flex-stretch dynamically with top-aligned headers:
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

### 3.4 Main Data Area (Paginated 10-Row Transaction Table)
1. **Grid Section Header**: `st.subheader("Transactions uploaded")`
2. **Database Repository Method Contract**:
   - `DatabaseRepository.get_transactions_dataframe(self)` queries raw transactions and returns a Pandas DataFrame.
3. **Query Strategy**:
   - Queries transactions directly from the normalized schema:
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
   - Implement explicit page controls for the DataFrame in `app.py`:
     - Calculate total pages: `math.ceil(total_rows / 10)`.
     - Maintain `current_page` in `st.session_state`.
     - Slice DataFrame: `df.iloc[(page - 1) * 10 : page * 10]`.
     - Display pagination control bar below the table with **Previous Page**, **Page X of Y**, and **Next Page** buttons.
5. **Dataframe Columns**: `trans_date`, `merchant`, `category_name`, `txn_amount`, `purchase_currency`, `hkd_amount`, `fx_rate`.

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
I WANT TO view aligned top margins and equal-height 240px metric cards with 5rem numbers  
SO THAT the Upload screen layout is balanced and easy to read.  

Acceptance Criteria:

Scenario 1: Sidebar Top Margin Offset  
GIVEN the Streamlit dashboard is open  
WHEN the page renders  
THEN `stSidebarContent` top padding is reduced to 1.5rem, placing the option menu flush with the main page title.  

Scenario 2: 5rem Metric Typography and Equal Heights  
GIVEN I am on the Upload screen  
WHEN the metric cards render  
THEN Total Transactions displays in 5rem font, and all three bordered cards match 240px height.  

---

### Story  story 2
**Target Epic**: `PET-4` (`Tabular UI`)  
**Title**: `[ UI | PY | DB ] Explicit 10-Row Table Pagination`

**Description**:
AS A Personal Tracker User  
I WANT TO navigate historical transactions in chunks of 10 rows using explicit page controls  
SO THAT I can inspect records cleanly without infinite vertical scrolling.  

Acceptance Criteria:

Scenario 1: Explicit Page Slice Controls  
GIVEN historical transactions exist in SQLite  
WHEN the table renders  
THEN exactly 10 rows display per page with Previous/Next page controls updating the view.