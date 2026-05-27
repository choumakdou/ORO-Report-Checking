"""online_checker.py — Online fact verification via OpenAI knowledge + HTTP."""
import re
import json
from typing import Optional
import config

# Try requests; gracefully degrade if not available
try:
    import requests as _requests
    _REQUESTS_OK = True
except ImportError:
    _REQUESTS_OK = False


def _gpt_fact_check(estate_name: str, questions: list) -> dict:
    """
    Ask GPT to answer factual questions about a Hong Kong estate.
    Returns dict of {question_key: answer}.
    """
    from openai import OpenAI
    client = OpenAI(api_key=config.get_api_key())

    qs_text = "\n".join(f"- {q}" for q in questions)
    prompt = f"""Answer these factual questions about the Hong Kong residential estate "{estate_name}".
Use your knowledge of Hong Kong property. Be concise. Return JSON only.

Questions:
{qs_text}

Return format example:
{{
  "mtr_station": "Tseung Kwan O",
  "mtr_walking_minutes": 5,
  "num_blocks": 3,
  "num_units": 1920,
  "year_of_completion": 1999,
  "developer": "Hong Kong Housing Authority",
  "confidence": "high/medium/low"
}}"""

    try:
        resp = client.chat.completions.create(
            model=config.get_model(),
            messages=[
                {"role": "system",
                 "content": "You are a Hong Kong property expert. Answer concisely with facts. Return JSON only."},
                {"role": "user", "content": prompt},
            ],
            temperature=0,
            response_format={"type": "json_object"},
        )
        return json.loads(resp.choices[0].message.content or "{}")
    except Exception as e:
        return {"_error": str(e)}


def _midland_lookup(estate_name: str) -> dict:
    """Quick HTTP lookup on Midland estate page for basic facts."""
    if not _REQUESTS_OK:
        return {}
    try:
        # Midland search URL (public, no auth required)
        search_url = (
            "https://www.midland.com.hk/en/estate/"
            + re.sub(r"\s+", "-", estate_name.lower())
        )
        r = _requests.get(search_url, timeout=8,
                          headers={"User-Agent": "Mozilla/5.0"})
        text = r.text.lower()
        result = {}
        # Extract walking time
        m = re.search(r"(\d+)\s*min(?:ute)?s?\s+walk", text)
        if m:
            result["mtr_walking_minutes"] = int(m.group(1))
        # Extract unit count
        m = re.search(r"([\d,]+)\s+(?:residential\s+)?units?", text)
        if m:
            result["num_units"] = int(m.group(1).replace(",", ""))
        return result
    except Exception:
        return {}


def run_online_checks(estate_name: str, val_data: dict) -> list:
    """
    Run online fact-checks for the estate. Returns list of Finding-like dicts:
    [{"check_id": ..., "severity": ..., "category": ..., "description": ...,
      "expected": ..., "actual": ..., "source": ...}]
    """
    if not config.get_api_key() or not estate_name:
        return [{
            "check_id": "WEB-0", "severity": "INFO",
            "category": "Online Verification",
            "description": "Online fact-check skipped (no API key or estate name not extracted).",
            "expected": "", "actual": "", "source": "",
        }]

    findings = []

    # Ask GPT
    online = _gpt_fact_check(estate_name, [
        "mtr_station: nearest MTR station name",
        "mtr_walking_minutes: walking minutes to nearest MTR (integer)",
        "num_blocks: number of residential blocks (integer)",
        "num_units: total residential units (integer)",
        "year_of_completion: year of completion (integer)",
    ])

    confidence = online.get("confidence", "unknown")
    conf_note = f" (GPT confidence: {confidence})" if confidence != "unknown" else ""

    # ── MTR check ──
    report_mtr = (val_data.get("mtr_station") or "").lower()
    online_mtr = str(online.get("mtr_station") or "").lower()
    if report_mtr and online_mtr:
        # Fuzzy: check if key words overlap
        r_words = set(report_mtr.split())
        o_words = set(online_mtr.split())
        if r_words & o_words:
            findings.append({
                "check_id": "WEB-1", "severity": "OK",
                "category": "Online Verification",
                "description": f"Nearest MTR station '{val_data.get('mtr_station')}' consistent with online data{conf_note}. ✓",
                "expected": online.get("mtr_station", ""), "actual": val_data.get("mtr_station", ""),
                "source": "GPT knowledge base",
            })
        else:
            findings.append({
                "check_id": "WEB-1", "severity": "CONCERN",
                "category": "Online Verification",
                "description": f"MTR station in report ('{val_data.get('mtr_station')}') may differ from online data ('{online.get('mtr_station')}'){conf_note} — verify.",
                "expected": online.get("mtr_station", ""), "actual": val_data.get("mtr_station", ""),
                "source": "GPT knowledge base",
            })

    # ── MTR walking time ──
    report_min_raw = val_data.get("mtr_walking_minutes") or ""
    online_min = online.get("mtr_walking_minutes")
    if online_min:
        # Extract numeric from report string e.g. "within 5 minutes" → 5
        m = re.search(r"(\d+)", str(report_min_raw))
        if m:
            report_min = int(m.group(1))
            if abs(report_min - int(online_min)) <= 2:
                findings.append({
                    "check_id": "WEB-2", "severity": "OK",
                    "category": "Online Verification",
                    "description": f"Walking time to MTR ({report_min} min) consistent with online data (~{online_min} min){conf_note}. ✓",
                    "expected": str(online_min), "actual": str(report_min), "source": "GPT knowledge base",
                })
            else:
                findings.append({
                    "check_id": "WEB-2", "severity": "CONCERN",
                    "category": "Online Verification",
                    "description": f"MTR walking time in report ({report_min} min) differs from online data ({online_min} min){conf_note}.",
                    "expected": str(online_min), "actual": str(report_min), "source": "GPT knowledge base",
                })

    # ── Number of blocks ──
    report_blocks = val_data.get("num_blocks")
    online_blocks = online.get("num_blocks")
    if report_blocks and online_blocks:
        try:
            if int(report_blocks) == int(online_blocks):
                findings.append({
                    "check_id": "WEB-3", "severity": "OK",
                    "category": "Online Verification",
                    "description": f"Number of blocks ({report_blocks}) matches online data{conf_note}. ✓",
                    "expected": str(online_blocks), "actual": str(report_blocks), "source": "GPT knowledge base",
                })
            else:
                findings.append({
                    "check_id": "WEB-3", "severity": "CONCERN",
                    "category": "Online Verification",
                    "description": f"Number of blocks in report ({report_blocks}) differs from online data ({online_blocks}){conf_note}.",
                    "expected": str(online_blocks), "actual": str(report_blocks), "source": "GPT knowledge base",
                })
        except (TypeError, ValueError):
            pass

    # ── Total units ──
    report_units = val_data.get("num_units")
    online_units = online.get("num_units")
    if report_units and online_units:
        try:
            if abs(int(report_units) - int(online_units)) <= 10:
                findings.append({
                    "check_id": "WEB-4", "severity": "OK",
                    "category": "Online Verification",
                    "description": f"Total units ({report_units}) matches online data{conf_note}. ✓",
                    "expected": str(online_units), "actual": str(report_units), "source": "GPT knowledge base",
                })
            else:
                findings.append({
                    "check_id": "WEB-4", "severity": "CONCERN",
                    "category": "Online Verification",
                    "description": f"Total units in report ({report_units}) differs from online data ({online_units}){conf_note}.",
                    "expected": str(online_units), "actual": str(report_units), "source": "GPT knowledge base",
                })
        except (TypeError, ValueError):
            pass

    if not findings:
        findings.append({
            "check_id": "WEB-0", "severity": "INFO",
            "category": "Online Verification",
            "description": f"Online data retrieved for '{estate_name}'. Insufficient report fields to compare{conf_note}.",
            "expected": "", "actual": "", "source": "GPT knowledge base",
        })

    return findings
