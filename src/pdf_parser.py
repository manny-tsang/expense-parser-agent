import logging
import re
from typing import Any, Dict, List, Optional
import pandas as pd
import pdfplumber

logger = logging.getLogger(__name__)


class HKCreditCardParser:
    """Parser for HK Credit Card PDF Statements."""

    # Anchors and Exclusion Rules
    PAGE1_START_PATTERN = re.compile(
        r"(Post\s*date|Trans\s*date|Description\s*of\s*transaction)",
        re.IGNORECASE,
    )
    PAGE1_STOP_PATTERN = re.compile(
        r"(MINIMUM\s+PAYMENT\s+SUMMARY|SUMMARY\s*戶口概要)", re.IGNORECASE
    )
    EXCLUSION_PATTERN = re.compile(
        r"(PREVIOUS\s+BALANCE|上月結欠/結餘)", re.IGNORECASE
    )
    GLOBAL_STOP_PATTERN = re.compile(
        r"\*?\s*FOR\s+CREDIT\s+CARD\s+TRANSACTIONS\s+EFFECTED\s+IN\s+CURRENCIES\s+OTHER\s+THAN\s+HONG\s+KONG\s+DOLLARS",
        re.IGNORECASE,
    )

    # Line Item Patterns
    TRANS_START_PATTERN = re.compile(r"^(\d{2}[A-Z]{3})\s+(\d{2}[A-Z]{3})\s+(.+)$")
    TWO_AMOUNTS_PATTERN = re.compile(
        r"^(.*?)\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})$"
    )
    ONE_AMOUNT_PATTERN = re.compile(r"^(.*?)\s+([\d,]+\.\d{2})$")

    # Multi-Line Metadata Patterns
    APPLE_PAY_PATTERN = re.compile(r"APPLE\s*PAY-MOBILE:\s*\S+", re.IGNORECASE)
    FX_RATE_PATTERN = re.compile(r"\*?\s*EXCHANGE\s+RATE:\s*([\d\.]+)", re.IGNORECASE)

    # Cleaning Patterns
    COUNTRY_CODE_PATTERN = re.compile(r"\s+[A-Z]{2}$")

    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.transactions: List[Dict[str, Any]] = []

    def _flush_transaction(self, current_trans: Optional[Dict[str, Any]]) -> None:
        """Clean merchant description and append finalized transaction."""
        if not current_trans:
            return

        merchant = current_trans["merchant"]
        merchant = self.COUNTRY_CODE_PATTERN.sub("", merchant).strip()
        current_trans["merchant"] = merchant
        self.transactions.append(current_trans)

    def parse() -> pd.DataFrame:
        """Extracts transaction data from PDF according to standard specification rules."""
        columns = [
            "post_date",
            "trans_date",
            "merchant",
            "aud_amount",
            "hkd_amount",
            "fx_rate",
        ]

        current_trans: Optional[Dict[str, Any]] = None
        global_stop = False

        try:
            with pdfplumber.open(self.pdf_path) as pdf:
                for page_num, page in enumerate(pdf.pages, start=1):
                    if global_stop:
                        break

                    # Rule: Skip Page 2 completely
                    if page_num == 2:
                        continue

                    text = page.extract_text()
                    if not text:
                        continue

                    lines = text.split("\n")
                    page_1_started = False

                    for line in lines:
                        line_str = line.strip()
                        if not line_str:
                            continue

                        # Check Global Stop Anchor across all pages
                        if self.GLOBAL_STOP_PATTERN.search(line_str):
                            global_stop = True
                            break

                        # Page 1 Specific Routing Rules
                        if page_num == 1:
                            if not page_1_started:
                                if self.PAGE1_START_PATTERN.search(line_str):
                                    page_1_started = True
                                continue
                            else:
                                if self.PAGE1_STOP_PATTERN.search(line_str):
                                    break  # Stop parsing Page 1

                        # Exclusion Rules
                        if self.EXCLUSION_PATTERN.search(line_str):
                            continue

                        # Check for Start of New Transaction Line (Line 1)
                        trans_match = self.TRANS_START_PATTERN.match(line_str)
                        if trans_match:
                            if current_trans:
                                self._flush_transaction(current_trans)
                                current_trans = None

                            post_date, trans_date, rest = trans_match.groups()
                            aud_amount: Optional[float] = None
                            hkd_amount: float = 0.0
                            merchant: str = rest.strip()

                            two_amt_match = self.TWO_AMOUNTS_PATTERN.match(rest)
                            if two_amt_match:
                                merchant_raw, aud_str, hkd_str = two_amt_match.groups()
                                try:
                                    aud_amount = float(aud_str.replace(",", ""))
                                    hkd_amount = float(hkd_str.replace(",", ""))
                                    merchant = merchant_raw.strip()
                                except ValueError:
                                    pass
                            else:
                                one_amt_match = self.ONE_AMOUNT_PATTERN.match(rest)
                                if one_amt_match:
                                    merchant_raw, hkd_str = one_amt_match.groups()
                                    try:
                                        hkd_amount = float(hkd_str.replace(",", ""))
                                        merchant = merchant_raw.strip()
                                    except ValueError:
                                        pass

                            current_trans = {
                                "post_date": post_date,
                                "trans_date": trans_date,
                                "merchant": merchant,
                                "aud_amount": aud_amount,
                                "hkd_amount": hkd_amount,
                                "fx_rate": None,
                            }
                            continue

                        # Handle Multi-Line Details for Pending Transaction
                        if current_trans:
                            # Line 2: Payment Metadata Token (To Be Discarded)
                            if self.APPLE_PAY_PATTERN.search(line_str):
                                continue

                            # Line 3: Capture Exchange Rate
                            fx_match = self.FX_RATE_PATTERN.search(line_str)
                            if fx_match:
                                try:
                                    current_trans["fx_rate"] = float(fx_match.group(1))
                                except ValueError:
                                    pass
                                continue

                # Flush final transaction buffer upon completion
                if current_trans:
                    self._flush_transaction(current_trans)

        except Exception as e:
            logger.error(f"Error reading PDF statement {self.pdf_path}: {e}")
            return pd.DataFrame(columns=columns)

        if not self.transactions:
            return pd.DataFrame(columns=columns)

        df = pd.DataFrame(self.transactions)
        return df[columns]


def parse_statement(
    pdf_path: str, output_csv_path: Optional[str] = None
) -> pd.DataFrame:
    """
    Parses an HK Credit Card PDF statement, cleans transactions, and exports to CSV if requested.

    Args:
        pdf_path: Local filesystem path to the target PDF statement.
        output_csv_path: Optional destination path to save the output CSV.

    Returns:
        DataFrame containing structured and anonymized transaction details.
    """
    parser = HKCreditCardParser(pdf_path)
    df = parser.parse()

    if output_csv_path:
        try:
            df.to_csv(output_csv_path, index=False)
            logger.info(f"Successfully saved transactions to {output_csv_path}")
        except Exception as e:
            logger.error(f"Failed to write output CSV file {output_csv_path}: {e}")

    return df