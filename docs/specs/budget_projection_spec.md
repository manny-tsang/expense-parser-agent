# Feature Specification: HK Card Budget Projection Engine

## 1. Module Overview & Primary Intent
- **Epic Title**: HK Card Budget Projection Engine
- **Epic Description**: As a Personal Expense Tracker user, I want a forward-looking budget planning engine to compute rolling spend baselines across multi-currency accounts (AUD, HKD, USD), suppress transaction outliers, set target category allocations, and export summaries to external spreadsheets.

## 2. Module Boundaries & Ownership Contracts
- **Primary Source Files**: `src/app.py` (Presentation & Interactive Target Controls), `src/repository.py` (Historical Aggregations & Target Calculations).
- **Allowed Dependencies**: `pandas`, `sqlite3`, `streamlit`, `DatabaseRepository`.
- **Forbidden Operations**: Presentation layer must not write raw SQL queries directly or modify baseline transaction records during projection adjustments.

## 3. Detailed Technical Requirements & Business Rules

### 3.1 Historical Baseline & Rolling Averages
1. **Window Selection**: The user can select a historical lookback window (Trailing 3 Months, Trailing 6 Months, or Trailing 12 Months) to compute the baseline monthly spend per category.
2. **Partial Lookback Window & Global Distinct Month Handling**: 
   - A **Distinct Month** is defined as a unique `YYYY-MM` calendar period containing at least one valid, non-outlier transaction anywhere in the database ledger.
   - The distinct month count denominator ($N_{months}$) is calculated globally across the entire database for the selected lookback window.
   - If $N_{months}$ is less than the requested window length (e.g., only 2 distinct months exist for a 3-month lookback), compute monthly averages using $N_{months}$ as the denominator and render an inline warning badge in the UI: `⚠️ Partial history: Calculation based on N distinct month(s)`.
   - If $N_{months} = 0$, default $N_{months}$ to 1 for calculation purposes, return `0.00` for all category averages, and display an inline informational badge: `ℹ️ No historical transactions found in selected window`.
   - Categories with zero transactions in the lookback window default their `Historical Monthly Avg` to `0.00` across all currencies.
3. **Base Currency & Multi-Currency Isolation**:
   - The primary reporting currency across all ledger views is AUD.
   - Historical baseline aggregations evaluate stored AUD transaction amounts directly and do not perform dynamic runtime FX conversions.
   - Historical baseline averages and target budgets are computed independently for each currency code (`AUD`, `HKD`, `USD`) without cross-currency blending.
4. **Outlier Suppression & Native Currency Limits**:
   - The outlier exclusion threshold is transient, configurable per session via a UI slider ($0.00 to $100,000.00 AUD, defaulting to $1,000.00 AUD). Setting the slider to $0.00 disables outlier suppression entirely.
   - The suppression applies ONLY to transactions that have an AUD amount.
   - Transactions performed in currencies other than AUD, that do not have an AUD amount already, ARE NOT to be converted into AUD to determine if they exceed the suppression threshold.  
   - These non-AUD transactions, if they were to be converted (again, we ARE NOT converting them), typically would not exceed the equivalent of $100 AUD, so naturally would never be suppressed and therefore should always be factored into the respective currencies computation / calculation.
   - A transaction line item is excluded from historical average calculations if its stored AUD amount is $\ge \text{Threshold}_{\text{Slider}}$,
   - The UI MUST display an explicit note: `"Transactions performed in AUD above the set threshold are excluded from projection calculations."`
   - If all transactions in a month for a given category are flagged as outliers, treat that category's monthly spend as $0.00 while maintaining the global $N_{months}$ denominator.
5. **Refunds and Credit Line Items**:
   - Negative transactions (credits/refunds) are included in the category net sum for a given month unless their absolute magnitude triggers the outlier threshold rule.

### 3.2 Target Budget Allocation & Interactive Overrides
1. **Default State**: 
   - Upon initial render or window change, `Target Monthly Budget (Currency)` fields for AUD, HKD, and USD default to their respective computed `Historical Monthly Avg (Currency)` values.
   - Where a category has transactions performed in more than one currency, then this category should have multiple lines. For example, if "Groceries" has transactions in AUD, HKD and USD, then "Groceries" will have 3 rows. Each row will be labelled as `<category> (Currency)` (e.g. `<Groceries> (AUD)`) showing `Target Monthly Budget (Currency)` and `Historical Monthly Avg (Currency)` for the respective currency, and the other columns for the other currencies are set to `0.00`.
   - Inversely, to be perfectly clear, if transactions for a specific category are all in a single currency, then there should only be one row for that category and the totals for columns that are not of that currency, should be set to `0.00`.
2. **Inline Table Target Adjustments (`st.data_editor`)**:
   - Eliminate any separate "Overrides" section or `st.expander` widget; all target budget edits MUST occur directly inline within the **Budget Projection Summary** table (`st.data_editor`).
   - Pass ONLY the active category rows (`base_df`, excluding the `Total` row) into `st.data_editor`, and capture its returned DataFrame (`edited_df`) directly to compute live totals.
   - Columns 1–4 (`Category` and `Historical Monthly Avg (AUD/HKD/USD)`) MUST be configured as read-only (`disabled=True`).
   - Columns 5–7 (`Target Monthly Budget (AUD)`, `Target Monthly Budget (HKD)`, `Target Monthly Budget (USD)`) MUST be editable inline via `st.column_config.NumberColumn(format="$%.2f", min_value=0.0, step=10.0)`.
   - Render the dynamically calculated `Total` summary row as a separate, read-only 1-row `st.dataframe` pinned directly beneath `st.data_editor` so users cannot edit the `Total` row while both the `Total` row and top KPI cards update instantaneously upon any cell edit.
   - Inputs must be non-negative real numbers. If a user enters a negative value or `NaN`/empty cell, replace `NaN`/negative values in `edited_df` with `0.00` and display an inline validation error (`"Target budget must be >= 0.00"`).
   - Explicit input of `0.00` is valid and indicates an intentional phase-out for that category target.
   - Automatically reset all `Target Monthly Budget` values to match the newly computed `Historical Monthly Avg` baselines whenever the Lookback Window or Outlier Threshold slider is modified (by incrementing the `st.data_editor` widget key), displaying an inline session notification informing the user that targets were re-initialized.
3. **Summary Aggregation**:
   - The system calculates independent live totals for Total Projected Monthly Spend (AUD), Total Projected Monthly Spend (HKD), and Total Projected Monthly Spend (USD).

### 3.3 Google Sheets Transfer Summary & Export Formats

#### 3.3.1 Summary Data Structure & Schema
- The summary data table follows an exact sequence of 7 columns:
   1. `Category` (Text)
   2. `Historical Monthly Avg (AUD)` (Float64)
   3. `Historical Monthly Avg (HKD)` (Float64)
   4. `Historical Monthly Avg (USD)` (Float64)
   5. `Target Monthly Budget (AUD)` (Float64)
   6. `Target Monthly Budget (HKD)` (Float64)
   7. `Target Monthly Budget (USD)` (Float64)
- A summary row labeled `Total` must be appended at the bottom, calculating the sum of each numeric column across all active categories and is read-only.
- Maintain the exact `Category` label as displayed on the UI when exporting to CSV.
- Include the `Total` row when exporting the table to CSV.

### 3.3.2 Streamlit Rendering & Export Options
1. **Component**: Active category rows are rendered via `st.data_editor` (with `hide_index=True`, `num_rows="fixed"`), disabling editing on `Category` and all `Historical Monthly Avg` columns while enabling inline numeric cell editing on `Target Monthly Budget (AUD)`, `Target Monthly Budget (HKD)`, and `Target Monthly Budget (USD)`.
2. **Locked Total Row & Real-Time KPI Sync**: Compute `summary_df = DatabaseRepository.add_total_summary_row(edited_df)` from the DataFrame returned by `st.data_editor`. Render the `Total` row in a locked read-only `st.dataframe` immediately below the editor and update the three top KPI summary cards (`Total Projected Monthly Spend (AUD/HKD/USD)`) in real time.
3. **Numeric Types**: Underlying pandas DataFrame columns maintain native `float64` numeric types to 2 decimal places to ensure raw CSV exports contain unformatted floats.
4. **Visual Column Configuration**: UI rendering uses `st.column_config.NumberColumn(format="$%.2f")` (and `min_value=0.0` enforced on Target columns).
5. **Export Interoperability**: Utilizes native Streamlit CSV download (`st.download_button`) exporting `summary_df` (containing all live edited category rows plus the updated `Total` row) with exact column headers.

## 4. User Stories & BDD Acceptance Criteria

### Story 1: Calculate Category Baseline Averages
**AS A** personal expense tracker user,  
**I WANT TO** select a historical lookback window,  
**SO THAT** I can see realistic baseline monthly averages per category.

#### Acceptance Criteria (Gherkin):
**Scenario 1: Successfully calculating trailing averages**
- **GIVEN** ingested transaction history for the selected lookback window
- **WHEN** the user selects a pre-defined timeframe
- **THEN** compute monthly spend averages per active category excluding outlier transactions

### Story 2: Interactive Target Adjustments
**AS A** personal expense tracker user,  
**I WANT TO** edit target budget cells directly inline within the Budget Projection Summary table,  
**SO THAT** I can plan my upcoming monthly salary allocation and see totals update in real time without a separate overrides section.

#### Acceptance Criteria (Gherkin):
**Scenario 1: User edits category target inline in Budget Projection Summary**
- **GIVEN** calculated baseline averages rendered in the Budget Projection Summary table (`st.data_editor`) with no separate "Overrides" expander
- **WHEN** the user edits a Target Monthly Budget cell directly inline within the summary table
- **THEN** validate that the input is non-negative ($\ge 0.00$) and recalculate the read-only `Total` row and top KPI summary cards in real time