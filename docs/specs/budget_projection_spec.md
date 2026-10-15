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
2. **Outlier Suppression**: Transactions flagged above the configurable outlier threshold (e.g., $1,000 AUD default) should be excluded from historical average calculations to prevent skewed projections.
3. **FX Conversion**: Historical foreign transactions are evaluated in AUD using stored exchange rates.

### 3.2 Target Budget Allocation & Interactive Overrides
1. **Default State**: Upon load, the "Target Monthly Budget" per category defaults to its computed historical monthly average.
2. **User Adjustment**: The user can edit individual category target budget figures directly in the UI.
3. **Summary Aggregation**: The system calculates live totals for:
   - Total Projected Monthly Spend (AUD)
   - Total Projected Monthly Spend (HKD equivalent)

### 3.3 Google Sheets Transfer Summary
1. **Export Card**: Displays a formatted markdown table or plain-text clipboard buffer structured as:
   `Category | Historical Monthly Avg (AUD) | Target Monthly Budget (AUD) | Target Monthly Budget (HKD)`
2. **One-Click Copy**: Provides a UI trigger to copy formatted rows directly for pasting into external budget spreadsheets.

## 4. User Stories & BDD Acceptance Criteria

### Story 1: Calculate Category Baseline Averages
**As a** user,  
**I want to** select a historical lookback window,  
**So that** I can see realistic baseline monthly averages per category.

#### Acceptance Criteria (Gherkin):
**Scenario: Successfully calculating trailing averages**
- **GIVEN** ingested transaction history for the selected lookback window
- **WHEN** the user selects "Trailing 6 Months"
- **THEN** compute monthly spend averages per active category excluding outlier transactions

### Story 2: Interactive Target Adjustments
**As a** user,  
**I want to** override historical averages with custom budget targets,  
**So that** I can plan my upcoming monthly salary allocation.

#### Acceptance Criteria (Gherkin):
**Scenario: User overrides category budget**
- **GIVEN** calculated baseline averages for 'Dining & Cafes'
- **WHEN** the user changes the target budget input
- **THEN** recalculate total projected monthly AUD and HKD budget sums