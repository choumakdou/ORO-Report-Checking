"""rule_checker.py — All QC check logic for ORO HOS valuation reports."""
from dataclasses import dataclass, field
from typing import List, Optional
import re
import utils


# ─────────────────────────────────────────────
# Data model for a single finding
# ─────────────────────────────────────────────
@dataclass
class Finding:
    severity: str          # "ERROR", "CONCERN", "OK", "INFO"
    category: str          # e.g. "Block Letter", "Arithmetic"
    check_id: str          # e.g. "E1"
    description: str       # human-readable finding
    expected: str = ""
    actual: str = ""
    source: str = ""       # which document the value came from


# ─────────────────────────────────────────────
# Helper
# ─────────────────────────────────────────────
def _ok(check_id: str, category: str, description: str) -> Finding:
    return Finding("OK", category, check_id, description)


def _err(check_id: str, category: str, description: str,
         expected: str = "", actual: str = "") -> Finding:
    return Finding("ERROR", category, check_id, description, expected, actual)


def _warn(check_id: str, category: str, description: str,
          expected: str = "", actual: str = "") -> Finding:
    return Finding("CONCERN", category, check_id, description, expected, actual)


def _info(check_id: str, category: str, description: str) -> Finding:
    return Finding("INFO", category, check_id, description)


def _missing(check_id: str, category: str, field_name: str) -> Finding:
    return Finding("CONCERN", category, check_id,
                   f"Could not extract '{field_name}' — please verify manually.")


# ─────────────────────────────────────────────
# Main checker
# ─────────────────────────────────────────────
def run_all_checks(
    val: dict,        # extracted from valuation report
    lr: dict,         # extracted from land register
    rvd: dict,        # extracted from RVD printout
    asgn: dict,       # extracted from assignment
    instr: dict,      # extracted from instruction letter
) -> List[Finding]:
    findings: List[Finding] = []

    findings += check_block_letter(val, lr, asgn, instr)
    findings += check_bankruptcy_date(val, lr, instr)
    findings += check_saleable_area(val, rvd)
    findings += check_om_arithmetic(val)
    findings += check_hossms_arithmetic(val)
    findings += check_spellouts(val)
    findings += check_encumbrances(val, lr)
    findings += check_registered_owners(val, lr, asgn)
    findings += check_lot_shares_lease(val, lr, asgn)
    findings += check_purchase_price_imv(val, asgn)
    findings += check_year_of_completion(val, rvd)
    findings += check_valuation_dates(val)
    findings += check_references(val, instr)
    findings += check_appendix_list(val)

    return findings


# ─────────────────────────────────────────────
# C1: Block letter consistency
# ─────────────────────────────────────────────
def check_block_letter(val, lr, asgn, instr) -> List[Finding]:
    findings = []
    cat = "Block Letter"

    # Block letter from instruction letter (authoritative)
    instr_block = (instr.get("block_letter") or "").strip().upper()
    # Block letter stated in §2.1
    s2_1_block = (val.get("block_letter_in_s2_1") or "").strip().upper()
    # Block letter in photo caption
    photo_block = (val.get("photo_block_letter") or "").strip().upper()

    if not instr_block:
        findings.append(_missing("BL-0", cat, "block_letter (instruction letter)"))
        return findings

    if not s2_1_block:
        findings.append(_missing("BL-1", cat, "block_letter_in_s2_1 (§2.1)"))
    elif s2_1_block != instr_block:
        findings.append(_err(
            "BL-1", cat,
            f"§2.1 states 'Block {s2_1_block}' but instruction letter and address say 'Block {instr_block}'.",
            expected=f"Block {instr_block}", actual=f"Block {s2_1_block}",
            source="§2.1 vs Instruction Letter"
        ))
    else:
        findings.append(_ok("BL-1", cat,
            f"§2.1 block letter '{s2_1_block}' matches instruction letter. ✓"))

    # Cross-check address block letters in report
    addr_letters = [x.strip().upper() for x in (val.get("address_block_letters") or []) if x]
    wrong_addr = [x for x in addr_letters if x and x != instr_block]
    if wrong_addr:
        findings.append(_warn("BL-2", cat,
            f"Some address fields in report mention Block {wrong_addr} — verify all are Block {instr_block}.",
            expected=f"Block {instr_block}", actual=str(wrong_addr)))
    elif addr_letters:
        findings.append(_ok("BL-2", cat,
            f"All address references in report use Block '{instr_block}'. ✓"))

    # Photo caption block
    if photo_block and photo_block != instr_block:
        findings.append(_err("BL-3", cat,
            f"Appendix D photo caption says 'Block {photo_block}' but subject is Block {instr_block}.",
            expected=f"Block {instr_block}", actual=f"Block {photo_block}",
            source="Appendix D photo caption"))
    elif photo_block:
        findings.append(_ok("BL-3", cat,
            f"Appendix D photo caption block letter '{photo_block}' is correct. ✓"))

    return findings


# ─────────────────────────────────────────────
# C2: Bankruptcy Order date
# ─────────────────────────────────────────────
def check_bankruptcy_date(val, lr, instr) -> List[Finding]:
    findings = []
    cat = "Bankruptcy Order Date"

    # Find bankruptcy encumbrance in Land Register
    lr_bk_entry = None
    for enc in (lr.get("encumbrances") or []):
        nature = (enc.get("nature") or "").upper()
        if "BANKRUPT" in nature or "BANKRUPTCY" in nature:
            lr_bk_entry = enc
            break

    # Find bankruptcy encumbrance in valuation report §3.7
    val_bk_entry = None
    for enc in (val.get("encumbrances") or []):
        nature = (enc.get("nature") or "").upper()
        if "BANKRUPT" in nature or "BANKRUPTCY" in nature:
            val_bk_entry = enc
            break

    if not lr_bk_entry:
        findings.append(_missing("BK-0", cat, "bankruptcy order in Land Register"))
        return findings
    if not val_bk_entry:
        findings.append(_missing("BK-1", cat, "bankruptcy order in §3.7"))
        return findings

    lr_date = lr_bk_entry.get("date_of_instrument") or ""
    val_date = val_bk_entry.get("date_of_instrument") or ""
    lr_year = utils.extract_year(lr_date)
    val_year = utils.extract_year(val_date)

    if lr_year and val_year:
        if lr_year != val_year:
            findings.append(_err("BK-1", cat,
                f"Bankruptcy Order year in §3.7 ({val_year}) does not match Land Register ({lr_year}).",
                expected=str(lr_year), actual=str(val_year),
                source="§3.7(iii) vs Land Register"))
        else:
            # Full date comparison
            lr_ymd = utils.parse_date_to_ymd(lr_date)
            val_ymd = utils.parse_date_to_ymd(val_date)
            if lr_ymd and val_ymd and lr_ymd != val_ymd:
                findings.append(_err("BK-1", cat,
                    f"Bankruptcy Order date in §3.7 ('{val_date}') differs from Land Register ('{lr_date}').",
                    expected=lr_date, actual=val_date,
                    source="§3.7(iii) vs Land Register"))
            else:
                findings.append(_ok("BK-1", cat,
                    f"Bankruptcy Order date '{val_date}' matches Land Register. ✓"))

    # Cross-check bankruptcy year with instruction letter
    instr_year = instr.get("bankruptcy_year")
    if instr_year and lr_year and int(instr_year) != lr_year:
        findings.append(_warn("BK-2", cat,
            f"Bankruptcy year in instruction letter ({instr_year}) differs from Land Register date year ({lr_year})."))
    elif instr_year and lr_year:
        findings.append(_ok("BK-2", cat,
            f"Bankruptcy year {lr_year} consistent with instruction letter. ✓"))

    # Memorial number check
    lr_memorial = (lr_bk_entry.get("memorial_no") or "").strip()
    val_memorial = (val_bk_entry.get("memorial_no") or "").strip()
    if lr_memorial and val_memorial:
        if lr_memorial.replace(" ", "").upper() != val_memorial.replace(" ", "").upper():
            findings.append(_warn("BK-3", cat,
                f"Bankruptcy Order memorial no. in report ({val_memorial}) differs from Land Register ({lr_memorial}).",
                expected=lr_memorial, actual=val_memorial))
        else:
            findings.append(_ok("BK-3", cat,
                f"Bankruptcy Order memorial no. '{val_memorial}' matches Land Register. ✓"))

    return findings


# ─────────────────────────────────────────────
# C3: Saleable area conversion
# ─────────────────────────────────────────────
def check_saleable_area(val, rvd) -> List[Finding]:
    findings = []
    cat = "Saleable Area"

    rvd_sqm = rvd.get("saleable_area_sqm")
    val_sqft = val.get("saleable_area_sqft")
    val_sqm = val.get("saleable_area_sqm")

    if rvd_sqm is None:
        findings.append(_missing("SA-0", cat, "saleable_area_sqm (RVD)"))
        return findings

    try:
        rvd_sqm_f = float(rvd_sqm)
    except (TypeError, ValueError):
        findings.append(_missing("SA-0", cat, "saleable_area_sqm (RVD) — could not parse"))
        return findings

    expected_sqft = utils.sqm_to_sqft(rvd_sqm_f)

    # Check sqm agreement
    if val_sqm is not None:
        try:
            val_sqm_f = float(val_sqm)
            if abs(val_sqm_f - rvd_sqm_f) > 0.05:
                findings.append(_err("SA-1", cat,
                    f"Saleable area (sq m) in report ({val_sqm_f}) differs from RVD ({rvd_sqm_f}).",
                    expected=str(rvd_sqm_f), actual=str(val_sqm_f),
                    source="§2.4 vs RVD"))
            else:
                findings.append(_ok("SA-1", cat,
                    f"Saleable area sq m ({val_sqm_f}) matches RVD ({rvd_sqm_f}). ✓"))
        except (TypeError, ValueError):
            findings.append(_missing("SA-1", cat, "saleable_area_sqm (report §2.4)"))

    # Check sqft
    if val_sqft is not None:
        try:
            val_sqft_i = int(val_sqft)
            if abs(val_sqft_i - expected_sqft) > 1:
                findings.append(_err("SA-2", cat,
                    f"Saleable area sqft in report ({val_sqft_i}) does not match expected conversion "
                    f"{rvd_sqm_f} sq m × 10.764 = {expected_sqft} sqft.",
                    expected=str(expected_sqft), actual=str(val_sqft_i),
                    source="§2.4 conversion check"))
            else:
                findings.append(_ok("SA-2", cat,
                    f"Saleable area sqft ({val_sqft_i}) correctly derived from {rvd_sqm_f} sq m. ✓"))
        except (TypeError, ValueError):
            findings.append(_missing("SA-2", cat, "saleable_area_sqft (report §2.4)"))
    else:
        findings.append(_missing("SA-2", cat, "saleable_area_sqft (§2.4)"))

    return findings


# ─────────────────────────────────────────────
# C4: OM arithmetic
# ─────────────────────────────────────────────
def check_om_arithmetic(val) -> List[Finding]:
    findings = []
    cat = "Open Market Arithmetic"

    om100 = val.get("om_value_100")
    om50 = val.get("om_value_50")
    disc = val.get("om_discount_pct")

    if om100 is None or om50 is None or disc is None:
        for f, n in [("om_value_100", om100), ("om_value_50", om50), ("om_discount_pct", disc)]:
            if n is None:
                findings.append(_missing("OM-0", cat, f))
        return findings

    try:
        om100_i = int(om100)
        om50_i = int(om50)
        disc_f = float(disc) / 100
        expected_50 = round(om100_i * 0.5 * (1 - disc_f))

        # Tolerance: ±1000 HK$
        if abs(om50_i - expected_50) > 1000:
            findings.append(_err("OM-1", cat,
                f"OM half-share HK${om50_i:,} ≠ HK${om100_i:,} × 50% × (1−{int(disc)}%) = HK${expected_50:,}.",
                expected=f"HK${expected_50:,}", actual=f"HK${om50_i:,}",
                source="§4.3(ii)"))
        else:
            findings.append(_ok("OM-1", cat,
                f"OM half-share HK${om50_i:,} arithmetic correct "
                f"(HK${om100_i:,} × 50% × {100-int(disc)}%). ✓"))
    except (TypeError, ValueError):
        findings.append(_err("OM-1", cat, "Could not verify OM half-share arithmetic — check values."))

    return findings


# ─────────────────────────────────────────────
# C5: HOSSMS arithmetic
# ─────────────────────────────────────────────
def check_hossms_arithmetic(val) -> List[Finding]:
    findings = []
    cat = "HOSSMS Arithmetic"

    h100 = val.get("hossms_value_100")
    h50 = val.get("hossms_value_50")
    disc = val.get("hossms_discount_pct")

    if h100 is None or h50 is None or disc is None:
        for f, n in [("hossms_value_100", h100), ("hossms_value_50", h50), ("hossms_discount_pct", disc)]:
            if n is None:
                findings.append(_missing("HS-0", cat, f))
        return findings

    try:
        h100_i = int(h100)
        h50_i = int(h50)
        disc_f = float(disc) / 100
        expected_50 = round(h100_i * 0.5 * (1 - disc_f))

        if abs(h50_i - expected_50) > 1000:
            findings.append(_err("HS-1", cat,
                f"HOSSMS half-share HK${h50_i:,} ≠ HK${h100_i:,} × 50% × (1−{int(disc)}%) = HK${expected_50:,}.",
                expected=f"HK${expected_50:,}", actual=f"HK${h50_i:,}",
                source="§5.3(ii)"))
        else:
            findings.append(_ok("HS-1", cat,
                f"HOSSMS half-share HK${h50_i:,} arithmetic correct "
                f"(HK${h100_i:,} × 50% × {100-int(disc)}%). ✓"))
    except (TypeError, ValueError):
        findings.append(_err("HS-1", cat, "Could not verify HOSSMS arithmetic — check values."))

    return findings


# ─────────────────────────────────────────────
# C6: Spell-outs
# ─────────────────────────────────────────────
def check_spellouts(val) -> List[Finding]:
    findings = []
    cat = "Value Spell-out"
    pairs = [
        ("om_value_100", "om_value_100_spellout", "OM 100%", "§4.3(i)"),
        ("om_value_50", "om_value_50_spellout", "OM 50%", "§4.3(ii)"),
        ("hossms_value_100", "hossms_value_100_spellout", "HOSSMS 100%", "§5.3(i)"),
        ("hossms_value_50", "hossms_value_50_spellout", "HOSSMS 50%", "§5.3(ii)"),
    ]
    for num_key, word_key, label, loc in pairs:
        amount = val.get(num_key)
        spellout = val.get(word_key)
        if amount is None:
            findings.append(_missing(f"SP-{label}", cat, num_key))
            continue
        if not spellout:
            findings.append(_missing(f"SP-{label}", cat, word_key))
            continue
        try:
            amount_i = int(amount)
            expected_words = utils.number_to_words(amount_i)
            matches = utils.spellout_matches(amount_i, spellout)
            if matches:
                findings.append(_ok(f"SP-{label}", cat,
                    f"{label} spell-out matches HK${amount_i:,}. ✓"))
            else:
                findings.append(_err(f"SP-{label}", cat,
                    f"{label} spell-out mismatch at {loc}.",
                    expected=expected_words,
                    actual=spellout.upper()[:120],
                    source=loc))
        except (TypeError, ValueError):
            findings.append(_warn(f"SP-{label}", cat,
                f"Could not verify {label} spell-out — please check manually."))
    return findings


# ─────────────────────────────────────────────
# C7: Encumbrance cross-check
# ─────────────────────────────────────────────
def check_encumbrances(val, lr) -> List[Finding]:
    findings = []
    cat = "Encumbrances"

    val_encs = val.get("encumbrances") or []
    lr_encs = lr.get("encumbrances") or []

    if not lr_encs:
        findings.append(_missing("ENC-0", cat, "encumbrances (Land Register)"))
        return findings
    if not val_encs:
        findings.append(_missing("ENC-0", cat, "encumbrances (§3.7)"))
        return findings

    # Check count
    if len(val_encs) < len(lr_encs):
        findings.append(_warn("ENC-1", cat,
            f"Land Register shows {len(lr_encs)} encumbrance(s) but report §3.7 lists {len(val_encs)}. "
            f"Possible omission — review Land Register.",
            expected=str(len(lr_encs)), actual=str(len(val_encs))))
    else:
        findings.append(_ok("ENC-1", cat,
            f"Encumbrance count: report §3.7 = {len(val_encs)}, Land Register = {len(lr_encs)}. ✓"))

    # Cross-check each encumbrance in the report against Land Register
    for i, ve in enumerate(val_encs):
        v_mem = (ve.get("memorial_no") or "").replace(" ", "").upper()
        # Find matching LR entry
        matched_lr = None
        for le in lr_encs:
            l_mem = (le.get("memorial_no") or "").replace(" ", "").upper()
            if v_mem and l_mem and v_mem == l_mem:
                matched_lr = le
                break

        if not matched_lr:
            # Try nature-based matching
            v_nat = (ve.get("nature") or "").upper()
            for le in lr_encs:
                l_nat = (le.get("nature") or "").upper()
                if any(kw in v_nat for kw in l_nat.split() if len(kw) > 4):
                    matched_lr = le
                    break

        if not matched_lr:
            findings.append(_warn(f"ENC-{i+2}", cat,
                f"Encumbrance {i+1} in §3.7 (memorial: {v_mem or 'unknown'}) "
                f"could not be matched in Land Register — verify manually."))
            continue

        # Date of instrument check
        v_date = ve.get("date_of_instrument") or ""
        l_date = matched_lr.get("date_of_instrument") or ""
        v_ymd = utils.parse_date_to_ymd(v_date)
        l_ymd = utils.parse_date_to_ymd(l_date)

        if v_ymd and l_ymd:
            if v_ymd != l_ymd:
                findings.append(_err(f"ENC-{i+2}", cat,
                    f"Encumbrance {i+1} (memorial {v_mem}): date in §3.7 ('{v_date}') "
                    f"differs from Land Register ('{l_date}').",
                    expected=l_date, actual=v_date,
                    source=f"§3.7 item {i+1} vs Land Register"))
            else:
                findings.append(_ok(f"ENC-{i+2}", cat,
                    f"Encumbrance {i+1} (memorial {v_mem}): date '{v_date}' matches Land Register. ✓"))
        else:
            findings.append(_warn(f"ENC-{i+2}", cat,
                f"Encumbrance {i+1} (memorial {v_mem}): could not parse dates for comparison "
                f"(report: '{v_date}', LR: '{l_date}') — verify manually."))

    return findings


# ─────────────────────────────────────────────
# C8: Registered owners
# ─────────────────────────────────────────────
def check_registered_owners(val, lr, asgn) -> List[Finding]:
    findings = []
    cat = "Registered Owners"

    val_owners = [utils.normalise_name(n) for n in (val.get("registered_owners") or []) if n]
    lr_owners = [utils.normalise_name(o.get("name", "")) for o in (lr.get("owners") or [])
                 if o.get("name") and o.get("name") != "THE HONG KONG HOUSING AUTHORITY"]
    asgn_owners = [utils.normalise_name(n) for n in (asgn.get("purchaser_names") or []) if n]

    if not val_owners:
        findings.append(_missing("OWN-0", cat, "registered_owners (§3.5)"))
        return findings

    if lr_owners:
        # Every LR owner should appear in report
        for name in lr_owners:
            if not any(utils.names_match(name, v) for v in val_owners):
                findings.append(_err("OWN-1", cat,
                    f"Owner '{name}' from Land Register not found in §3.5.",
                    expected=name, actual=str(val_owners), source="§3.5 vs Land Register"))
        if all(any(utils.names_match(n, v) for v in val_owners) for n in lr_owners):
            findings.append(_ok("OWN-1", cat,
                f"All registered owners in §3.5 match Land Register. ✓"))

    if asgn_owners:
        for name in asgn_owners:
            if not any(utils.names_match(name, v) for v in val_owners):
                findings.append(_warn("OWN-2", cat,
                    f"Purchaser '{name}' from Assignment not found in §3.5 — check romanisation.",
                    expected=name, actual=str(val_owners), source="§3.5 vs Assignment"))
        if all(any(utils.names_match(n, v) for v in val_owners) for n in asgn_owners):
            findings.append(_ok("OWN-2", cat,
                f"Owner names consistent with Assignment. ✓"))

    return findings


# ─────────────────────────────────────────────
# C9: Lot, shares, lease term
# ─────────────────────────────────────────────
def check_lot_shares_lease(val, lr, asgn) -> List[Finding]:
    findings = []
    cat = "Lot / Shares / Lease"

    def cmp(field, v_val, l_val, label, check_id):
        if not v_val:
            findings.append(_missing(check_id, cat, f"{field} (§3.x)"))
            return
        if not l_val:
            findings.append(_missing(check_id, cat, f"{field} (Land Register)"))
            return
        v_norm = re.sub(r"\s+", " ", str(v_val).strip().upper())
        l_norm = re.sub(r"\s+", " ", str(l_val).strip().upper())
        if v_norm != l_norm:
            findings.append(_err(check_id, cat,
                f"{label} in report differs from Land Register.",
                expected=l_norm[:100], actual=v_norm[:100],
                source=f"§3.x vs Land Register"))
        else:
            findings.append(_ok(check_id, cat, f"{label} matches Land Register. ✓"))

    cmp("shares", val.get("shares"), lr.get("shares"), "Shares of Lot (§3.2)", "LSL-1")

    # Lease term
    v_start = val.get("lease_term_start") or ""
    v_end = val.get("lease_term_end") or ""
    l_start = lr.get("lease_start") or ""
    l_end = lr.get("lease_end") or ""

    if v_start and l_start:
        v_ymd = utils.parse_date_to_ymd(v_start)
        l_ymd = utils.parse_date_to_ymd(l_start)
        if v_ymd and l_ymd and v_ymd != l_ymd:
            findings.append(_err("LSL-2", cat,
                f"Lease start in report ('{v_start}') differs from Land Register ('{l_start}').",
                expected=l_start, actual=v_start))
        else:
            findings.append(_ok("LSL-2", cat, f"Lease start date matches. ✓"))
    else:
        findings.append(_missing("LSL-2", cat, "lease_term_start"))

    if v_end and l_end:
        v_ymd = utils.parse_date_to_ymd(v_end)
        l_ymd = utils.parse_date_to_ymd(l_end)
        if v_ymd and l_ymd and v_ymd != l_ymd:
            findings.append(_err("LSL-3", cat,
                f"Lease expiry in report ('{v_end}') differs from Land Register ('{l_end}').",
                expected=l_end, actual=v_end))
        else:
            findings.append(_ok("LSL-3", cat, f"Lease expiry date matches. ✓"))
    else:
        findings.append(_missing("LSL-3", cat, "lease_term_end"))

    return findings


# ─────────────────────────────────────────────
# C10: Purchase Price / IMV vs Assignment
# ─────────────────────────────────────────────
def check_purchase_price_imv(val, asgn) -> List[Finding]:
    findings = []
    cat = "Purchase Price / IMV"

    for key, asgn_key, label, check_id in [
        ("purchase_price", "purchase_price", "Purchase Price", "PP-1"),
        ("initial_market_value", "initial_market_value", "Initial Market Value", "PP-2"),
    ]:
        v_val = val.get(key)
        a_val = asgn.get(asgn_key)
        if v_val is None:
            findings.append(_missing(check_id, cat, f"{key} (§3.6)"))
            continue
        if a_val is None:
            findings.append(_missing(check_id, cat, f"{asgn_key} (Assignment)"))
            continue
        try:
            if abs(int(v_val) - int(a_val)) > 0:
                findings.append(_err(check_id, cat,
                    f"{label} in §3.6 (HK${int(v_val):,}) differs from Assignment (HK${int(a_val):,}).",
                    expected=f"HK${int(a_val):,}", actual=f"HK${int(v_val):,}",
                    source="§3.6 vs Assignment"))
            else:
                findings.append(_ok(check_id, cat,
                    f"{label} HK${int(v_val):,} matches Assignment. ✓"))
        except (TypeError, ValueError):
            findings.append(_warn(check_id, cat,
                f"Could not compare {label} numerically — verify manually."))

    return findings


# ─────────────────────────────────────────────
# C11: Year of completion
# ─────────────────────────────────────────────
def check_year_of_completion(val, rvd) -> List[Finding]:
    findings = []
    cat = "Year of Completion"

    val_year = val.get("year_of_completion")
    rvd_year = rvd.get("cc_issued_year")

    if val_year is None:
        findings.append(_missing("YC-1", cat, "year_of_completion (§2.2)"))
        return findings
    if rvd_year is None:
        # Try to derive from cc_issued_date
        cc_date = rvd.get("cc_issued_date") or ""
        rvd_year = utils.extract_year(cc_date)

    if rvd_year is None:
        findings.append(_missing("YC-1", cat, "cc_issued_year (RVD)"))
        return findings

    try:
        if int(val_year) != int(rvd_year):
            findings.append(_err("YC-1", cat,
                f"Year of completion in §2.2 ({val_year}) differs from RVD CC issued year ({rvd_year}).",
                expected=str(rvd_year), actual=str(val_year),
                source="§2.2 vs RVD"))
        else:
            findings.append(_ok("YC-1", cat,
                f"Year of completion {val_year} matches RVD CC issued date. ✓"))
    except (TypeError, ValueError):
        findings.append(_warn("YC-1", cat, "Could not compare year of completion — verify manually."))

    return findings


# ─────────────────────────────────────────────
# C12: Valuation date consistency within report
# ─────────────────────────────────────────────
def check_valuation_dates(val) -> List[Finding]:
    findings = []
    cat = "Valuation Date Consistency"

    d_header = val.get("date_of_valuation") or ""
    d_s4 = val.get("valuation_date_in_s4_3") or ""
    d_s5 = val.get("valuation_date_in_s5_3") or ""

    if not d_header:
        findings.append(_missing("VD-1", cat, "date_of_valuation (report header)"))
        return findings

    h_ymd = utils.parse_date_to_ymd(d_header)

    all_ok = True
    for d, loc in [(d_s4, "§4.3"), (d_s5, "§5.3")]:
        if not d:
            findings.append(_missing(f"VD-{loc}", cat, f"valuation date ({loc})"))
            all_ok = False
            continue
        ymd = utils.parse_date_to_ymd(d)
        if h_ymd and ymd and h_ymd != ymd:
            findings.append(_err(f"VD-{loc}", cat,
                f"Date in {loc} ('{d}') differs from report header ('{d_header}').",
                expected=d_header, actual=d, source=loc))
            all_ok = False
        else:
            findings.append(_ok(f"VD-{loc}", cat,
                f"Valuation date '{d}' in {loc} consistent with header. ✓"))

    return findings


# ─────────────────────────────────────────────
# C13: ORO / CHFT references
# ─────────────────────────────────────────────
def check_references(val, instr) -> List[Finding]:
    findings = []
    cat = "Reference Numbers"

    v_oro = (val.get("oro_reference") or "").strip()
    i_oro = (instr.get("oro_reference") or "").strip()

    if v_oro and i_oro:
        if v_oro.upper() != i_oro.upper():
            findings.append(_err("REF-1", cat,
                f"ORO reference in report ('{v_oro}') differs from instruction letter ('{i_oro}').",
                expected=i_oro, actual=v_oro, source="Cover vs Instruction Letter"))
        else:
            findings.append(_ok("REF-1", cat, f"ORO reference '{v_oro}' matches instruction letter. ✓"))
    else:
        findings.append(_missing("REF-1", cat, "oro_reference"))

    return findings


# ─────────────────────────────────────────────
# C14: Appendix list
# ─────────────────────────────────────────────
def check_appendix_list(val) -> List[Finding]:
    findings = []
    cat = "Appendix List"

    expected = ["A", "B", "C", "D", "E", "F", "G", "H"]
    listed = [str(x).strip().upper() for x in (val.get("appendix_list") or [])]

    if not listed:
        findings.append(_missing("APP-1", cat, "appendix_list"))
        return findings

    missing = [x for x in expected if x not in listed]
    if missing:
        findings.append(_warn("APP-1", cat,
            f"Expected appendices A–H; these may be missing: {', '.join(missing)}.",
            expected="A, B, C, D, E, F, G, H", actual=", ".join(listed)))
    else:
        findings.append(_ok("APP-1", cat, "All appendices A–H listed in report. ✓"))

    return findings
