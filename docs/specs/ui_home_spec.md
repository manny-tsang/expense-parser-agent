# Specification: Home Landing Page UI

## 1. Objective
AS A Personal Expense Tracker user  
I WANT TO have a landing page that serves as an executive summary upon launching the application  
SO THAT I have a snapshot view of key statistics that help me quickly understand the landscape of my expenses for the year so far, whilst also giving me view of any outstanding actions that I need to take.

## 2. Technical Stack & Dependencies
- **Language**: Python 3.x
- **UI Framework**: Streamlit (`src/app.py`), `streamlit-option-menu`, `plotly.graph_objects`
- **Data Engine & Repository**: `src/repository.py` (`DatabaseRepository`)
- **Database Target**: `db/personal-expense-tracker.db`

---

## 3. UI Design & Layout Architecture (`src/app.py`)

### 3.1 Sidebar Navigation Standard & Brand Logo
- **Brand Logo Placeholder**:
  - Rendered at the top of the sidebar above menu items.
  - Geometry: Aspect ratio strictly 1:1 (Square).
  - Width: Set to `160px` (guaranteed to be wider than the longest menu item, `"Categorise"`).
  - Implementation: `st.sidebar.image("assets/logo_placeholder.png", width=160)` or SVG placeholder container.
- **Menu Items**: `["Home", "Upload", "Categorise", "Charts", "Search"]`
- **Icons**: `["house", "cloud-upload", "tag", "bar-chart", "search"]`
- **Default Index**: `0` (Home)

### 3.2 Page Header & Introductory Copy
- **Header Title**: `Home`
- **Page Descriptor Text**:  
  `st.markdown("Welcome to your Personal Expense Tracker — a central dashboard designed to aggregate multi-currency credit card statements, automate merchant categorisation, and track long-term spending patterns.")`

### 3.3 Three-Row Home Screen Architecture

#### Row 1: KPI Summary Cards (3 Equal Columns, Equal Height)
All cards MUST be enclosed inside `st.container(border=True, height="stretch")`.

- **Column 1: Spend last 30-days**
  - Subheader: `st.subheader("Spend last 30-days")`
  - Calculation: Sum of `txn_amount` in AUD where `trans_date` falls within the last 30 days relative to the maximum `trans_date` stored in SQLite.
  - Subtext: Displays date span (e.g., `"12 Aug 2026 - 11 Sep 2026"`).

- **Column 2: Spend year-to-date**
  - Subheader: `st.subheader("Spend year-to-date")`
  - Calculation: Sum of `txn_amount` in AUD for the current calendar year of the latest ingested transaction.
  - Subtext: Displays total YTD record count.

- **Column 3: Uncategorised merchants (Clickable Container)**
  - Subheader: `st.subheader("Uncategorised merchants")`
  - Calculation: Count of distinct merchants where `category_id = 1` ('Uncategorised').
  - Subtext: If count > 0, displays `"Click card to manage unmapped merchants →"`.
  - Interaction: Clicking inside the container sets navigation state to `"Categorise"` and executes `st.rerun()`.

#### Row 2: Visual Analytics & System Operations (Split 3:2 Ratio)

- **Column 1 (Left, 60% Width) - Spending trend**:
  - Container Wrapper: `st.container(border=True)`
  - Subheader: `st.subheader("Spending trend")`
  - Description: `st.markdown("Year-on-year comparison showing the spend trajectory based on the current year-to-date position.")`
  - Component: `st.plotly_chart` rendering `plotly.graph_objects.Figure`.
  - Data Series:
    - **Current YTD (Solid Line, `#4A90E2`)**: Monthly total AUD spend from Jan through the latest month of the current year.
    - **Prior YTD (Dashed Line, `#808495`)**: Monthly total AUD spend for matching months of the prior year.

- **Column 2 (Right, 40% Width) - Tracker status**:
  - Container Wrapper: `st.container(border=True)`
  - Subheader: `st.subheader("Tracker status")`
  - Display Fields:
    - `Last statement uploaded`: Filename from `statement_log`.
    - `Ingestion date`: Processed timestamp.
    - `Total transactions`: Total record count in `"transaction"`.
    - `Categorisation health`: Percentage of transactions mapped to non-default categories.

#### Row 3: Recent Transactions Log Table (Full Width)
- Container Wrapper: `st.container(border=True)`
- Subheader: `st.subheader("Last 10 transactions")`
- Table: Full-width DataFrame displaying the 10 most recently ingested transactions (`ORDER BY id DESC`).
- Columns: `Transaction date`, `Merchant`, `Category`, `Amount ($AUD)`, `HKD Amount`, `FX Rate`.

---

## 4. Jira Automation & Epic Structure

- **Project Key**: `PET`
- **Epic Title**: `Home UI`

---

## 5. Story Backlog Definitions

### Story 1: Brand Logo & Sidebar Expansion
**Target Epic**: `Home UI`  
**Title**: `[ UI | PY | DB ] Sidebar Brand Logo Placeholder & Menu Navigation`

**Description**:
AS A Personal Expense Tracker user  
I WANT TO see a square brand logo above the sidebar navigation items  
SO THAT the application maintains a distinct, professional visual identity.

Acceptance Criteria:
- **Scenario 1: Brand Logo Sizing & Position**:  
  GIVEN the application is launched  
  WHEN the sidebar renders  
  THEN a square 1:1 aspect ratio logo placeholder displays above the menu items with a width wider than `"Categorise"`.

- **Scenario 2: Missing Logo Asset**:  
  GIVEN the logo image asset file is missing or unreadable  
  WHEN the sidebar renders  
  THEN the application falls back gracefully to a styled text/SVG placeholder without throwing an uncaught exception or breaking sidebar navigation.

---

### Story 2: Spend Last 30-Days Widget
**Target Epic**: `Home UI`  
**Title**: `[ UI | PY | DB ] Rolling 30-Day Spend KPI Widget`

**Description**:
AS A Personal Expense Tracker user  
I WANT TO view my total AUD expenditure over the last 30 rolling days  
SO THAT I can track my active monthly burn rate regardless of statement cutoff dates.

Acceptance Criteria:
- **Scenario 1: Rolling 30-Day Calculation**:  
  GIVEN transactions exist in SQLite  
  WHEN the Home view loads  
  THEN "Spend last 30-days" displays the sum of $AUD expenses from the past 30 days relative to the latest transaction date.

- **Scenario 2: Empty Database**:  
  GIVEN no transaction records exist in the database  
  WHEN the Home view loads  
  THEN "Spend last 30-days" displays `$0.00` with date span `"N/A"`.

---

### Story 3: Spend Year-to-Date Widget
**Target Epic**: `Home UI`  
**Title**: `[ UI | PY | DB ] Year-to-Date Spend KPI Widget`

**Description**:
AS A Personal Expense Tracker user  
I WANT TO view my cumulative YTD spend in AUD on the Home landing page  
SO THAT I can evaluate my overall annual expenditure at a glance.

Acceptance Criteria:
- **Scenario 1: YTD Spend Calculation**:  
  GIVEN transaction records exist  
  WHEN the Home page renders  
  THEN "Spend year-to-date" calculates and displays the total $AUD spend for the current calendar year.

- **Scenario 2: No Current Year Data**:  
  GIVEN imported transactions exist only for previous calendar years  
  WHEN the Home page renders  
  THEN "Spend year-to-date" evaluates relative to the latest transaction's calendar year and displays the total for that active dataset year.

---

### Story 4: Uncategorised Merchants Action Widget
**Target Epic**: `Home UI`  
**Title**: `[ UI | PY | DB ] Uncategorised Merchants Action Widget & Tab Navigation`

**Description**:
AS A Personal Expense Tracker user  
I WANT TO view outstanding uncategorised merchants and click the card to jump directly to the Categorise view  
SO THAT I can promptly resolve unmapped merchants.

Acceptance Criteria:
- **Scenario 1: Outstanding Count & Card Interaction**:  
  GIVEN unmapped merchants exist  
  WHEN I click inside the "Uncategorised merchants" card container  
  THEN the application switches navigation to the "Categorise" view.

- **Scenario 2: Zero Uncategorised Merchants**:  
  GIVEN all merchants in SQLite are mapped to categories (`category_id != 1`)  
  WHEN the "Uncategorised merchants" card renders  
  THEN it displays `0` with subtext `"All merchants categorised"`, and clicking the card still navigates cleanly to "Categorise".

---

### Story 5: Spending Trend YoY Trajectory Chart
**Target Epic**: `Home UI`  
**Title**: `[ UI | PY | DB ] Year-on-Year Spending Trend Trajectory Chart`

**Description**:
AS A Personal Expense Tracker user  
I WANT TO view a dual-line chart comparing current YTD monthly spend against the prior year  
SO THAT I can track whether my spending trajectory is pacing higher or lower than last year.

Acceptance Criteria:
- **Scenario 1: Dual-Line YoY Comparison**:  
  GIVEN historical transaction data exists for both current and prior years  
  WHEN the "Spending trend" widget renders  
  THEN it plots a solid line for current YTD months and a dashed line for matching prior-year months.

- **Scenario 2: Single-Year Data Available**:  
  GIVEN transaction data exists for only one calendar year  
  WHEN the "Spending trend" widget renders  
  THEN it plots the solid line for the available year, omits the prior-year dashed line, and renders a subtle caption `"Prior year comparison unavailable"`.

---

### Story 6: Tracker Status Ingestion Widget
**Target Epic**: `Home UI`  
**Title**: `[ UI | PY | DB ] Tracker System & Statement Ingestion Status Widget`

**Description**:
AS A Personal Expense Tracker user  
I WANT TO view system health metrics and statement ingestion logs  
SO THAT I can verify that my latest statements were imported successfully.

Acceptance Criteria:
- **Scenario 1: Status Metadata Display**:  
  GIVEN processed statements exist in `statement_log`  
  WHEN "Tracker status" renders  
  THEN it displays the latest filename, import date, total database records, and categorisation health %.

- **Scenario 2: No Statements Uploaded**:  
  GIVEN `statement_log` is empty  
  WHEN "Tracker status" renders  
  THEN it displays `"None"` for statement name and date, `0` total transactions, and `0%` categorisation health.

---

### Story 7: Last 10 Transactions Log
**Target Epic**: `Home UI`  
**Title**: `[ UI | PY | DB ] Recent 10 Transactions Log Table`

**Description**:
AS A Personal Expense Tracker user  
I WANT TO view the 10 most recently uploaded transactions in a full-width table  
SO THAT I can review the latest imported line items immediately upon launching the app.

Acceptance Criteria:
- **Scenario 1: Recent Records Table**:  
  GIVEN transactions are stored in SQLite  
  WHEN the Home page loads  
  THEN "Last 10 transactions" displays the 10 most recent rows ordered by database insertion.

- **Scenario 2: Fewer Than 10 Transactions**:  
  GIVEN fewer than 10 total transactions exist in the database  
  WHEN the Home page loads  
  THEN the table displays all available records without pagination errors or empty row padding.