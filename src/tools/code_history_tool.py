"""
Code History Tool for QR Scan Entries (LiveKit Version)

Provides lookup for scan history from code_history.csv by opus_pc_id or coupon_code,
and returns a structured summary the agent can use to explain outcomes.
"""

import csv
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from livekit.agents import function_tool, RunContext


def _get_data_file_path() -> str:
    """Get absolute path to code_history.csv."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(current_dir))
    return os.path.join(project_root, "data/code_history.csv")


# Reference (extended) data
def _get_reference_file_path() -> str:
    """Get absolute path to code_history_reference.csv."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(current_dir))
    return os.path.join(project_root, "data/code_history_reference.csv")


def _load_reference_map() -> Dict[str, List[Dict[str, str]]]:
    """Load reference rows keyed by code_history_id (as string)."""
    ref_path = _get_reference_file_path()
    ref_map: Dict[str, List[Dict[str, str]]] = {}
    if not os.path.exists(ref_path):
        return ref_map
    try:
        with open(ref_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                key = str(row.get("code_history_id", "")).strip()
                if not key:
                    continue
                ref_map.setdefault(key, []).append(row)
    except Exception:
        return ref_map
    return ref_map


# Map status codes to human-readable labels
STATUS_LABELS: Dict[str, str] = {
    "Y": "Success",
    "N": "Invalid (not found on server)",
    "A": "Already Used",
    "E": "Expired",
    "P": "Pending (user/badge pending)",
    "R": "Rejected (Badge Approval)",
    "G": "Geo Restricted (near contractor location)",
    "U": "Unmapped Loyalty Product Points",
    "X": "Deactivated (Self-Enrollment)",
    "Z": "Rejected (Self-Enrollment)",
    "V": "Inactive",
    "I": "Invalid",
    "B": "Non-Birla Opus Entry",
    "O": "Outer container loyalty code",
}


def _normalize_opus_pc_id(raw: Optional[str]) -> Optional[str]:
    """Normalize various opus id formats to standard PC-XXXXXX.

    Accepts values like "89012", "089012", or "PC-089012" and returns "PC-089012".
    If no digits are present, returns the original string.
    """
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    if s.upper().startswith("PC-"):
        return s
    digits = ''.join(ch for ch in s if ch.isdigit())
    if not digits:
        return s
    if len(digits) < 6:
        digits = digits.zfill(6)
    return f"PC-{digits}"


def _parse_dt(value: str) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    except Exception:
        return None


def _to_int(value: str) -> int:
    try:
        if value is None or value == "":
            return 0
        # Some CSVs may store as float-like strings
        return int(float(value))
    except Exception:
        return 0


def _row_to_entry(row: Dict[str, str]) -> Dict[str, Any]:
    status = row.get("status", "")
    coupon_type = row.get("coupon_type", "")
    earn_point = _to_int(row.get("earn_point", "0"))

    return {
        "id": row.get("id"),
        "opus_pc_id": row.get("opus_pc_id"),
        "category_id": row.get("category_id"),
        "coupon_code": row.get("coupon_code"),
        "coupon_type": coupon_type,  # 'L' or 'C'
        "status": status,
        "status_label": STATUS_LABELS.get(status, "Unknown"),
        "pack_code": row.get("pack_code"),
        "earn_point": earn_point,
        "product_code": row.get("product_code"),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
        "deleted_at": row.get("deleted_at"),
        "created_by": row.get("created_by"),
        "updated_by": row.get("updated_by"),
        "deleted_by": row.get("deleted_by"),
    }


def _sort_key(row: Dict[str, str]) -> Tuple[Optional[datetime], Optional[datetime]]:
    # Sort primarily by updated_at, then created_at
    return (
        _parse_dt(row.get("updated_at", "")) or _parse_dt(row.get("created_at", "")),
        _parse_dt(row.get("created_at", "")),
    )


def query_code_history(
    opus_pc_id: Optional[str] = None,
    coupon_code: Optional[str] = None,
    limit: Optional[int] = None,
    order: Optional[str] = None,
    user_type: Optional[str] = None,
    caller_opus_pc_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Query code history by opus_pc_id or coupon_code.

    Also enriches with reference data and provides conversational messages and advice.

    Args:
        opus_pc_id: The opus_pc_id to filter by.
        coupon_code: The coupon_code to filter by.
        limit: The maximum number of records to return.
        order: The sort order for records ('asc' or 'desc').
        user_type: 'PAINTER' or 'CONTRACTOR' to check for code-type mismatch.
        caller_opus_pc_id: The caller's opus_pc_id for ownership checks.

    Returns:
        Dictionary with entries, summary, and message/advice suitable for agent consumption.
    """
    # Handle default values internally
    limit = limit if limit is not None else 50
    order = order if order is not None else "desc"

    if not opus_pc_id and not coupon_code:
        return {"success": False, "error": "Either opus_pc_id or coupon_code must be provided"}

    try:
        data_file = _get_data_file_path()
        if not os.path.exists(data_file):
            return {
                "success": False,
                "error": f"Code history file not found at {data_file}",
            }

        rows: List[Dict[str, str]] = []
        with open(data_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if opus_pc_id and row.get("opus_pc_id") != opus_pc_id:
                    continue
                if coupon_code and row.get("coupon_code") != coupon_code:
                    continue
                rows.append(row)

        # If we need complete code-level history (e.g., already-scanned checks), gather all rows for this code
        code_rows: List[Dict[str, str]] = []
        if coupon_code:
            with open(data_file, "r", encoding="utf-8") as f2:
                reader2 = csv.DictReader(f2)
                for r in reader2:
                    if r.get("coupon_code") == coupon_code:
                        code_rows.append(r)

        if not rows:
            return {
                "success": False,
                "error": "No matching scan records found",
                "query": {
                    "opus_pc_id": opus_pc_id,
                    "coupon_code": coupon_code,
                },
            }

        # Sort
        rows.sort(key=_sort_key, reverse=(order.lower() != "asc"))

        # Limit
        limited_rows = rows[: max(1, limit)] if limit else rows

        # Convert to entries and compute summary
        entries = [_row_to_entry(r) for r in limited_rows]

        # Attach reference info to entries
        ref_map = _load_reference_map()
        for e in entries:
            cid = (e.get("id") or "").strip()
            ref_rows = ref_map.get(cid, [])
            # Attach a compact reference snapshot (latest row if multiple)
            if ref_rows:
                ref = ref_rows[-1]
                e["reference"] = {
                    "scan_from": ref.get("scan_from"),
                    "pincode": ref.get("pincode"),
                    "propix_response": ref.get("propix_response"),
                    "scan_method": ref.get("scan_method"),
                    "coupon_image": ref.get("coupon_image"),
                    "scan_message": ref.get("scan_message"),
                    "coupon_url": ref.get("coupon_url"),
                    "product_sku_code": ref.get("product_sku_code"),
                    "product_sku_name": ref.get("product_sku_name"),
                }
            else:
                e["reference"] = None

        counts_by_status: Dict[str, int] = {}
        loyalty_points_earned = 0
        cash_points_earned = 0

        for r in limited_rows:
            status = r.get("status", "")
            counts_by_status[status] = counts_by_status.get(status, 0) + 1
            if status == "Y":
                if r.get("coupon_type") == "L":
                    loyalty_points_earned += _to_int(r.get("earn_point", "0"))
                elif r.get("coupon_type") == "C":
                    cash_points_earned += _to_int(r.get("earn_point", "0"))

        first_dt = _parse_dt(limited_rows[-1].get("created_at", "")) if len(limited_rows) > 0 else None
        last_dt = _parse_dt(limited_rows[0].get("created_at", "")) if len(limited_rows) > 0 else None

        latest_status = limited_rows[0].get("status", "")
        latest_status_label = STATUS_LABELS.get(latest_status, "Unknown")

        summary = {
            "total_records": len(limited_rows),
            "counts_by_status": {
                code: {
                    "count": count,
                    "label": STATUS_LABELS.get(code, "Unknown"),
                }
                for code, count in counts_by_status.items()
            },
            "loyalty_points_earned": loyalty_points_earned,
            "cash_points_earned": cash_points_earned,
            "date_range": {
                "from": first_dt.isoformat(sep=" ") if first_dt else None,
                "to": last_dt.isoformat(sep=" ") if last_dt else None,
            },
            "latest": {
                "status": latest_status,
                "status_label": latest_status_label,
                "coupon_code": limited_rows[0].get("coupon_code"),
                "updated_at": limited_rows[0].get("updated_at"),
                "created_at": limited_rows[0].get("created_at"),
            },
        }

        # Build decision hints and common-case messages
        advice: List[Dict[str, Any]] = []
        caller_id = _normalize_opus_pc_id(caller_opus_pc_id or opus_pc_id)
        latest_entry = entries[0] if entries else None

        # Determine derived type by length
        code_len = len(latest_entry["coupon_code"]) if latest_entry and latest_entry.get("coupon_code") else 0
        derived_type = "L" if code_len == 12 else ("C" if code_len == 13 else None)

        # Check user_type mismatch (Contractor should scan L/12, Painter should scan C/13)
        mismatch_message = None
        if user_type and latest_entry:
            user_type_norm = user_type.strip().upper()
            expected_type = "L" if user_type_norm == "CONTRACTOR" else ("C" if user_type_norm == "PAINTER" else None)
            if expected_type:
                actual_type = latest_entry.get("coupon_type") or derived_type
                if actual_type and actual_type != expected_type:
                    mismatch_message = (
                        "Incorrect code type. Contractors must scan the outside Loyalty code (12-digit, L); "
                        "Painters must scan the inside Cash code (13-digit, C)."
                    )
                    advice.append({
                        "type": "WRONG_CODE_TYPE",
                        "user_type": user_type_norm,
                        "expected_type": expected_type,
                        "actual_type": actual_type,
                        "message": mismatch_message,
                    })

        # Ownership checks for A (already used) and Y (successful) statuses
        already_message = None
        if coupon_code and latest_entry:
            # Determine latest owner of this scan
            latest_owner = _normalize_opus_pc_id(latest_entry.get("opus_pc_id"))

            # For status A: find who scanned first successfully/used
            # For status Y: treat as already used as well; if caller != owner => someone else scanned
            if latest_status in {"A", "Y"}:
                # Examine full code history for this code
                def dt(row):
                    return _parse_dt(row.get("created_at", "")) or _parse_dt(row.get("updated_at", ""))

                prior_rows_sorted = sorted(code_rows, key=lambda r: dt(r) or datetime.min)
                own_prior = None
                other_prior = None
                for r in prior_rows_sorted:
                    if r.get("status") in {"Y", "A"}:
                        rid_owner = _normalize_opus_pc_id(r.get("opus_pc_id"))
                        if caller_id and rid_owner == caller_id and not own_prior:
                            own_prior = r
                        elif not other_prior and (not caller_id or rid_owner != caller_id):
                            other_prior = r

                # Prefer the latest known owner if lists are empty
                if not own_prior and latest_owner and caller_id == latest_owner:
                    own_prior = limited_rows[0]
                if not other_prior and latest_owner and caller_id and latest_owner != caller_id:
                    other_prior = limited_rows[0]

                if own_prior:
                    when = own_prior.get("created_at") or own_prior.get("updated_at")
                    already_message = (
                        f"This code was already scanned by you on {when}. Each code can be scanned only once."
                    )
                    advice.append({
                        "type": "DUPLICATE_SCAN_BY_SAME_USER",
                        "scanned_at": when,
                        "coupon_code": coupon_code,
                    })
                elif other_prior:
                    when = other_prior.get("created_at") or other_prior.get("updated_at")
                    who = _normalize_opus_pc_id(other_prior.get("opus_pc_id"))
                    already_message = (
                        "This code was scanned by another user. I recommend creating a complaint; our technical team will resolve within 7 days."
                    )
                    advice.append({
                        "type": "CREATE_COMPLAINT_FOR_FRAUD_SCAN",
                        "coupon_code": coupon_code,
                        "scanned_by": who,
                        "scanned_at": when,
                        "next_action": "call_create_complaint_tool",
                    })

        # Status-specific quick guidance
        status_message = None
        requires_kyc_check = False
        if latest_status == "P":
            status_message = (
                "The code is not yet updated in our database. Please try scanning again after 2–3 days."
            )
            # Pending can be due to KYC not completed
            requires_kyc_check = True
            advice.append({
                "type": "ADVISE_WAIT",
                "wait_days": 2,
                "hint": "Delay can occur if KYC is incomplete",
                "next_action": "optionally_check_kyc_status",
            })
        elif latest_status == "G":
            status_message = (
                "Geo restricted due to contractor location. Please scan from a location more than 22 meters away."
            )
            advice.append({
                "type": "GEO_RESTRICTED",
                "radius_m": 22,
            })
        elif latest_status in {"R", "Z"}:
            status_message = (
                "Profile appears rejected. First verify KYC is complete; if KYC is complete, create a complaint and suggest contacting the TSM."
            )
            requires_kyc_check = True
            advice.append({
                "type": "REJECTED_PROFILE",
                "requires_kyc_check": True,
                "next_action": "check_kyc_then_create_complaint_if_complete",
                "suggest_contact": "TSM",
            })
        elif latest_status == "E":
            status_message = "The code has expired. Points cannot be credited."

        # Camera vs Manual guidance (reference table)
        manual_message = None
        latest_ref = None
        if coupon_code and entries:
            latest_cid = (limited_rows[0].get("id") or "").strip()
            latest_ref_rows = ref_map.get(latest_cid, [])
            latest_ref_methods = { (ref.get("scan_method") or "").upper() for ref in latest_ref_rows }
            latest_ref = latest_ref_rows[-1] if latest_ref_rows else None
            # Consider only this user's history for the same code
            user_rows = [r for r in code_rows if caller_id and r.get("opus_pc_id") == caller_id]
            user_manual_found = False
            for r in user_rows:
                rid = (r.get("id") or "").strip()
                for ref in ref_map.get(rid, []):
                    if (ref.get("scan_method") or "").upper() == "M":
                        user_manual_found = True
                        break
                if user_manual_found:
                    break
            if ("C" in latest_ref_methods) and not user_manual_found:
                manual_message = (
                    "The code was scanned using the camera and no manual entry from this user is found. "
                    "Please enter the code manually in the app and call back if the issue persists."
                )
                advice.append({
                    "type": "CAMERA_USED_NO_MANUAL_TRY",
                    "next_action": "ask_user_manual_entry",
                })
            elif ("C" in latest_ref_methods) and user_manual_found:
                advice.append({
                    "type": "CAMERA_USED_AND_MANUAL_TRIED",
                })

        # Propix-response consistency hints (mapping: 200 OK->accepted, 404->pending, 500->invalid origin)
        if latest_ref:
            propix = (latest_ref.get("propix_response") or "").upper()
            if propix == "404 NOT FOUND" and latest_status != "P":
                advice.append({
                    "type": "REFERENCE_STATUS_MISMATCH",
                    "expected_status": "P",
                    "actual_status": latest_status,
                    "hint": "Server hasn't updated the code yet (404). Treat as pending.",
                })
                # Prefer pending-style message if nothing stronger selected
                if not mismatch_message and not already_message and not manual_message:
                    status_message = (
                        "The code is not yet updated in our database. Please try scanning again after 2–3 days."
                    )
            if propix == "500 ERROR":
                # 500 implies unknown source; coupon_type should be I and code may be missing
                if (latest_entry or {}).get("coupon_type") != "I":
                    advice.append({
                        "type": "EXPECTED_COUPON_TYPE_I_FOR_500",
                        "actual_coupon_type": (latest_entry or {}).get("coupon_type"),
                    })
                if (latest_entry or {}).get("coupon_code"):
                    advice.append({
                        "type": "SERVER_500_WITH_CODE_PRESENT",
                        "note": "Random/unknown source scans may not have a verifiable coupon code.",
                    })

        # Coupon length vs type sanity check (12->L, 13->C)
        if latest_entry and derived_type and latest_entry.get("coupon_type") in {"L", "C"}:
            if latest_entry["coupon_type"] != derived_type:
                advice.append({
                    "type": "COUPON_TYPE_LENGTH_MISMATCH",
                    "coupon_type": latest_entry["coupon_type"],
                    "derived_type": derived_type,
                    "coupon_code_length": code_len,
                })

        # Compose final message preference order: mismatch > already > manual > status-specific > generic summary
        if mismatch_message:
            message = mismatch_message
        elif already_message:
            message = already_message
        elif manual_message:
            message = manual_message
        elif status_message:
            message = status_message
        else:
            message = (
                f"Latest status: {latest_status_label}. "
                f"Total scans: {len(limited_rows)}. "
                f"Earned L:{loyalty_points_earned} / C:{cash_points_earned} points (status=Y)."
            )

        return {
            "success": True,
            "query": {
                "opus_pc_id": opus_pc_id,
                "coupon_code": coupon_code,
                "limit": limit,
                "order": order,
                "user_type": user_type,
                "caller_opus_pc_id": caller_opus_pc_id,
            },
            "entries": entries,
            "summary": summary,
            "message": message,
            "advice": advice,
            "requires_kyc_check": requires_kyc_check,
            "derived": {
                "coupon_code_length": code_len,
                "derived_type": derived_type,
            },
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"Error reading code history: {str(e)}",
        }


# Export the main function for LiveKit use
# The agent.py will wrap this with @function_tool() decorator
query_code_history_func = query_code_history

@function_tool()
async def code_history_tool(context: RunContext, 
                            opus_pc_id: str = None,
                            coupon_code: str = None,
                            limit: int = None,
                            order: str = None,
                            user_type: str = None,
                            caller_opus_pc_id: str = None) -> dict:
    """Query code history by opus_pc_id or coupon_code for QR scanning issues."""
    return query_code_history_func(
        opus_pc_id=opus_pc_id,
        coupon_code=coupon_code,
        limit=limit,
        order=order,
        user_type=user_type,
        caller_opus_pc_id=caller_opus_pc_id
        )