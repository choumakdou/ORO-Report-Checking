"""report_generator.py — Generate PDF QC report using reportlab."""
import os
import datetime
from typing import List

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether
)
from reportlab.platypus import PageBreak

from rule_checker import Finding

# ── Colours ──────────────────────────────────────────────────────────────────
C_NAVY    = colors.HexColor("#1a3a5c")
C_RED     = colors.HexColor("#c0392b")
C_AMBER   = colors.HexColor("#d97706")
C_GREEN   = colors.HexColor("#16a34a")
C_BLUE    = colors.HexColor("#2563eb")
C_RED_BG  = colors.HexColor("#fdf2f0")
C_AMB_BG  = colors.HexColor("#fefce8")
C_GRN_BG  = colors.HexColor("#f0fdf4")
C_BLU_BG  = colors.HexColor("#eff6ff")
C_LGREY   = colors.HexColor("#f0f4f8")
C_WHITE   = colors.white

SEV_STYLE = {
    "ERROR":   {"bg": C_RED_BG,  "border": C_RED,   "badge_bg": C_RED,   "label": "ERROR"},
    "CONCERN": {"bg": C_AMB_BG,  "border": C_AMBER,  "badge_bg": C_AMBER, "label": "CONCERN"},
    "OK":      {"bg": C_GRN_BG,  "border": C_GREEN,  "badge_bg": C_GREEN, "label": "VERIFIED"},
    "INFO":    {"bg": C_BLU_BG,  "border": C_BLUE,   "badge_bg": C_BLUE,  "label": "INFO"},
}

W, H = A4


def _styles():
    base = getSampleStyleSheet()
    def ps(name, **kw):
        return ParagraphStyle(name, parent=base["Normal"], **kw)

    return {
        "title":    ps("t", fontSize=18, textColor=C_NAVY, fontName="Helvetica-Bold",
                       leading=22, spaceAfter=2),
        "meta":     ps("m", fontSize=8.5, textColor=colors.white, leading=13),
        "sec":      ps("s", fontSize=10.5, textColor=C_NAVY, fontName="Helvetica-Bold",
                       leading=14, spaceBefore=12, spaceAfter=4),
        "body":     ps("b", fontSize=9, leading=14),
        "small":    ps("sm", fontSize=8, textColor=colors.HexColor("#555555"), leading=12),
        "badge":    ps("bd", fontSize=7.5, textColor=C_WHITE, fontName="Helvetica-Bold",
                       leading=10),
        "detail":   ps("dt", fontSize=8, textColor=colors.HexColor("#444444"), leading=12),
        "footer":   ps("ft", fontSize=7.5, textColor=colors.HexColor("#999999"),
                       alignment=TA_CENTER, leading=11),
    }


def _badge_cell(label: str, bg: colors.Color) -> Table:
    """Render a coloured badge as a mini-table cell."""
    t = Table([[Paragraph(f"<b>{label}</b>",
                          ParagraphStyle("_b", fontSize=7, textColor=C_WHITE,
                                         fontName="Helvetica-Bold", leading=9))]],
              colWidths=[18*mm], rowHeights=[5*mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), bg),
        ("ALIGN",      (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
    ]))
    return t


def _finding_table(f: Finding, styles: dict, usable_w: float) -> KeepTogether:
    """Render one finding as a coloured row table."""
    s = SEV_STYLE.get(f.severity, SEV_STYLE["INFO"])

    badge = _badge_cell(s["label"], s["badge_bg"])
    desc_text = f.description
    if f.expected:
        desc_text += f"<br/><font size='8' color='#555555'><b>Expected:</b> {f.expected[:120]}</font>"
    if f.actual:
        desc_text += f"<br/><font size='8' color='#555555'><b>Found:</b> {f.actual[:120]}</font>"
    if f.source:
        desc_text += f"<br/><font size='8' color='#555555'><b>Source:</b> {f.source}</font>"

    desc = Paragraph(desc_text, styles["body"])

    data = [[badge, desc]]
    t = Table(data, colWidths=[20*mm, usable_w - 20*mm])
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), s["bg"]),
        ("LINEAFTER",     (0, 0), (0, 0),   0.5, s["border"]),
        ("LINEBEFORE",    (0, 0), (0, 0),   2.5, s["border"]),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 4),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 4),
    ]))
    return KeepTogether([t, Spacer(1, 2)])


def generate_pdf_report(
    findings: List[Finding],
    online_findings: list,
    property_address: str,
    oro_ref: str,
    chft_ref: str,
    output_path: str,
    extracted_data: dict = None,
    folder_scan: dict = None,
) -> str:
    """Generate a PDF QC report. Returns output_path."""

    styles = _styles()
    now = datetime.datetime.now().strftime("%d %B %Y  %H:%M")

    # Merge online findings as Finding objects
    all_findings = list(findings)
    for of in (online_findings or []):
        all_findings.append(Finding(
            severity=of.get("severity", "INFO"),
            category=of.get("category", "Online Verification"),
            check_id=of.get("check_id", "WEB"),
            description=of.get("description", ""),
            expected=of.get("expected", ""),
            actual=of.get("actual", ""),
            source=of.get("source", ""),
        ))

    errors   = [f for f in all_findings if f.severity == "ERROR"]
    concerns = [f for f in all_findings if f.severity == "CONCERN"]
    oks      = [f for f in all_findings if f.severity == "OK"]

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=18*mm, rightMargin=18*mm,
        topMargin=18*mm, bottomMargin=18*mm,
        title="ORO QC Report",
        author="CHFT Advisory and Appraisal Ltd.",
    )
    usable_w = W - 36*mm
    story = []

    # ── Header block ──────────────────────────────────────────────────────────
    hdr_data = [[
        Paragraph("<b>ORO Valuation QC Report</b>",
                  ParagraphStyle("_h", fontSize=14, textColor=C_WHITE,
                                 fontName="Helvetica-Bold", leading=18)),
        Paragraph(
            f"Property: {property_address}<br/>"
            f"ORO Ref: {oro_ref} &nbsp;&nbsp; CHFT Ref: {chft_ref}<br/>"
            f"Generated: {now}",
            ParagraphStyle("_hm", fontSize=8.5, textColor=C_WHITE, leading=13)),
    ]]
    hdr_t = Table(hdr_data, colWidths=[60*mm, usable_w - 60*mm])
    hdr_t.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), C_NAVY),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
    ]))
    story.append(hdr_t)
    story.append(Spacer(1, 6*mm))

    # ── Summary row ───────────────────────────────────────────────────────────
    def sum_cell(num, label, bg, txt_color):
        return [
            Paragraph(f"<b>{num}</b>",
                      ParagraphStyle("_n", fontSize=20, textColor=txt_color,
                                     fontName="Helvetica-Bold", alignment=TA_CENTER, leading=24)),
            Paragraph(label,
                      ParagraphStyle("_l", fontSize=8, textColor=txt_color,
                                     alignment=TA_CENTER, leading=11)),
        ]

    sum_data = [
        [sum_cell(len(errors),   "ERRORS",   C_RED_BG,  C_RED),
         sum_cell(len(concerns), "CONCERNS", C_AMB_BG,  C_AMBER),
         sum_cell(len(oks),      "VERIFIED", C_GRN_BG,  C_GREEN)],
    ]
    # Flatten nested lists
    flat = [[
        Table([[r[0]], [r[1]]], colWidths=[40*mm]) for r in sum_data[0]
    ]]
    for i, cell_tbl in enumerate(flat[0]):
        cell_tbl.setStyle(TableStyle([
            ("ALIGN",  (0, 0), (-1, -1), "CENTER"),
            ("BACKGROUND", (0, 0), (-1, -1),
             [C_RED_BG, C_AMB_BG, C_GRN_BG][i]),
            ("TOPPADDING",    (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
    sum_t = Table([flat[0]], colWidths=[usable_w / 3] * 3)
    sum_t.setStyle(TableStyle([
        ("ALIGN",  (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, C_LGREY),
        ("BOX",       (0, 0), (-1, -1), 0.5, C_LGREY),
    ]))
    story.append(sum_t)
    story.append(Spacer(1, 6*mm))

    # ── Documents used ────────────────────────────────────────────────────────
    if folder_scan:
        sup = folder_scan.get("supporting", {})
        excl = folder_scan.get("excluded_reports", [])
        rows = []
        type_labels = {
            "land_register": "Land Register",
            "rvd": "RVD Printout",
            "assignment": "Assignment",
            "instruction_letter": "Instruction Letter",
        }
        for k, label in type_labels.items():
            v = sup.get(k)
            val = os.path.basename(v) if v else "— not found"
            rows.append([label, val])
        for p in sup.get("unknown", []):
            rows.append(["Other", os.path.basename(p)])
        for p in excl:
            rows.append(["Excluded (report draft)", os.path.basename(p)])
        if rows:
            story.append(Paragraph("Documents Used", styles["sec"]))
            doc_t = Table(
                [[Paragraph(r[0], styles["small"]),
                  Paragraph(r[1], styles["small"])] for r in rows],
                colWidths=[40*mm, usable_w - 40*mm],
            )
            doc_t.setStyle(TableStyle([
                ("BACKGROUND",    (0, 0), (-1, -1), C_LGREY),
                ("ROWBACKGROUNDS",(0, 0), (-1, -1), [C_WHITE, C_LGREY]),
                ("GRID",          (0, 0), (-1, -1), 0.3, colors.HexColor("#dde3ea")),
                ("TOPPADDING",    (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING",   (0, 0), (-1, -1), 5),
            ]))
            story.append(doc_t)
            story.append(Spacer(1, 5*mm))

    # ── Extracted data summary ────────────────────────────────────────────────
    if extracted_data:
        val = extracted_data.get("valuation", {})
        fields = [
            ("Block in §2.1",      val.get("block_letter_in_s2_1")),
            ("Saleable Area",       f"{val.get('saleable_area_sqft')} sqft / {val.get('saleable_area_sqm')} sq m"
                                    if val.get("saleable_area_sqft") else None),
            ("Year of Completion",  val.get("year_of_completion")),
            ("Date of Valuation",   val.get("date_of_valuation")),
            ("Inspector",           val.get("inspector_name")),
            ("Signatory",           f"{val.get('signatory_name','')} {val.get('signatory_quals','')}".strip()),
            ("OM Value 100%",       f"HK${int(val['om_value_100']):,}" if val.get("om_value_100") else None),
            ("OM Value 50%",        f"HK${int(val['om_value_50']):,}" if val.get("om_value_50") else None),
            ("HOSSMS Value 100%",   f"HK${int(val['hossms_value_100']):,}" if val.get("hossms_value_100") else None),
            ("HOSSMS Value 50%",    f"HK${int(val['hossms_value_50']):,}" if val.get("hossms_value_50") else None),
        ]
        rows = [[k, str(v)] for k, v in fields if v and str(v).strip() not in ("", "None")]
        if rows:
            story.append(Paragraph("Extracted Report Data", styles["sec"]))
            d_t = Table(
                [[Paragraph(r[0], styles["small"]),
                  Paragraph(r[1], styles["body"])] for r in rows],
                colWidths=[45*mm, usable_w - 45*mm],
            )
            d_t.setStyle(TableStyle([
                ("ROWBACKGROUNDS", (0, 0), (-1, -1), [C_WHITE, C_LGREY]),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#dde3ea")),
                ("TOPPADDING",    (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING",   (0, 0), (-1, -1), 5),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ]))
            story.append(d_t)
            story.append(Spacer(1, 5*mm))

    # ── Findings by category ──────────────────────────────────────────────────
    categories: dict = {}
    for f in all_findings:
        categories.setdefault(f.category, []).append(f)

    for cat, items in categories.items():
        story.append(Paragraph(cat, styles["sec"]))
        story.append(HRFlowable(width="100%", thickness=1.5, color=C_NAVY, spaceAfter=3))
        for f in items:
            story.append(_finding_table(f, styles, usable_w))
        story.append(Spacer(1, 3*mm))

    # ── Footer ────────────────────────────────────────────────────────────────
    story.append(Spacer(1, 8*mm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cccccc")))
    story.append(Spacer(1, 2*mm))
    story.append(Paragraph(
        "CHFT Advisory and Appraisal Ltd.  |  ORO QC Checker  |  "
        f"Generated {now}  |  For internal use only",
        styles["footer"]))

    doc.build(story)
    return output_path
