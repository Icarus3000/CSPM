from __future__ import annotations

import re
from typing import Any

def looks_like_email(email: str) -> bool:
    email = str(email or "").strip()
    if not email:
        return True
    return bool(re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", email))

def is_valid_iso_date(text: str) -> bool:
    text = str(text or "").strip()
    if not text:
        return True
    return bool(re.match(r"^\d{4}-\d{2}-\d{2}$", text))

def validate_client_payload(payload: dict[str, Any]) -> list[str]:
    issues = []
    
    # Client Name Check
    client_name = str(payload.get("clientName") or "").strip()
    if not client_name:
        issues.append("Client Name is required.")
        
    # Phone Checks
    phones = [
        {"label": "Primary Phone", "value": payload.get("primaryPhone")},
        {"label": "Secondary Phone", "value": payload.get("secondaryPhone")},
    ]
    for p in phones:
        val = str(p["value"] or "").strip()
        if val:
            digits = re.sub(r"\D", "", val)
            if len(digits) == 11 and digits.startswith("1"):
                digits = digits[1:]
            if len(digits) != 10:
                issues.append(f"{p['label']} must use 10 digits (xxx-xxx-xxxx).")
                
    # Email Checks
    emails = [
        {"label": "Primary Email", "value": payload.get("primaryEmail")},
        {"label": "Secondary Email", "value": payload.get("secondaryEmail")},
        {"label": "Billing Email", "value": payload.get("billingEmail")},
    ]
    for e in emails:
        val = str(e["value"] or "").strip()
        if val and not looks_like_email(val):
            issues.append(f"{e['label']} is not in a valid email format.")
            
    # Date Checks
    dates = [
        {"label": "Engagement Start", "value": payload.get("engagementStart")},
        {"label": "Date Client Added", "value": payload.get("dateClientAdded")},
        {"label": "Birthday", "value": payload.get("birthday")},
    ]
    for d in dates:
        val = str(d["value"] or "").strip()
        if val and not is_valid_iso_date(val):
            issues.append(f"{d['label']} must be in YYYY-MM-DD format.")
            
    # Retainer Check
    retainer_required = str(payload.get("retainerRequired") or "").strip().lower()
    if retainer_required == "yes":
        try:
            amt = float(payload.get("retainerAmount", 0))
            if amt <= 0:
                issues.append("Retainer Amount must be greater than 0 when Retainer Required is Yes.")
        except ValueError:
            issues.append("Retainer Amount must be greater than 0 when Retainer Required is Yes.")
            
    return issues
