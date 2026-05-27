"""doc_classifier.py — Auto-classify PDFs in a folder as supporting docs or report drafts."""
import os
import re
from typing import Optional
import pdf_parser

# ── Keywords that signal a file is a CHFT valuation report (to be excluded) ──
_REPORT_TITLE_PHRASES = [
    "valuation report",
    "chft advisory and appraisal",
    "official receiver's office | page",
    "v/sch/",          # CHFT reference pattern
]
_REPORT_FILENAME_PATTERNS = [
    r"valreport",
    r"val[\s_\-]?report",
    r"valuation[\s_\-]report",
]

# ── Keywords to classify SUPPORTING document types ──
_DOC_TYPE_SIGNALS = {
    "land_register": [
        "land registry", "land register", "土 地 註 冊 處", "土地登記冊",
        "incumbrances", "memorial no", "share of the lot",
    ],
    "rvd": [
        "rating and valuation department", "property information online",
        "差餉物業估價署", "物業資訊網", "saleable area", "completion certificate issued on",
        "assessment no", "673-",
    ],
    "assignment": [
        "hong kong housing authority", "the vendor", "the purchaser",
        "assignment", "deed of mutual covenant", "schedule to the housing ordinance",
        "initial market value",
    ],
    "instruction_letter": [
        "official receiver's office", "official receiver & trustee",
        "i hereby appoint you", "bankruptcy no", "破廢管理署",
        "furnish me with the valuation report",
    ],
}


def _first_pages_text(pdf_path: str, pages: int = 3) -> str:
    """Extract and concatenate text from the first N pages of a PDF."""
    page_data = pdf_parser.extract_text_by_page(pdf_path)
    combined = " ".join(text for _, text in page_data[:pages])
    return combined.lower()


def is_report_draft(pdf_path: str, selected_report_path: str) -> bool:
    """
    Return True if this PDF should be excluded (is a valuation report draft/version).
    Checks:
      1. Exact same path as the selected report
      2. Filename matches known report naming patterns
      3. PDF content contains CHFT report title phrases
    """
    # 1. Exact match
    if os.path.abspath(pdf_path) == os.path.abspath(selected_report_path):
        return True

    filename = os.path.basename(pdf_path).lower()

    # 2. Filename heuristic
    for pattern in _REPORT_FILENAME_PATTERNS:
        if re.search(pattern, filename, re.IGNORECASE):
            return True

    # 3. Content check (first 3 pages)
    try:
        text = _first_pages_text(pdf_path, pages=3)
        hits = sum(1 for phrase in _REPORT_TITLE_PHRASES if phrase in text)
        if hits >= 2:           # needs at least 2 signals to be sure
            return True
    except Exception:
        pass

    return False


def classify_doc_type(pdf_path: str) -> str:
    """
    Classify a supporting PDF into one of:
      'land_register', 'rvd', 'assignment', 'instruction_letter', 'unknown'
    """
    try:
        text = _first_pages_text(pdf_path, pages=4)
    except Exception:
        return "unknown"

    scores: dict = {k: 0 for k in _DOC_TYPE_SIGNALS}
    for doc_type, signals in _DOC_TYPE_SIGNALS.items():
        for signal in signals:
            if signal.lower() in text:
                scores[doc_type] += 1

    best = max(scores, key=lambda k: scores[k])
    return best if scores[best] >= 2 else "unknown"


def scan_folder(folder_path: str, selected_report_path: str) -> dict:
    """
    Scan a folder and return a dict:
    {
        'supporting': {
            'land_register': path_or_None,
            'rvd':           path_or_None,
            'assignment':    path_or_None,
            'instruction_letter': path_or_None,
            'unknown':       [list of unclassified paths],
        },
        'excluded_reports': [list of excluded paths],
    }
    Only the first match per doc_type is kept (most recently modified wins).
    """
    if not folder_path or not os.path.isdir(folder_path):
        return {"supporting": {}, "excluded_reports": []}

    pdf_files = sorted(
        [os.path.join(folder_path, f) for f in os.listdir(folder_path)
         if f.lower().endswith(".pdf")],
        key=os.path.getmtime,
        reverse=True,   # newest first → first match wins
    )

    excluded: list = []
    classified: dict = {
        "land_register": None,
        "rvd": None,
        "assignment": None,
        "instruction_letter": None,
        "unknown": [],
    }

    for path in pdf_files:
        if is_report_draft(path, selected_report_path):
            excluded.append(path)
            continue
        doc_type = classify_doc_type(path)
        if doc_type == "unknown":
            classified["unknown"].append(path)
        elif classified[doc_type] is None:
            classified[doc_type] = path
        # If already have one of this type, add as unknown
        else:
            classified["unknown"].append(path)

    return {"supporting": classified, "excluded_reports": excluded}
