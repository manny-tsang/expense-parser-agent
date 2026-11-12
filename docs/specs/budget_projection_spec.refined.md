Refinement Pass: 1

## 0. Questions & Clarification Needed for Human Sign-Off

- **Question**: Row Granularity vs. Column Schema for Multi-Currency Categories
  - **Justification & Impact**: Section 3.2 states that categories with transactions across multiple currencies should spawn multiple rows formatted as `<Category> (Currency)` (e.g., `Groceries (AUD)`), while Section 3.3.1 specifies a fixed 7-column schema containing AUD, HKD, and USD columns simultaneously. Clarification is required to ensure consistent table rendering and CSV output structure.
  - **Proposed Default / Response**: Each unique currency active for a category will produce a distinct row labeled `Category (Currency)`. In each row, only the matching currency columns (`Historical Monthly Avg (Currency)` and `Target Monthly Budget (Currency)`) will contain active non-zero values, while non-matching currency columns for that row will strictly default to `0.00`.

- **Question**: Outlier Exclusion Criteria for Transactions Lacking Stored AUD Equivalents
  - **Justification & Impact**: Section 3.1 states outlier suppression applies only to transactions with a stored AUD amount. If foreign currency transactions (HKD/USD) lack a pre-calculated AUD equivalent field in the ledger database, their handling under high values must be defined.
  - **Proposed Default / Response**: Any transaction lacking a stored `amount_aud` value will be bypass-approved for baseline historical calculations without outlier filtering (treated as non-outlier native currency spend).

- **Question**: Re-Initialization Trigger Handling for User-Customized Target Values
  - **Justification & Impact**: Section 3.2 mandates that modifying the Lookback Window or Outlier Threshold slider auto-resets all target budget edits to baseline values. Confirm whether user edits should be preserved during threshold adjustments if the baseline average for a row remains unchanged.
  - **Proposed Default / Response**: Maintain strict auto-reset behavior: any shift in lookback window or outlier threshold triggers a full overwrite of `Target Monthly Budget` values across all rows, re-initializing them to the newly computed baseline averages and displaying an inline warning notice.

---

## 1. Module Overview & Primary Intent
- **Epic Title**: HK Card Budget Projection Engine
- **Epic Description**: As a Personal Expense Tracker user, I want a forward-looking budget planning engine to compute rolling spend baselines across multi-currency accounts (AUD, HKD, USD), suppress transaction outliers, set target category allocations, and export summaries to external spreadsheets.

---

## 2. Module Boundaries & Ownership Contracts
- **Primary Source Files**: 
  - `src/app.py` (Presentation, Interactive Target Controls, `st.data_editor` UI state management).
  - `src/repository.py` (Historical Aggregations, Distinct Month Computations, Baseline & Target Calculations).
- **Allowed Dependencies**: `pandas`, `sqlite3`, `streamlit`, `DatabaseRepository`.
- **Forbidden Operations**: 
  - Presentation layer (`src/app.py`) MUST NOT execute raw SQL queries directly.
  - Baseline transaction records in the ledger database MUST NOT be altered, mutated, or deleted during projection calculations or interactive adjustments.
  - Presentation layer MUST NOT perform dynamic runtime FX currency conversion rates.

---

## 3. Detailed Technical Requirements & Business Rules

### 3.1 Historical Baseline & Rolling Averages
1. **Window Selection**:
   - The user selects a historical lookback window via a UI selector: `Trailing 3 Months`, `Trailing 6 Months`, or `Trailing 12 Months`.
2. **Partial Lookback Window & Global Distinct Month Handling**:
   - A **Distinct Month** ($N_{months}$) is defined as a unique `YYYY-MM` calendar period containing at least one valid, non-outlier transaction anywhere in the global ledger database.
   - The denominator ($N_{months}$) is calculated globally across the entire database ledger for the selected lookback timeframe.
   - If $0 < N_{months} < \text{Requested Window}$, monthly averages are computed using $N_{months}$ as the denominator, and the UI MUST display an inline warning badge:  
     `⚠️ Partial history: Calculation based on N distinct month(s)`
   - If $N_{months} = 0$, default $N_{months}$ to `1` for calculation purposes, return `0.00` for all category averages, and render an inline informational badge:  
     `ℹ️ No historical transactions found in selected window`
   - Categories with zero transactions in the selected lookback window default their `Historical Monthly Avg` to `0.00` across all currency columns.
3. **Base Currency & Multi-Currency Isolation**:
   - Primary reporting currency across global ledger views is AUD.
   - Baseline historical aggregations evaluate stored native transactions directly without performing dynamic runtime FX conversions.
   - Historical baseline averages and target budgets are calculated independently for each currency code (`AUD`, `HKD`, `USD`) without cross-currency blending.
4. **Outlier Suppression & Native Currency Limits**:
   - The outlier exclusion threshold is configurable per session via a UI slider ranging from `$0.00` to `$100,000.00 AUD` (default: `$1,000.00 AUD`). Setting the slider to `$0.00` disables outlier suppression entirely.
   - Suppression applies **ONLY** to transactions that possess a valid stored AUD amount (`amount_aud`).
   - Transactions in foreign currencies (`HKD`, `USD`) that do not possess a stored AUD equivalent amount are NOT converted to AUD and are NOT subject to outlier filtering; they are fully included in historical baseline calculations for their native currency.
   - A line item with an AUD amount is excluded from historical calculations if $\text{Amount}_{\text{AUD}} \ge \text{Threshold}_{\text{Slider}}$.
   - The UI MUST display the notice: `"Transactions performed in AUD above the set threshold are excluded from projection calculations."`
   - If all transactions in a lookback period for a given category/currency are flagged as outliers, that category's average spend computes to `0.00` while preserving the global $N_{months}$ denominator.
5. **Refunds and Credit Line Items**:
   - Negative line items (refunds/credits) are included in the category net sum for a given month unless their absolute value $|\text{Amount}_{\text{AUD}}| \ge \text{Threshold}_{\text{Slider}}$.

### 3.2 Target Budget Allocation & Interactive Overrides
1. **Default State**:
   - Upon initial load or lookback window/threshold change, `Target Monthly Budget (Currency)` fields for `AUD`, `HKD`, and `USD` default to their computed `Historical Monthly Avg (Currency)` values.
   - For categories with historical spend across multiple currencies, a distinct row is generated per active currency formatted as `<Category> (Currency)` (e.g., `Groceries (AUD)` and `Groceries (HKD)`). Non-applicable currency columns for that specific row are populated with `0.00`.
   - Single-currency categories yield exactly one row labeled `<Category> (Currency)`, with inactive currency columns set to `0.00`.
2. **Inline Table Target Adjustments (`st.data_editor`)**:
   - All budget edits MUST occur directly within `st.data_editor`. No separate override form or expander widget is permitted.
   - Column configuration:
     - Columns 1–4 (`Category`, `Historical Monthly Avg (AUD)`, `Historical Monthly Avg (HKD)`, `Historical Monthly Avg (USD)`) are read-only (`disabled=True`).
     - Columns 5–7 (`Target Monthly Budget (AUD)`, `Target Monthly Budget (HKD)`, `Target Monthly Budget (USD)`) are editable inline via `st.column_config.NumberColumn(format="$%.2f", min_value=0.0, step=10.0)`.
   - The `Total` summary row MUST be dynamically calculated from the edited category rows in real time and rendered as a locked, read-only bottom row.
   - Edits must be non-negative numbers ($\ge 0.00$). If invalid or negative input occurs, the UI displays an inline validation error (`"Target budget must be >= 0.00"`) and resets the cell value to `0.00`.
   - Explicit entry of `0.00` is valid and denotes intentional target phase-out.
   - Modifying the Lookback Window or Outlier Slider auto-resets all `Target Monthly Budget` values to match newly calculated baseline averages, displaying an inline session notification.
3. **Summary Aggregation**:
   - Independent totals are computed in real time for `Total Projected Monthly Spend (AUD)`, `Total Projected Monthly Spend (HKD)`, and `Total Projected Monthly Spend (USD)`.

### 3.3 Google Sheets Transfer Summary & Export Formats

#### 3.3.1 Summary Data Structure & Schema
- The exported and displayed summary table contains 7 columns in exact sequence:
  1. `Category` (Text)
  2. `Historical Monthly Avg (AUD)` (Float64)
  3. `Historical Monthly Avg (HKD)` (Float64)
  4. `Historical Monthly Avg (USD)` (Float64)
  5. `Target Monthly Budget (AUD)` (Float64)
  6. `Target Monthly Budget (HKD)` (Float64)
  7. `Target Monthly Budget (USD)` (Float64)
- A read-only `Total` row MUST be appended at the bottom, calculating column sums across all active category rows.

#### 3.3.2 Streamlit Rendering & Export Options
1. **Component**: Rendered via `st.data_editor(hide_index=True, num_rows="fixed")`.
2. **Real-Time Total & KPI Sync**: Any inline edit recalculates the `Total` row and top KPI summary cards (`Total Projected Monthly Spend AUD/HKD/USD`) instantaneously.
3. **Numeric Precision**: Underlying `pandas.DataFrame` columns maintain unformatted `float64` values to 2 decimal places for raw CSV exports.
4. **Export Interoperability**: Executed via native `st.download_button`, exporting the summary table (including active category rows and the `Total` row) as a standard CSV matching UI column names.

---

## 4. User Stories & BDD Acceptance Criteria

### Story 1: Calculate Category Baseline Averages
**AS A** personal expense tracker user,  
**I WANT TO** select a historical lookback window and outlier threshold,  
**SO THAT** I can view realistic baseline monthly averages per category across multi-currency accounts without distorted transaction anomalies.

#### Acceptance Criteria (Gherkin):

```gherkin
Feature: Calculate Category Baseline Averages

  Background:
    Given the ledger database contains historical transactions across multiple currencies
    And the user is on the HK Card Budget Projection page

  Scenario: Computing monthly baseline spend for standard lookback window
    Given the database contains active transactions spanning 3 distinct calendar months
    And the transaction ledger contains the following baseline records:
      | category     | currency | amount_native | amount_aud | transaction_month |
      | Dining Out   | AUD      | 150.00        | 150.00     | 2023-01           |
      | Dining Out   | AUD      | 300.00        | 300.00     | 2023-02           |
      | Dining Out   | AUD      | 450.00        | 450.00     | 2023-03           |
      | Travel       | HKD      | 800.00        | null       | 2023-01           |
      | Travel       | HKD      | 400.00        | null       | 2023-02           |
    When the user selects the lookback window "Trailing 3 Months"
    And sets the outlier suppression threshold slider to "$1,000.00 AUD"
    Then the calculated historical monthly averages should be:
      | category         | Historical Monthly Avg (AUD) | Historical Monthly Avg (HKD) | Historical Monthly Avg (USD) |
      | Dining Out (AUD) | 300.00                       | 0.00                         | 0.00                         |
      | Travel (HKD)     | 0.00                         | 400.00                       | 0.00                         |
    And no historical status warning badges should be displayed

  Scenario Outline: Global distinct month partial history and zero transaction states
    Given the database contains valid non-outlier transactions spanning <distinct_months_count> distinct calendar months
    When the user selects the lookback window "<selected_window>"
    Then the system should compute baseline averages using denominator <effective_denominator>
    And the UI display status should show "<ui_status_badge>"

    Examples:
      | selected_window   | distinct_months_count | effective_denominator | ui_status_badge                                           |
      | Trailing 6 Months | 4                     | 4                     | ⚠️ Partial history: Calculation based on 4 distinct month(s) |
      | Trailing 3 Months | 1                     | 1                     | ⚠️ Partial history: Calculation based on 1 distinct month(s) |
      | Trailing 3 Months | 0                     | 1                     | ℹ️ No historical transactions found in selected window     |

  Scenario Outline: Outlier suppression filtering on AUD and foreign currency transactions
    Given the transaction ledger contains the following items in a single distinct month lookback window:
      | category  | currency | amount_native   | amount_aud   |
      | Groceries | AUD      | <aud_amount>    | <aud_amount> |
      | Software  | USD      | <usd_amount>    | null         |
    When the user sets the outlier suppression threshold slider to "<threshold_setting>"
    Then the computed historical baseline for "Groceries (AUD)" should equal <expected_aud_avg>
    And the computed historical baseline for "Software (USD)" should equal <expected_usd_avg>

    Examples:
      | aud_amount | usd_amount | threshold_setting | expected_aud_avg | expected_usd_avg |
      | 1500.00    | 200.00     | $1,000.00 AUD     | 0.00             | 200.00           |
      | 950.00     | 200.00     | $1,000.00 AUD     | 950.00           | 200.00           |
      | 1500.00    | 200.00     | $0.00 AUD         | 1500.00          | 200.00           |
```

---

### Story 2: Interactive Target Adjustments & Dynamic Export
**AS A** personal expense tracker user,  
**I WANT TO** edit target budget values inline within the projection table and export the summary,  
**SO THAT** I can dynamically plan monthly category spend allocations and transfer verified projection summaries to external tools.

#### Acceptance Criteria (Gherkin):

```gherkin
Feature: Interactive Target Adjustments & Dynamic Export

  Background:
    Given the system has calculated historical averages for 1 distinct calendar month
    And the following summary table state is loaded into `st.data_editor`:
      | Category         | Historical Monthly Avg (AUD) | Historical Monthly Avg (HKD) | Historical Monthly Avg (USD) | Target Monthly Budget (AUD) | Target Monthly Budget (HKD) | Target Monthly Budget (USD) |
      | Groceries (AUD)  | 500.00                       | 0.00                         | 0.00                         | 500.00                      | 0.00                        | 0.00                        |
      | Utilities (HKD)  | 0.00                         | 1200.00                      | 0.00                         | 0.00                        | 1200.00                     | 0.00                        |
      | Total            | 500.00                       | 1200.00                      | 0.00                         | 500.00                      | 1200.00                     | 0.00                        |

  Scenario: Inline editing updates totals and top KPI cards in real time
    When the user edits the cell "Target Monthly Budget (AUD)" for "Groceries (AUD)" to "650.00" directly in `st.data_editor`
    Then the read-only summary row "Total" should immediately update "Target Monthly Budget (AUD)" to "650.00"
    And the top KPI summary card "Total Projected Monthly Spend (AUD)" should display "$650.00"
    And the historical baseline columns should remain unchanged at "500.00"

  Scenario Outline: Validation of target budget entry inputs
    When the user enters "<user_input>" into an editable target budget cell in `st.data_editor`
    Then the system should evaluate the input state as "<expected_status>"
    And the cell target value should settle to "<final_cell_value>"
    And the UI warning notification state should be "<ui_notification>"

    Examples:
      | user_input | expected_status | final_cell_value | ui_notification                |
      | 750.00     | Valid           | 750.00           | None                           |
      | 0.00       | Valid Phase-Out | 0.00             | None                           |
      | -150.00    | Invalid         | 0.00             | Target budget must be >= 0.00  |

  Scenario: Automatic target re-initialization on lookback parameter shift
    Given the user has modified "Target Monthly Budget (AUD)" for "Groceries (AUD)" to "800.00"
    When the user changes the lookback window selector to "Trailing 6 Months"
    Then all "Target Monthly Budget" fields should automatically reset to match the newly calculated "Historical Monthly Avg" values
    And an inline session notification should state "Target budgets re-initialized to historical baselines."

  Scenario: CSV summary file export structure
    Given the current projection summary table displays 2 active category rows and 1 read-only Total row
    When the user clicks the "Download CSV" button
    Then a CSV file should be generated containing exactly 7 columns in order:
      """
      Category,Historical Monthly Avg (AUD),Historical Monthly Avg (HKD),Historical Monthly Avg (USD),Target Monthly Budget (AUD),Target Monthly Budget (HKD),Target Monthly Budget (USD)
      """
    And the generated CSV must include the bottom "Total" row with matching aggregated column sums
```