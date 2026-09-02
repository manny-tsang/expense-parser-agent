# Specification: Analytics & Spending Insights UI (`ui_charts_spec.md`)

## 1. Objective
AS A Personal Tracker User  
I WANT TO view graphical spending breakdowns and tabular monthly averages in AUD on a unified analytics dashboard  
SO THAT I can accurately assess category spending baselines and transfer calculated monthly averages directly into my master budget spreadsheet.

## 2. Technical Stack & Dependencies
- **Language**: Python 3.x
- **UI Framework**: Streamlit (`src/app.py`), `streamlit-option-menu`
- **Visualization Library**: `plotly` (`plotly.express`, `plotly.graph_objects`), `st.plotly_chart`
- **Data Engine & Repository**: `src/repository.py` (`DatabaseRepository`), `pandas`, `numpy`
- **Database Target**: `db/personal-expense-tracker.db`
- **Database Ownership Contract**:
  - `src/repository.py` exclusively owns database queries and data frame retrievals.
  - `src/app.py` executes analytics reads strictly via `DatabaseRepository.get_transactions_dataframe()` without direct SQLite connection handles.

---

## 3. Jira Automation & Story Backlog Definitions

- **Project Key**: `PET`
- **Prefix Standard**: `[ TOUCHPOINT_1 | TOUCHPOINT_2 | ... ] Story Title` (Front-to-Back: `UI` -> `PY` -> `API` -> `DB`)
- **Epic Mapping**:
  - **`PET-7`** (`Graphical UI`): Donut chart, visual metrics, and filtering controls.
  - **`PET-4`** (`Tabular UI`): Paginated category budget statistics and monthly average calculations.

### Story 1 (Epic: PET-7)
**Title**: `[ UI | PY | DB ] AUD Category Donut Visualization & Filtering Bar`

**Description**:
AS A Personal Tracker User  
I WANT TO filter transactions by date ranges and categories to view a Plotly donut chart centered on total AUD spend  
SO THAT I can instantly visualize my top spending categories for any selected time window.

Acceptance Criteria:

Scenario 1: Default View on Initial Page Load
GIVEN I navigate to the Charts view for the first time
WHEN the page finishes loading
THEN the date range preset automatically defaults to "This Month", displaying only current month AUD spending statistics.

Scenario 2: AUD Donut Chart Rendering  
GIVEN historical transactions exist in SQLite  
WHEN the donut chart renders  
THEN a Plotly donut chart displays spending per category in AUD in Row 1 Column 1, with total AUD spend centered in the cutout and a sub-metric badge flagging *"Transactions in currencies other than AUD"* if unconverted foreign transactions exist.

Scenario 3: Preset Date Range Filtering  
GIVEN the filter control card in Row 1 Column 2  
WHEN I switch date presets ("This Month", "Last 3 Months", "Last 6 Months", "Year to Date", "All Time")  
THEN the donut chart and category table instantly recalculate totals and monthly averages for the selected period.

---

### Story 2 (Epic: PET-4)
**Title**: `[ UI | PY | DB ] Category Monthly Average Budget Table & Outlier Callouts`

**Description**:
AS A Personal Expense Tracker User  
I WANT TO inspect a tabular breakdown of total AUD spend, monthly averages, percentage shares, and maximum single transactions  
SO THAT I can copy accurate monthly category averages into my personal budget spreadsheet.

Acceptance Criteria:

Scenario 1: Tabular Budget Statistics Calculation  
GIVEN a filtered transaction dataset  
WHEN Row 2 renders  
THEN a full-width DataFrame displays columns: `Category`, `Total Spend (AUD)`, `Monthly Average (AUD)`, `% of Total`, `Txn Count`, and `Max Single Txn (AUD)` sorted by `Total Spend (AUD) DESC`.

Scenario 2: Configurable Single Transaction Outlier Callout  
GIVEN transactions in the selected period exceeding the configurable threshold (defaulting to $1,000 AUD)  
WHEN the table renders  
THEN an inline visual highlight flags large individual transactions to alert me to single-item budget anomalies.

---

## 4. UI Design & Layout Architecture (`src/app.py`)

### 4.1 Header & Alignment Standard
- Target `render_charts_page()` in `src/app.py`.
- Injects persistent sticky title `"Charts & Insights"` via `inject_css("Charts")`.

### 4.2 Two-Row Dashboard Layout

#### Row 1: Interactive Donut Chart & Filter Control Card (`st.columns([3, 2])`)
- **Column 1 (Plotly Donut Chart Card)**:
  - Enclosed inside `st.container(border=True, height="stretch")`.
  - **Plotly Donut Spec**:
    - `hole=0.55` displaying total AUD spend formatted as `$XX,XXX.XX` (supporting 5-figure monthly totals) inside the center cutout.
    - Custom color palette matching Streamlit dark theme (`#0E1117`, `#262730`, `#1F77B4`, etc.).
    - Interactive legend and hover tooltips showing `Category`, `Total Spend (AUD)`, and `% of Total`.
  - **Sub-Metric Badge**: Below the chart, render `st.caption("ℹ️ Transactions in currencies other than AUD")` if native non-AUD records exist in the selection.
- **Column 2 (Filter Controls Card)**:
  - Enclosed inside `st.container(border=True, height="stretch")`.
  - **Date Range Presets**: `st.radio("Date Range", options=["This Month", "Last 3 Months", "Last 6 Months", "Year to Date", "All Time"], index=0, horizontal=True, key="charts_date_preset")`.
  - **Custom Date Fallback**: `st.date_input("Custom Date Range", value=(), key="charts_custom_date")`.
  - **Category Filter**: `st.multiselect("Filter Categories", options=category_list, default=category_list, key="charts_category_filter")`.
  - **Outlier Threshold Input**: `st.number_input("Highlight Outliers Above ($)", value=1000, step=100, key="charts_outlier_threshold")`.

#### Row 2: Category Budget Statistics Table (`Full Width`)
- Enclosed inside `st.container(border=True)`.
- **Subheader**: `st.subheader("Category Budget Statistics")`.
- **Description**: `st.markdown("Monthly averages calculated across the selected date range for direct import into budget spreadsheets.")`.
- **DataFrame Schema & Calculations**:
  - `Months in Range` $N = \max\left(1, \frac{\text{Days Between Min and Max Date}}{30.44}\right)$.
  - `Category`: `category_name`.
  - `Total Spend (AUD)`: `SUM(txn_amount)` formatted as `$X,XXX.XX`.
  - `Monthly Average (AUD)`: `SUM(txn_amount) / N` formatted as `$X,XXX.XX`.
  - `% of Total`: `(Category Spend / Total Spend) * 100` formatted as `XX.X%`.
  - `Txn Count`: `COUNT(t.id)`.
  - `Max Single Txn (AUD)`: `MAX(txn_amount)` formatted as `$X,XXX.XX`.
- **Outlier Indicator**: Highlights cells or appends an asterisk `*` to `Max Single Txn (AUD)` values exceeding `charts_outlier_threshold`.