Refinement Pass: 1

## 0. Questions & Clarification Needed for Human Sign-Off

* **Question**: How should multi-currency row splitting format the `Category` column string for unique identification in `st.data_editor`?
  * **Justification & Impact**: Section 3.2.1 specifies that categories with transactions in multiple currencies must be expanded into distinct rows formatted as `<category> (Currency)` (e.g., `Groceries (AUD)`), while Section 3.3.1 states the `Category` column is text exported directly to CSV. Clarification is required to ensure consistent row key tracking in Streamlit and CSV exports.
  * **Proposed Default / Response**: Format the `Category` string column directly as `<category> (<CUR>)` (e.g., `Groceries (AUD)`) for multi-currency split rows, and retain standard `<category>` (e.g., `Dining`) when a category contains transactions in only a single currency.

* **Question**: How is the distinct month count ($N_{months}$) defined when calendar months within a lookback window have zero recorded transactions?
  * **Justification & Impact**: Section 3.1.2 defines a Distinct Month as a unique `YYYY-MM` period containing at least one valid, non-outlier transaction in the database. If a 6-month lookback covers Jan–Jun but Feb has 0 transactions across the entire database, clarification is needed on whether $N_{months}$ equals 5 or 6.
  * **Proposed Default / Response**: Calculate $N_{months}$ strictly as `COUNT(DISTINCT strftime('%Y-%m', transaction_date))` over non-outlier ledger records within the start/end date bounds of the lookback window. If 5 calendar months contain transactions, $N_{months} = 5$.

* **Question**: Should non-AUD transactions missing a pre-populated AUD amount be entirely exempt from outlier suppression regardless of native currency magnitude?
  * **Justification & Impact**: Section 3.1.4 explicitly prohibits dynamic FX conversion for outlier filtering and states non-AUD transactions without stored AUD amounts must not be suppressed. Extreme native amounts (e.g., HKD 500,000) could skew HKD baselines if unhedged.
  * **Proposed Default / Response**: Enforce strict isolation: outlier evaluation evaluates *only* the populated `amount_aud` field against the slider threshold. Non-AUD rows lacking an AUD equivalent are never suppressed.

---

## 1. Module Overview & Primary Intent
- **Epic Title**: HK Card Budget Projection Engine
- **Epic Description**: As a Personal Expense Tracker user, I want a forward-looking budget planning engine to compute rolling spend baselines across multi-currency accounts (AUD, HKD, USD), suppress transaction outliers, set target category allocations, and export summaries to external spreadsheets.

---

## 2. Module Boundaries & Ownership Contracts
- **Primary Source Files**: 
  - `src/app.py`: Interactive UI presentation, session state control, slider widgets, `st.data_editor` integrations, and visual alert badges.
  - `src/repository.py`: Core baseline queries, global $N_{months}$ calculation, outlier suppression logic, data transformation pipelines, multi-currency row splitting, and summary math.
- **Allowed Dependencies**: `pandas`, `sqlite3`, `streamlit`, `DatabaseRepository`.
- **Forbidden Operations**: 
  - Presentation layer (`src/app.py`) MUST NOT execute raw SQL queries directly or alter database records during budget interactive adjustments.
  - Data repository (`src/repository.py`) MUST NOT invoke dynamic FX rate API calls during baseline or target calculation runs.

---

## 3. Detailed Technical Requirements & Business Rules

### 3.1 Historical Baseline & Rolling Averages
1. **Window Selection**:
   - The user selects a lookback window from three options: `Trailing 3 Months`, `Trailing 6 Months`, or `Trailing 12 Months`.
   - Start and end dates are evaluated relative to the current execution date or latest available transaction record.

2. **Partial Lookback Window & Global Distinct Month Handling**:
   - A **Distinct Month** is defined as a unique `YYYY-MM` calendar period containing at least one valid, non-outlier transaction in the database.
   - The distinct month count denominator ($N_{months}$) is calculated globally across all active categories in the database for the selected window.
   - **Calculation Logic**:
     $$\text{Historical Monthly Avg} = \frac{\sum \text{Valid Transaction Amounts in Window}}{N_{months}}$$
   - **Condition A ($N_{months} < \text{Requested Window}$)**: Compute averages using actual $N_{months}$ and render an inline UI warning badge:
     `⚠️ Partial history: Calculation based on N distinct month(s)`
   - **Condition B ($N_{months} = 0$)**: Set $N_{months} = 1$ for safety against division-by-zero, return `0.00` for all category averages, and render an inline info badge:
     `ℹ️ No historical transactions found in selected window`
   - **Zero-Spend Categories**: Any active category with zero transactions in the selected lookback window defaults its `Historical Monthly Avg` to `0.00` across all currencies.

3. **Base Currency & Multi-Currency Isolation**:
   - Reporting base currency across unified summary calculations is `AUD`.
   - Calculations use stored ledger currency columns directly (`amount_aud`, `amount_hkd`, `amount_usd`). No runtime FX conversions are performed.
   - Target budgets and historical averages are computed independently for `AUD`, `HKD`, and `USD`.

4. **Outlier Suppression & Native Currency Limits**:
   - Outlier threshold ($\text{Threshold}_{\text{Slider}}$) is configurable per session via UI slider ($0.00 to $100,000.00 AUD, default = $1,000.00 AUD). Setting the slider to $0.00 disables suppression entirely.
   - Outlier evaluation applies **ONLY** to records with a populated `amount_aud`. A transaction is flagged as an outlier and excluded from historical averages if:
     $$\text{amount\_aud} \ge \text{Threshold}_{\text{Slider}} \quad (\text{when } \text{Threshold}_{\text{Slider}} > 0.00)$$
   - Transactions in non-AUD currencies lacking stored AUD amounts are exempt from threshold suppression.
   - UI explicit notice: `"Transactions performed in AUD above the set threshold are excluded from projection calculations."`
   - If all transactions in a month for a specific category are suppressed as outliers, treat that category's net spend for that month as $0.00 while preserving global $N_{months}$.

5. **Refunds and Credit Line Items**:
   - Credit transactions (negative numeric values) are included in net monthly sums unless their absolute magnitude ($|\text{amount\_aud}|$) triggers outlier suppression.

---

### 3.2 Target Budget Allocation & Interactive Overrides

1. **Default State & Multi-Currency Row Expansion**:
   - Initial values for `Target Monthly Budget (Currency)` default to the computed `Historical Monthly Avg (Currency)`.
   - **Row Splitting Rule**: If a category contains transactions in multiple currencies (e.g., `Groceries` in AUD and USD), expand into multiple distinct rows labeled `<category> (<CUR>)` (e.g., `Groceries (AUD)`, `Groceries (USD)`).
   - Non-applicable currency columns for a split row MUST be set to `0.00`.
   - Single-currency categories remain as single rows labeled `<category>` with inactive currency columns set to `0.00`.

2. **Inline Data Editor (`st.data_editor`) Integration**:
   - Overrides MUST take place directly inside `st.data_editor`. No separate `st.expander` or override panel is permitted.
   - Only non-total data rows (`base_df`) are passed into `st.data_editor`.
   - **Column Behaviors**:
     - Columns 1–4 (`Category`, `Historical Monthly Avg (AUD)`, `Historical Monthly Avg (HKD)`, `Historical Monthly Avg (USD)`): Read-only (`disabled=True`).
     - Columns 5–7 (`Target Monthly Budget (AUD)`, `Target Monthly Budget (HKD)`, `Target Monthly Budget (USD)`): Editable via `st.column_config.NumberColumn(format="$%.2f", min_value=0.0, step=10.0)`.
   - **Input Validation**: Values must be non-negative real numbers ($\ge 0.00$). If `NaN`, empty, or negative inputs occur, automatically replace with `0.00` in the captured `edited_df` and display inline validation warning: `"Target budget must be >= 0.00"`. Explicit entry of `0.00` is valid.
   - **State Invalidation & Re-initialization**: Whenever the lookback window or outlier slider changes, target budget allocations are reset to match updated historical averages by incrementing the `st.data_editor` key, displaying notification: `"Target budgets re-initialized based on updated historical baselines."`

3. **Summary Aggregation & Read-Only Total Row**:
   - Dynamic real-time totals for projected monthly spend in AUD, HKD, and USD are recalculated upon every cell edit.
   - The total row is appended via `DatabaseRepository.add_total_summary_row(edited_df)` and displayed in a dedicated read-only `st.dataframe` pinned below `st.data_editor`.

---

### 3.3 Google Sheets Transfer Summary & Export Schema

#### 3.3.1 Summary Data Structure & Schema
The exported summary structure contains exactly 7 columns:
1. `Category` (Text)
2. `Historical Monthly Avg (AUD)` (Float64)
3. `Historical Monthly Avg (HKD)` (Float64)
4. `Historical Monthly Avg (USD)` (Float64)
5. `Target Monthly Budget (AUD)` (Float64)
6. `Target Monthly Budget (HKD)` (Float64)
7. `Target Monthly Budget (USD)` (Float64)

A final summary row labeled `Total` calculates column sums across all category rows.

#### 3.3.2 Streamlit Rendering & Interoperability
- Rendered via `st.data_editor(hide_index=True, num_rows="fixed")`.
- Top summary metric KPI cards (`Total Projected Monthly Spend AUD/HKD/USD`) update synchronously with inline edits.
- Data values maintain raw float64 precision formatted visually via `st.column_config.NumberColumn(format="$%.2f")`.
- Export triggered via `st.download_button` exporting raw CSV containing edited rows plus the appended `Total` row.

---

## 4. User Stories & Acceptance Criteria (Cucumber Standard Gherkin)

### Story 1: Calculate Category Rolling Baselines & Handle Partial History
**AS A** Personal Expense Tracker user,  
**I WANT TO** select a historical lookback window and outlier threshold,  
**SO THAT** I can inspect multi-currency rolling spend baselines with outlier suppression and partial history handling.

```gherkin
Feature: Historical Category Spend Projection & Rolling Averages

  Background:
    Given the SQLite database is populated with transaction ledger records:
      | transaction_id | date       | category | amount_aud | amount_hkd | amount_usd |
      | TXN-001         | 2023-10-15 | Dining   | 150.00     | 0.00       | 0.00       |
      | TXN-002         | 2023-10-20 | Dining   | 1200.00    | 0.00       | 0.00       |
      | TXN-003         | 2023-11-05 | Dining   | 200.00     | 0.00       | 0.00       |
      | TXN-004         | 2023-11-12 | Software | 0.00       | 0.00       | 50.00      |
      | TXN-005         | 2023-11-18 | Travel   | -50.00     | 0.00       | 0.00       |

  Scenario Outline: Baseline calculation with varying lookback windows and outlier thresholds
    When the user selects a lookback window of "<lookback_window>"
    And sets the outlier suppression threshold slider to <threshold_val>
    Then the calculated distinct month denominator N_months should be <expected_n_months>
    And the baseline calculation for "<category_label>" should match:
      | Hist_Avg_AUD   | Hist_Avg_HKD   | Hist_Avg_USD   |
      | <hist_aud>     | <hist_hkd>     | <hist_usd>     |
    And the UI should display the indicator message "<ui_badge>"

    Examples:
      | lookback_window    | threshold_val | expected_n_months | category_label | hist_aud | hist_hkd | hist_usd | ui_badge                                                  |
      | Trailing 3 Months  | 1000.00       | 2                 | Dining         | 175.00   | 0.00     | 0.00     | ⚠️ Partial history: Calculation based on 2 distinct month(s) |
      | Trailing 3 Months  | 0.00          | 2                 | Dining         | 775.00   | 0.00     | 0.00     | ⚠️ Partial history: Calculation based on 2 distinct month(s) |
      | Trailing 6 Months  | 1000.00       | 2                 | Software       | 0.00     | 0.00     | 25.00    | ⚠️ Partial history: Calculation based on 2 distinct month(s) |
      | Trailing 12 Months | 500.00        | 2                 | Travel         | -25.00   | 0.00     | 0.00     | ⚠️ Partial history: Calculation based on 2 distinct month(s) |

  Scenario: Zero transaction history within lookback window
    Given no transactions exist in the database for the past 12 months
    When the user selects a lookback window of "Trailing 12 Months"
    Then the global distinct month denominator N_months should default to 1
    And all category historical monthly averages should return 0.00
    And the UI should display an informational badge "ℹ️ No historical transactions found in selected window"

  Scenario: Non-AUD transactions exempt from outlier suppression
    Given a transaction ledger entry for "Shopping" with amount_aud=0.00, amount_hkd=15000.00, amount_usd=0.00
    When the outlier threshold slider is set to 1000.00 AUD
    Then the transaction should not be suppressed as an outlier
    And the Historical Monthly Avg (HKD) for "Shopping" should reflect the full 15000.00 amount
```

---

### Story 2: Inline Target Budget Overrides & Real-Time Sync
**AS A** Personal Expense Tracker user,  
**I WANT TO** edit target budget values directly inline within the projection summary table,  
**SO THAT** category targets, total projections, and KPI cards update dynamically without separate forms.

```gherkin
Feature: Inline Target Budget Editing & Validation

  Background:
    Given the projection summary table is rendered in st.data_editor with initial baselines:
      | Category        | Hist_Avg_AUD | Hist_Avg_HKD | Hist_Avg_USD | Target_AUD | Target_HKD | Target_USD |
      | Groceries (AUD) | 400.00       | 0.00         | 0.00         | 400.00     | 0.00       | 0.00       |
      | Utility (HKD)   | 0.00         | 1200.00      | 0.00         | 0.00       | 1200.00    | 0.00       |

  Scenario Outline: Dynamic real-time calculation on valid inline target modification
    When the user edits row "<row_category>" field "<target_column>" to value <input_val>
    Then the table target value for "<target_column>" on "<row_category>" becomes <expected_target>
    And the pinned read-only Total summary row reflects:
      | Total_Target_AUD   | Total_Target_HKD   | Total_Target_USD   |
      | <total_aud>        | <total_hkd>        | <total_usd>        |
    And top KPI summary cards show AUD=<total_aud>, HKD=<total_hkd>, USD=<total_usd>

    Examples:
      | row_category    | target_column             | input_val | expected_target | total_aud | total_hkd | total_usd |
      | Groceries (AUD) | Target Monthly Budget (AUD)| 550.00    | 550.00          | 550.00    | 1200.00   | 0.00      |
      | Groceries (AUD) | Target Monthly Budget (AUD)| 0.00      | 0.00            | 0.00      | 1200.00   | 0.00      |
      | Utility (HKD)   | Target Monthly Budget (HKD)| 1500.00   | 1500.00         | 400.00    | 1500.00   | 0.00      |

  Scenario Outline: Validation for invalid target inputs
    When the user enters invalid value "<invalid_input>" into "Target Monthly Budget (AUD)" for "Groceries (AUD)"
    Then the input should be converted to 0.00 in the edited dataframe
    And an inline validation warning "Target budget must be >= 0.00" should be displayed

    Examples:
      | invalid_input |
      | -150.00       |
      | NaN           |
      | -0.01         |

  Scenario: Target reset on lookback window or threshold change
    Given modified target budget values exist in session state
    When the user changes the lookback window or outlier threshold slider
    Then target budgets re-initialize to match newly calculated historical monthly averages
    And an inline notification "Target budgets re-initialized based on updated historical baselines." is displayed
```

---

### Story 3: CSV Export Interoperability
**AS A** Personal Expense Tracker user,  
**I WANT TO** export the projection table including category target overrides and the Total row to CSV,  
**SO THAT** I can transfer budget data directly to external spreadsheets.

```gherkin
Feature: Export Budget Projection Summary

  Scenario: Exporting valid budget projection dataframe to CSV
    Given the following active budget projection summary state:
      | Category       | Hist_Avg_AUD | Hist_Avg_HKD | Hist_Avg_USD | Target_AUD | Target_HKD | Target_USD |
      | Dining         | 250.00       | 0.00         | 0.00         | 300.00     | 0.00       | 0.00       |
      | Cloud Hosting  | 0.00         | 0.00         | 45.00        | 0.00       | 0.00       | 50.00      |
    And the total summary row is computed as:
      | Category | Hist_Avg_AUD | Hist_Avg_HKD | Hist_Avg_USD | Target_AUD | Target_HKD | Target_USD |
      | Total    | 250.00       | 0.00         | 45.00        | 300.00     | 0.00       | 50.00      |
    When the user clicks the "Download Projection CSV" button
    Then a CSV file is generated with 7 columns in exact sequence:
      """
      Category,Historical Monthly Avg (AUD),Historical Monthly Avg (HKD),Historical Monthly Avg (USD),Target Monthly Budget (AUD),Target Monthly Budget (HKD),Target Monthly Budget (USD)
      """
    And the exported CSV contains unformatted Float64 raw numbers
    And the final row of the CSV is the exact "Total" aggregation row
```