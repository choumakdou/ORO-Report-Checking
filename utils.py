"""utils.py — Number-to-words, spell-out verification, date helpers."""
import re
from typing import Optional

# ─────────────────────────────────────────────
# Number → English words (HK legal convention)
# ─────────────────────────────────────────────
_ONES = [
    "", "ONE", "TWO", "THREE", "FOUR", "FIVE", "SIX", "SEVEN",
    "EIGHT", "NINE", "TEN", "ELEVEN", "TWELVE", "THIRTEEN",
    "FOURTEEN", "FIFTEEN", "SIXTEEN", "SEVENTEEN", "EIGHTEEN", "NINETEEN",
]
_TENS = [
    "", "", "TWENTY", "THIRTY", "FORTY", "FIFTY",
    "SIXTY", "SEVENTY", "EIGHTY", "NINETY",
]


def _below_1000(n: int) -> str:
    """
    Convert integer 0–999 to words.
    HK legal convention: NO 'AND' between hundreds and tens.
    e.g. 820 → 'EIGHT HUNDRED TWENTY' (NOT 'EIGHT HUNDRED AND TWENTY')
    """
    if n == 0:
        return ""
    if n < 20:
        return _ONES[n]
    if n < 100:
        t = _TENS[n // 10]
        o = _ONES[n % 10]
        return t + ("-" + o if o else "")
    h = _ONES[n // 100] + " HUNDRED"
    rem = n % 100
    if rem == 0:
        return h
    # No AND here — HK legal doc style omits AND within hundreds
    return h + " " + _below_1000(rem)


def number_to_words(n: int) -> str:
    """
    Convert a non-negative integer to HK legal-document word form.
    Rules:
      - No AND within a three-digit group (hundreds + tens)
      - AND before thousands if higher group present AND thousands_value < 100
      - AND before units (< 1000) if any higher group is present
    Examples:
        5820000  → 'FIVE MILLION EIGHT HUNDRED TWENTY THOUSAND'
        2037000  → 'TWO MILLION AND THIRTY-SEVEN THOUSAND'
        4800000  → 'FOUR MILLION EIGHT HUNDRED THOUSAND'
        1440000  → 'ONE MILLION FOUR HUNDRED FORTY THOUSAND'
        1757300  → 'ONE MILLION SEVEN HUNDRED FIFTY-SEVEN THOUSAND AND THREE HUNDRED'
        958200   → 'NINE HUNDRED FIFTY-EIGHT THOUSAND AND TWO HUNDRED'
    """
    if n == 0:
        return "ZERO"

    result_parts = []  # list of string segments

    billions = n // 1_000_000_000
    n %= 1_000_000_000
    if billions:
        result_parts.append(_below_1000(billions) + " BILLION")

    millions = n // 1_000_000
    n %= 1_000_000
    if millions:
        result_parts.append(_below_1000(millions) + " MILLION")

    thousands = n // 1_000
    n %= 1_000
    if thousands:
        # AND before thousands only when higher groups exist AND thousands < 100
        prefix = "AND " if (result_parts and thousands < 100) else ""
        result_parts.append(prefix + _below_1000(thousands) + " THOUSAND")

    if n:
        # AND before units whenever a higher group exists
        prefix = "AND " if result_parts else ""
        result_parts.append(prefix + _below_1000(n))

    return " ".join(result_parts)


def spellout_matches(amount: int, spellout: str) -> bool:
    """
    Check whether a numeric amount matches a given spell-out string.
    Normalises whitespace, hyphens, AND usage before comparing.
    """
    expected = number_to_words(amount)
    # normalise the candidate
    candidate = spellout.upper()
    candidate = re.sub(r"HONG KONG DOLLARS?\s*", "", candidate)
    candidate = re.sub(r"\s*ONLY\s*$", "", candidate).strip()
    candidate = re.sub(r"\s+", " ", candidate)
    candidate = candidate.replace(" - ", "-")
    # normalise expected similarly
    expected_norm = re.sub(r"\s+", " ", expected).strip()
    return candidate == expected_norm


def parse_hk_amount(text: str) -> Optional[int]:
    """Extract first HK$ amount from a string, returning integer cents."""
    m = re.search(r"HK\$?([\d,]+)", text.replace(" ", ""))
    if m:
        try:
            return int(m.group(1).replace(",", ""))
        except ValueError:
            pass
    return None


# ─────────────────────────────────────────────
# Saleable area conversion
# ─────────────────────────────────────────────
SQM_TO_SQFT = 10.764


def sqm_to_sqft(sqm: float) -> int:
    return round(sqm * SQM_TO_SQFT)


# ─────────────────────────────────────────────
# Date helpers
# ─────────────────────────────────────────────
MONTH_MAP = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4,
    "jun": 6, "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def parse_date_to_ymd(date_str: str) -> Optional[tuple]:
    """
    Parse a date string like '14 October 2003', '09/07/1999', '1999-02-23'
    Returns (year, month, day) tuple of ints or None.
    """
    if not date_str:
        return None
    s = date_str.strip()

    # DD/MM/YYYY or DD-MM-YYYY
    m = re.match(r"(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})", s)
    if m:
        return (int(m.group(3)), int(m.group(2)), int(m.group(1)))

    # YYYY-MM-DD
    m = re.match(r"(\d{4})[/\-](\d{1,2})[/\-](\d{1,2})", s)
    if m:
        return (int(m.group(1)), int(m.group(2)), int(m.group(3)))

    # DD Month YYYY  e.g. "14 October 2003"
    m = re.match(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", s)
    if m:
        month_name = m.group(2).lower()
        month_num = MONTH_MAP.get(month_name)
        if month_num:
            return (int(m.group(3)), month_num, int(m.group(1)))

    # Month YYYY (year only needed sometimes)
    m = re.match(r"([A-Za-z]+)\s+(\d{4})", s)
    if m:
        month_name = m.group(1).lower()
        month_num = MONTH_MAP.get(month_name)
        if month_num:
            return (int(m.group(2)), month_num, 0)

    return None


def extract_year(date_str: str) -> Optional[int]:
    ymd = parse_date_to_ymd(date_str)
    if ymd:
        return ymd[0]
    # fallback: grab 4-digit year
    m = re.search(r"\b(\d{4})\b", date_str)
    if m:
        return int(m.group(1))
    return None


# ─────────────────────────────────────────────
# Name normalisation for fuzzy comparison
# ─────────────────────────────────────────────
def normalise_name(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip().upper())


def names_match(a: str, b: str) -> bool:
    """Case-insensitive name comparison, ignoring extra whitespace."""
    return normalise_name(a) == normalise_name(b)
