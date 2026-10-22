# Feature Specification: HK Card Budget Projection Engine

## 1. Module Overview & Primary Intent
The Budget Projection Engine provides a forward-looking planning view inside the Personal Expense Tracker application. It utilizes historical HKD statement transaction averages to establish a configurable baseline, allowing the user to set future category targets, adjust for one-off/irregular spend, and generate a clean copy-pasteable summary formatted for external budget tracking (Google Sheets).

## 2. Module Boundaries & Ownership Contracts
- **Primary Source Files**: `src/app.py` (Presentation & Interactive Target Controls), `src/repository.py` (Historical Aggregations & Target Calculations).
- **Allowed Dependencies**: `pandas`, `sqlite3`, `streamlit`, `DatabaseRepository`.
- **Forbidden Operations**: Presentation layer must not write raw SQL queries directly or modify baseline transaction records during projection adjustments.

## 3. Detailed Technical Requirements & Business Rules

### 3.1 Historical Baseline & Rolling Averages
1. **Window Selection**: The user can select a historical lookback window (Trailing 3 Months, Trailing 6 Months, or Trailing 12 Months) to compute the baseline monthly spend per category.
2. **Partial Lookback Window Handling**: 
   - If active statement history spans fewer distinct months than the selected lookback window (e.g., only 3 months of data exist for a 12-month selection), compute monthly category averages using the actual number of distinct months available and render an inline warning badge in the UI.
   - Distinct months are defined as `YYYY-MM` calendar periods containing at least one non-outlier transaction
3. **Outlier Suppression**:
   - The outlier exclusion threshold is configurable, defaulting to $1,000.00 AUD, and can be disabled, is evaluated against individual transaction line items prior to monthly category aggregation.
   - Any transaction line item $\ge \text{Threshold}_{\text{Outlier}}$ is excluded from historical average calculations to prevent skewed projections.
4. **Base Currency & FX Handling**:
   - The primary reporting currency across all ledger views is AUD.
   - Ingested HK Card transactions already contain stored HKD amounts and pre-converted AUD amounts calculated at the bank statement ingestion rate.
   - Historical baseline aggregations evaluate these stored AUD transaction amounts directly and do not perform dynamic runtime FX conversions.
   - The number of expected HKD transactions per month are less than 5, as indicated by the `transaction.purchase_currency_id` field with a value of `16`. This has been the pattern for the last 15 months. 
   - Typically there are two transactions, that belong to the `DCC FEE-NON-HK MERCHANT` merchant, `transaction.merchant_id` value of 27, which is a bank fee from my HK credit card and a merchant containing the label `Netflix.com`, `transaction.merchant_id` of 26 or 173, which is for my Netflix subscription. 
   - Because of this, I suggest creating two projections the primary one in AUD and one for HKD transactions, thus not needing any currency conversions

### 3.2 Target Budget Allocation & Interactive Overrides
1. **Default State**: Upon initial render or window change, "Target Monthly Budget (AUD)" per category defaults to its computed historical monthly average.
2. **User Adjustment**: The user can edit individual category target budget figures directly in the UI. Inputs must be non-negative real numbers; negative values trigger an inline validation error and fall back to 0.00.
3. **Summary Aggregation & FX Projections**:
   - The system calculates live totals for Total Projected Monthly Spend (AUD) and Total Projected Monthly Spend (HKD equivalent).
   - Future target totals in HKD equivalent are computed using the most recent exchange rate stored in `DatabaseRepository`:
     $$\text{Target HKD} = \text{Target AUD} \times \text{Latest FX Rate}_{\text{AUD}\rightarrow\text{HKD}}$$

### 3.3 Google Sheets Transfer Summary
### 3.3 Google Sheets Transfer Summary & Export Formats

#### 3.3.1 Data Export Structure
The system presents the budget summary in a tabular layout structured with the following exact column schema:
- `Category`: The expense category name.
- `Historical Monthly Avg (AUD)`: Computed historical baseline average in AUD (2 decimal places).
- `Target Monthly Budget (AUD)`: Active user-configured monthly target in AUD (2 decimal places).
- `Target Monthly Budget (HKD)`: Converted target monthly budget in HKD equivalent (2 decimal places).

A summary row labeled `Total` must be appended at the bottom of the dataset aggregating the sums across all active categories for each monetary column.

#### 3.3.2 Streamlit Dataframe Interactive Export & Display
1. **Interactive Dataframe Container**: The summary table is rendered using Streamlit's native dataframe presentation component (`st.dataframe`).
2. **Native Export & Utilities**: Presentation layer configuration leverages built-in Streamlit dataframe capabilities, providing users with:
   - One-click **Export to CSV** action for seamless import into Google Sheets, Microsoft Excel, or external financial planning tools.
   - Interactive column sorting, search/filtering, and full-screen view controls out of the box.
3. **Number Formatting**: All numeric monetary figures within the dataframe display formatted to 2 decimal places with standard comma separators (e.g., `1,250.50`).

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
**I WANT TO** override historical averages with custom budget targets,  
**SO THAT** I can plan my upcoming monthly salary allocation.

#### Acceptance Criteria (Gherkin):
**Scenario 1: User overrides category budget**
- **GIVEN** calculated baseline averages for a selected expense category
- **WHEN** the user changes the target budget input
- **THEN** recalculate total projected monthly AUD and HKD budget sums