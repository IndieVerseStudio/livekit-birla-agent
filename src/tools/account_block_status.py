"""
Account Block Status tool for Birla Opus Customer Care (LiveKit Version).

Looks up a customer (by Opus ID or mobile) in mock_extended.csv and evaluates
their block status, computing clear next-step recommendations for the agent.
"""

import csv
import os
from datetime import datetime, timedelta
from typing import Any, Dict, Optional
from livekit.agents import function_tool, RunContext


def _get_data_file_path() -> str:
    """Get the absolute path to the extended mock data file."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(current_dir))
    return os.path.join(project_root, "data/mock_extended.csv")


def _clean_phone(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    digits = ''.join(ch for ch in str(value) if ch.isdigit())
    return digits if digits else None


def _clean_opus(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    digits = ''.join(ch for ch in str(value) if ch.isdigit())
    return digits if digits else None


def _parse_block_date(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    s = str(value).strip()
    # Try common formats present in dataset
    fmts = [
        "%d/%m/%y %H:%M",
        "%d/%m/%Y %H:%M",
        "%d/%m/%y",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    ]
    for fmt in fmts:
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            continue
    return None


def _status_label(code: str) -> str:
    mapping = {
        "U": "Unblocked",
        "A": "Automatic Block",
        "M": "Manual Block",
        "P": "Permanent Block",
    }
    return mapping.get((code or "").upper(), "Unknown")


def _block_through_label(code: Optional[str]) -> Optional[str]:
    if not code:
        return None
    c = str(code).strip().upper()
    mapping = {
        "O": "OTP related activity",
        "S": "Suspicious/Incorrect scans",
    }
    return mapping.get(c, None)


def check_account_block_status(
    opus_id: Optional[str] = None,
    mobile_number: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Check a customer's account block status and recommend next steps.

    Args:
        opus_id: Opus/UID (digits expected)
        mobile_number: 10-digit mobile number

    Returns:
        A dictionary containing customer, block status, timeline evaluation, and advice for the agent.
    """
    try:
        if not opus_id and not mobile_number:
            return {
                "success": False,
                "error": "Provide opus_id or mobile_number",
            }

        def _normalize_opus_digits(raw: Optional[str]) -> Optional[str]:
            d = _clean_opus(raw)
            if not d:
                return None
            # Zero-pad to 6 digits to align with PC-XXXXXX semantics
            return d.zfill(6)

        query_opus = _normalize_opus_digits(opus_id) if opus_id else None
        query_phone = _clean_phone(mobile_number) if mobile_number else None

        data_file = _get_data_file_path()
        if not os.path.exists(data_file):
            return {
                "success": False,
                "error": f"Extended customer data file not found at {data_file}",
            }

        matched_row: Optional[Dict[str, str]] = None

        # Prefer opus match when provided, then fall back to phone
        with open(data_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        if query_opus:
            for row in rows:
                # Match either numeric opus_id (unpadded) or PC-formatted opus_pc_id
                row_opus_digits = _normalize_opus_digits(row.get('opus_id'))
                row_pc_digits = _normalize_opus_digits(row.get('opus_pc_id'))
                if row_opus_digits == query_opus or row_pc_digits == query_opus:
                    matched_row = row
                    break

        if matched_row is None and query_phone:
            for row in rows:
                row_phone = _clean_phone(row.get('mobile_number'))
                if row_phone == query_phone:
                    matched_row = row
                    break

        if not matched_row:
            return {
                "success": True,
                "customer_found": False,
                "message": "No matching customer found",
                "query": {"opus_id": opus_id, "mobile_number": mobile_number},
            }

        # Extract key fields
        customer_name = f"{matched_row.get('first_name', '').strip()} {matched_row.get('last_name', '').strip()}".strip()
        found_opus = matched_row.get('opus_id', '')
        found_phone = matched_row.get('mobile_number', '')
        block_status = (matched_row.get('block_status') or '').strip().upper()
        block_status_date_raw = matched_row.get('block_status_date')
        block_status_by = matched_row.get('block_status_by')
        block_through = (matched_row.get('block_through') or '').strip().upper() or None
        account_status = matched_row.get('status', '')
        kyc_status = matched_row.get('kyc_status', '')

        block_dt = _parse_block_date(block_status_date_raw)
        hours_since_block: Optional[int] = None
        expected_auto_unblock_at: Optional[str] = None
        expected_auto_unblock_date: Optional[str] = None
        if block_dt:
            delta = datetime.now() - block_dt
            hours_since_block = int(delta.total_seconds() // 3600)
            expected_dt = block_dt + timedelta(hours=48)
            expected_auto_unblock_at = expected_dt.strftime("%Y-%m-%d %H:%M")
            expected_auto_unblock_date = expected_dt.strftime("%Y-%m-%d")

        advice = []
        message = ""
        recommendation = None  # wait | complaint | none
        timeline_info: Dict[str, Any] = {}

        status_label = _status_label(block_status)
        through_label = _block_through_label(block_through)

        if block_status == 'U' or block_status == '':
            message = "Account is currently not blocked."
            recommendation = "none"
            advice.append({"type": "NOT_BLOCKED"})
        elif block_status == 'A':
            # Automatic block: 48-hour auto removal policy
            if hours_since_block is None:
                message = "Account is automatically blocked. Exact block time is unavailable; advise waiting up to 48 hours."
                recommendation = "wait"
                advice.append({"type": "WAIT_UNTIL_48_HOURS", "next_action": "create_enquiry_tool"})
            elif hours_since_block < 48:
                reason_msg = (
                    "due to multiple incorrect scans" if block_through == 'S' else (
                        "due to OTP-related activity" if block_through == 'O' else "automatically"
                    )
                )
                message = (
                    f"Account was auto-blocked {hours_since_block} hour(s) ago {reason_msg}. "
                    f"It should auto-unblock by {expected_auto_unblock_at}. Please wait until 48 hours are complete."
                )
                recommendation = "wait"
                advice.append({
                    "type": "WAIT_UNTIL_48_HOURS",
                    "reason": through_label,
                    "expected_unblock_at": expected_auto_unblock_at,
                    "expected_unblock_date": expected_auto_unblock_date,
                    "next_action": "create_enquiry_tool",
                })
                if block_through == 'S':
                    advice.append({"type": "GUIDE_SCAN_PRACTICES"})
                if block_through == 'O':
                    advice.append({"type": "GUIDE_OTP_PRACTICES"})
            else:
                message = (
                    "Automatic block has exceeded 48 hours. Raise a complaint so the backend team can investigate; "
                    "resolution within 7 days."
                )
                recommendation = "complaint"
                advice.append({
                    "type": "RAISE_COMPLAINT_OVER_48_HOURS",
                    "timeline_days": 7,
                    "next_action": "create_complaint_tool",
                })
        elif block_status == 'M':
            when = block_dt.strftime("%Y-%m-%d") if block_dt else "the recorded date"
            message = (
                f"Account is manually blocked by backend on {when}. It does not auto-unblock. "
                "Raising a complaint; final decision rests with the TSM."
            )
            recommendation = "complaint"
            advice.append({
                "type": "RAISE_COMPLAINT_MANUAL_BLOCK",
                "tsm_decision": True,
                "timeline_days": 7,
                "next_action": "create_complaint_tool",
            })
        elif block_status == 'P':
            message = (
                "Account is permanently blocked (usually after multiple auto-bans). "
                "Raising a complaint for backend investigation; expected resolution within 7 days."
            )
            recommendation = "complaint"
            advice.append({
                "type": "RAISE_COMPLAINT_PERMANENT_BLOCK",
                "timeline_days": 7,
                "next_action": "create_complaint_tool",
            })
        else:
            message = "Block status is unknown. Raising an investigation complaint is recommended."
            recommendation = "complaint"
            advice.append({"type": "UNKNOWN_BLOCK_STATUS", "next_action": "create_complaint_tool"})

        if expected_auto_unblock_at:
            timeline_info["expected_auto_unblock_at"] = expected_auto_unblock_at
        if expected_auto_unblock_date:
            timeline_info["expected_auto_unblock_date"] = expected_auto_unblock_date
        if hours_since_block is not None:
            timeline_info["hours_since_block"] = hours_since_block
        if block_dt:
            timeline_info["block_date"] = block_dt.strftime("%Y-%m-%d %H:%M")

        return {
            "success": True,
            "query": {"opus_id": opus_id, "mobile_number": mobile_number},
            "customer": {
                "name": customer_name,
                "opus_id": found_opus,
                "mobile_number": found_phone,
                "kyc_status": kyc_status,
                "account_status": account_status,
            },
            "block": {
                "status": block_status,
                "status_label": status_label,
                "block_status_date": block_status_date_raw,
                "block_status_by": block_status_by,
                "block_through": block_through,
                "block_through_label": through_label,
            },
            "timeline_info": timeline_info,
            "recommendation": recommendation,
            "message": message,
            "advice": advice,
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error checking account block status: {str(e)}",
        }


# Export the main function for LiveKit use
# The agent.py will wrap this with @function_tool() decorator
account_block_status_func = check_account_block_status

@function_tool()
async def account_block_status_tool(context: RunContext, 
                                    opus_id: str = None,
                                    mobile_number: str = None) -> dict:
    """Check account block status and provide recommendations."""
    return account_block_status_func(opus_id=opus_id, mobile_number=mobile_number)

