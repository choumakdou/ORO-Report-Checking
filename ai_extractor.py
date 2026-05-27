"""ai_extractor.py — Extract structured fields from PDF text via OpenAI."""
import json
import re
from typing import Any, Optional
from openai import OpenAI
import config


def _client() -> OpenAI:
    return OpenAI(api_key=config.get_api_key())


def _chat(system: str, user: str, model: Optional[str] = None) -> dict:
    """Call OpenAI and return parsed JSON dict, or {} on failure."""
    m = model or config.get_model()
    try:
        resp = _client().chat.completions.create(
            model=m,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0,
            response_format={"type": "json_object"},
        )
        raw = resp.choices[0].message.content or "{}"
        return json.loads(raw)
    except Exception as e:
        return {"_error": str(e)}


# ─────────────────────────────────────────────
# VALUATION REPORT
# ─────────────────────────────────────────────
VALUATION_SYSTEM = """You are a Hong Kong property valuation expert and document analyst.
Extract fields from ORO (Official Receiver's Office) HOS valuation reports.
Return ONLY valid JSON. Use null for any field not found in the text.
All monetary amounts as integers (no commas). Percentages as numbers (e.g. 30 not 0.30).
Dates as strings in the format they appear in the document."""

VALUATION_PROMPT = """From the valuation report text below, extract ALL of the following fields as a JSON object:

{
  "block_letter_in_s2_1": "Block letter stated in section 2.1 description sentence (single letter A/B/C)",
  "address_block_letters": ["all block letters that appear in the property address throughout the report"],
  "photo_block_letter": "Block letter mentioned in Appendix D photo captions (e.g. 'Subject Block A')",
  "year_of_completion": "Year stated in section 2.2 (integer)",
  "saleable_area_sqft": "Saleable area in square feet from section 2.4 (integer)",
  "saleable_area_sqm": "Saleable area in square metres from section 2.4 (float)",
  "registered_owners": ["list of owner names from section 3.5"],
  "lot_number": "Full lot description from section 3.1",
  "shares": "Undivided shares fraction from section 3.2 (e.g. '50/98512')",
  "lease_term_start": "Lease start date from section 3.3",
  "lease_term_end": "Lease expiry date from section 3.3",
  "govt_rent": "Government rent description from section 3.4",
  "encumbrances": [
    {
      "memorial_no": "memorial number e.g. SK365381",
      "date_of_instrument": "date as stated in report",
      "nature": "nature of instrument",
      "in_favour_of": "beneficiary or null"
    }
  ],
  "purchase_price": "Purchase Price HK$ amount from section 3.6 (integer)",
  "initial_market_value": "Initial Market Value HK$ from section 3.6 (integer)",
  "om_value_100": "Open Market Value 100% HK$ from section 4.3(i) (integer)",
  "om_value_100_spellout": "Word spell-out for OM 100% value",
  "om_discount_pct": "Discount % for OM half-share from section 4.2 (integer)",
  "om_value_50": "OM Value 50% half-share HK$ from section 4.3(ii) (integer)",
  "om_value_50_spellout": "Word spell-out for OM 50% value",
  "hossms_value_100": "HOSSMS Value 100% HK$ from section 5.3(i) (integer)",
  "hossms_value_100_spellout": "Word spell-out for HOSSMS 100% value",
  "hossms_discount_pct": "Discount % for HOSSMS half-share from section 5.2 (integer)",
  "hossms_value_50": "HOSSMS Value 50% half-share HK$ from section 5.3(ii) (integer)",
  "hossms_value_50_spellout": "Word spell-out for HOSSMS 50% value",
  "date_of_valuation": "Date of valuation as stated in report header",
  "date_of_report": "Date of report",
  "inspector_name": "Name of person who conducted site inspection",
  "inspection_date": "Date of site inspection",
  "signatory_name": "Name of signing valuer",
  "signatory_quals": "Professional qualifications of signing valuer (e.g. MRICS MHKIS)",
  "mtr_station": "Nearest MTR station name from section 1.2",
  "mtr_walking_minutes": "Walking time to MTR stated in report (string as written)",
  "num_blocks": "Number of blocks in development from section 1.4 (integer)",
  "num_units": "Total number of residential units from section 1.4 (integer)",
  "oro_reference": "ORO client reference number",
  "chft_reference": "CHFT valuer's reference number",
  "appendix_list": ["list of appendix labels e.g. A, B, C"],
  "valuation_date_in_s4_3": "Date stated after 'as at' in section 4.3",
  "valuation_date_in_s5_3": "Date stated after 'as at' in section 5.3"
}

VALUATION REPORT TEXT:
"""


def extract_valuation_report(text: str) -> dict:
    from pdf_parser import truncate_for_ai
    t = truncate_for_ai(text, 90000)
    return _chat(VALUATION_SYSTEM, VALUATION_PROMPT + t)


# ─────────────────────────────────────────────
# LAND REGISTER
# ─────────────────────────────────────────────
LAND_REG_SYSTEM = """You are a Hong Kong Land Registry document analyst.
Extract structured data from Hong Kong Land Register printouts.
Return ONLY valid JSON. Use null for fields not found."""

LAND_REG_PROMPT = """From the Hong Kong Land Register text below, extract:

{
  "lot_number": "Full lot description e.g. 'THE REMAINING PORTION OF TSEUNG KWAN O TOWN LOT NO. 54'",
  "shares": "Share of the lot e.g. '50/98512'",
  "lease_start": "Lease commencement date",
  "lease_end": "Lease expiry date",
  "govt_rent_remarks": "Government rent remarks text",
  "property_address": "Full English property address",
  "search_date": "Date and time of land search",
  "owners": [
    {
      "name": "Owner name",
      "capacity": "e.g. JOINT TENANT or SOLE OWNER or null",
      "memorial_no": "Memorial number of ownership instrument",
      "date_of_instrument": "Date of instrument (DD/MM/YYYY)",
      "consideration": "Consideration amount or null"
    }
  ],
  "encumbrances": [
    {
      "memorial_no": "e.g. SK365381",
      "date_of_instrument": "Date of instrument (DD/MM/YYYY or as shown)",
      "date_of_registration": "Date of registration",
      "nature": "Nature of instrument e.g. DEED OF MUTUAL COVENANT",
      "in_favour_of": "Beneficiary name or null",
      "remarks": "Any remarks text"
    }
  ],
  "deeds_pending": ["list of any deeds pending registration, or empty list"]
}

LAND REGISTER TEXT:
"""


def extract_land_register(text: str) -> dict:
    from pdf_parser import truncate_for_ai
    t = truncate_for_ai(text, 60000)
    return _chat(LAND_REG_SYSTEM, LAND_REG_PROMPT + t)


# ─────────────────────────────────────────────
# RVD PRINTOUT
# ─────────────────────────────────────────────
RVD_SYSTEM = """You are a Hong Kong Rating and Valuation Department document analyst.
Extract data from RVD Property Information Online printouts. Return ONLY valid JSON."""

RVD_PROMPT = """From the RVD Property Information Online printout text below, extract:

{
  "saleable_area_sqm": "Saleable area in square metres (float, e.g. 50.10)",
  "cc_issued_date": "Completion Certificate issued date as shown",
  "cc_issued_year": "Year of completion certificate (integer)",
  "block_name_english": "English block name e.g. 'TONG FAI HOUSE (BLK A)'",
  "block_name_chinese": "Chinese block name if shown",
  "property_address_english": "Full English property address",
  "assessment_no": "Assessment number",
  "date_of_information": "Date of provision of information",
  "property_type": "Property type for rates purposes (English)",
  "pio_serial_no": "PIO Serial Number of Occupation Document"
}

RVD TEXT:
"""


def extract_rvd(text: str) -> dict:
    from pdf_parser import truncate_for_ai
    t = truncate_for_ai(text, 30000)
    return _chat(RVD_SYSTEM, RVD_PROMPT + t)


# ─────────────────────────────────────────────
# ASSIGNMENT
# ─────────────────────────────────────────────
ASSIGN_SYSTEM = """You are a Hong Kong conveyancing document analyst.
Extract data from HKHA Assignment documents. Return ONLY valid JSON. 
Monetary amounts as integers."""

ASSIGN_PROMPT = """From the HKHA Assignment document text below, extract:

{
  "purchaser_names": ["list of purchaser names"],
  "purchase_price": "Purchase price HK$ integer",
  "purchase_price_words": "Purchase price in words as written in the document",
  "initial_market_value": "Initial market value HK$ integer from Clause 5",
  "imv_words": "IMV in words as written in the document",
  "flat_no": "Flat number",
  "floor": "Floor number",
  "block_letter": "Block letter (single letter)",
  "estate_name": "Estate name",
  "lot_number": "Full lot description from Schedule (1)(a)",
  "shares": "Undivided shares e.g. '50/98512'",
  "lease_start": "Lease commencement date from Schedule (2)(c)",
  "lease_end": "Lease expiry date from Schedule (2)(c)",
  "dmc_memorial_no": "Deed of Mutual Covenant memorial number from Schedule (3)",
  "dmc_date": "DMC date from Schedule (3)",
  "assignment_date": "Date of the Assignment",
  "assignment_memorial_no": "Memorial number assigned by Land Registry on registration"
}

ASSIGNMENT TEXT:
"""


def extract_assignment(text: str) -> dict:
    from pdf_parser import truncate_for_ai
    t = truncate_for_ai(text, 40000)
    return _chat(ASSIGN_SYSTEM, ASSIGN_PROMPT + t)


# ─────────────────────────────────────────────
# INSTRUCTION LETTER
# ─────────────────────────────────────────────
INSTR_SYSTEM = """You are an analyst reading Official Receiver's Office instruction letters.
Extract structured data. Return ONLY valid JSON."""

INSTR_PROMPT = """From the ORO instruction letter text below, extract:

{
  "bankruptcy_number": "Bankruptcy number (integer)",
  "bankruptcy_year": "Bankruptcy year (integer)",
  "bankrupt_name": "Name of the bankrupt individual",
  "property_address": "Full property address as stated in the letter",
  "block_letter": "Block letter from address (single letter)",
  "flat_no": "Flat number",
  "floor": "Floor number",
  "estate_name": "Estate name",
  "oro_reference": "ORO reference (Your Ref in letter header)",
  "letter_date": "Date of the instruction letter",
  "due_days": "Number of days to submit report (usually 21)",
  "fee_amount": "Professional fee amount HK$",
  "oro_contact_officer": "Name of ORO officer who signed the letter",
  "valuation_scope": "Description of what must be valued (open market value, HOS secondary, half share etc)"
}

INSTRUCTION LETTER TEXT:
"""


def extract_instruction_letter(text: str) -> dict:
    from pdf_parser import truncate_for_ai
    t = truncate_for_ai(text, 20000)
    return _chat(INSTR_SYSTEM, INSTR_PROMPT + t)


# ─────────────────────────────────────────────
# SPELL-OUT VERIFICATION VIA AI
# ─────────────────────────────────────────────
SPELLOUT_SYSTEM = """You are a Hong Kong legal document expert. 
Verify whether a numerical amount matches its English word spell-out 
in Hong Kong legal document convention. Return JSON only."""

def verify_spellout_ai(amount: int, spellout: str) -> dict:
    """Use AI to verify spell-out when rule-based check is uncertain."""
    prompt = f"""Does the following spell-out correctly represent HK${amount:,} 
in Hong Kong legal document convention?

Spell-out: "{spellout}"
Amount: {amount} (HK${amount:,})

Return: {{"matches": true/false, "expected": "correct spell-out", "issue": "description of mismatch or null"}}"""
    return _chat(SPELLOUT_SYSTEM, prompt)
