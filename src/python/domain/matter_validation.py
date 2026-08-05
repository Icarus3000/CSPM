from __future__ import annotations

import re
from typing import Any
from domain.client_validation import looks_like_email, is_valid_iso_date

def validate_matter_payload(payload: dict[str, Any]) -> list[str]:
    issues = []
    
    matter_name = str(payload.get("matterName") or "").strip()
    if not matter_name:
        issues.append("Matter Name is required.")
        
    client_name = str(payload.get("clientName") or "").strip()
    if not client_name:
        issues.append("Client is required.")
        
    billing_email = str(payload.get("billingEmail") or "").strip()
    if billing_email and not looks_like_email(billing_email):
        issues.append("Billing Email is not in a valid email format.")
        
    dates = [
        {"label": "Date Of Engagement", "value": payload.get("dateOfEngagement")},
        {"label": "Date Opened", "value": payload.get("dateOpened")},
        {"label": "Date Closed", "value": payload.get("dateClosed")},
    ]
    for d in dates:
        val = str(d["value"] or "").strip()
        if val and not is_valid_iso_date(val):
            issues.append(f"{d['label']} must be in YYYY-MM-DD format.")
            
    date_opened = str(payload.get("dateOpened") or "").strip()
    date_closed = str(payload.get("dateClosed") or "").strip()
    
    if is_valid_iso_date(date_opened) and is_valid_iso_date(date_closed):
        if date_opened and date_closed and date_closed < date_opened:
            issues.append("Date Closed cannot be earlier than Date Opened.")
            
    try:
        def_rate = float(payload.get("defaultRate", 0))
        if def_rate < 0:
            issues.append("Default Rate must be a number greater than or equal to 0.")
    except (ValueError, TypeError):
        issues.append("Default Rate must be a number greater than or equal to 0.")
        
    try:
        def_share = float(payload.get("defaultShare", 0))
        if def_share < 0 or def_share > 100:
            issues.append("Default Share % must be between 0 and 100.")
    except (ValueError, TypeError):
        issues.append("Default Share % must be between 0 and 100.")
        
    return issues
