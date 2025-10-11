"""
Cash Transfer History Tool (LiveKit Version)

Provides the last N cash transfer requests for a given opus_pc_id from
data/cash_transfer.csv and enriches with reference info from
data/cash_transfer_reference.csv.
"""

import csv
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from livekit.agents import function_tool, RunContext


def _get_cash_transfer_file_path() -> str:
    """Get absolute path to cash_transfer.csv."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(current_dir))
    return os.path.join(project_root, "data/cash_transfer.csv")


def _get_cash_transfer_reference_file_path() -> str:
    """Get absolute path to cash_transfer_reference.csv."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(current_dir))
    return os.path.join(project_root, "data/cash_transfer_reference.csv")


def _normalize_opus_pc_id(raw: Optional[str]) -> Optional[str]:
    """Normalize Opus ID to canonical PC-XXXXXX format (6 digits, zero-padded)."""
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


TYPE_LABELS: Dict[str, str] = {
    "U": "UPI transaction",
    "B": "Bank Transfer",
}


STATUS_LABELS: Dict[str, str] = {
    "P": "Pending",
    "Y": "Success",
    "N": "Failed",
    "R": "Rejected",
}


def _parse_dt(value: str) -> Optional[datetime]:
    """Parse CSV datetime like '11/08/25 10:50'. Return None if unknown."""
    if not value:
        return None
    value = value.strip()
    if not value:
        return None
    patterns = [
        "%d/%m/%y %H:%M:%S",
        "%d/%m/%y %H:%M",
    ]
    for p in patterns:
        try:
            return datetime.strptime(value, p)
        except Exception:
            continue
    return None


def _get_point_history_file_path() -> str:
    """Get absolute path to point_history.csv."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(current_dir))
    return os.path.join(project_root, "data/point_history.csv")


def _safe_int(value: Optional[str]) -> int:
    try:
        if value is None or value == "":
            return 0
        return int(float(value))
    except Exception:
        return 0


def _compute_point_balance(opus_pc_id: str) -> Dict[str, Any]:
    """Compute or fetch the latest balance for an opus_pc_id from point_history.csv.

    Preference order:
    1) Latest non-empty balance field by created_at
    2) Fallback to computed sum of credits (C) minus debits (D)
    """
    result: Dict[str, Any] = {
        "balance": None,
        "source": None,
        "as_of": None,
    }

    path = _get_point_history_file_path()
    if not os.path.exists(path):
        return result

    rows: List[Dict[str, str]] = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if (row.get("opus_pc_id") or "").strip() == opus_pc_id:
                    rows.append(row)
    except Exception:
        return result

    if not rows:
        # No history available
        return result

    # Sort by created_at desc
    rows.sort(key=lambda r: _parse_dt(r.get("created_at", "")) or datetime.min, reverse=True)

    # Try latest non-empty balance field
    for r in rows:
        bal_raw = (r.get("balance") or "").strip()
        if bal_raw != "":
            result["balance"] = _safe_int(bal_raw)
            result["source"] = "balance_field"
            result["as_of"] = r.get("created_at")
            break

    if result["balance"] is None:
        # Fallback: compute from credits (C) and debits (D)
        computed = 0
        for r in rows:
            points = _safe_int(r.get("point_cr_db"))
            method = (r.get("method") or "").strip().upper()
            if method == "C":
                computed += points
            elif method == "D":
                computed -= points
        result["balance"] = computed
        result["source"] = "computed"
        result["as_of"] = rows[0].get("created_at")

    return result


def _sort_key(row: Dict[str, str]) -> Tuple[Optional[datetime], Optional[datetime], int]:
    """Sort primarily by updated_at, then created_at, then id (desc)."""
    def to_int(v: Optional[str]) -> int:
        try:
            if v is None or v == "":
                return 0
            return int(float(v))
        except Exception:
            return 0

    return (
        _parse_dt(row.get("updated_at", "")) or _parse_dt(row.get("created_at", "")),
        _parse_dt(row.get("created_at", "")),
        to_int(row.get("id")),
    )


def _load_reference_map() -> Dict[str, List[Dict[str, str]]]:
    """Load reference rows keyed by cash_transfer_id (string)."""
    ref_path = _get_cash_transfer_reference_file_path()
    ref_map: Dict[str, List[Dict[str, str]]] = {}
    if not os.path.exists(ref_path):
        return ref_map
    try:
        with open(ref_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                key = str(row.get("cash_transfer_id", "")).strip()
                if not key:
                    continue
                ref_map.setdefault(key, []).append(row)
    except Exception:
        return ref_map
    return ref_map


def _row_to_entry(row: Dict[str, str], ref_rows: List[Dict[str, str]]) -> Dict[str, Any]:
    """Project minimal fields needed by the agent for redemption guidance."""
    type_code = (row.get("type") or "").strip().upper()
    status_code = (row.get("status") or "").strip().upper()

    # Attach latest reference snapshot if available
    latest_ref = ref_rows[-1] if ref_rows else None
    reference = None
    if latest_ref:
        reference = {
            "latitude": latest_ref.get("latitude"),
            "longitude": latest_ref.get("longitude"),
            "factor": latest_ref.get("factor"),
            "transaction_rspn": latest_ref.get("transaction_rspn"),
            "status_rspn": latest_ref.get("status_rspn"),
            "created_at": latest_ref.get("created_at"),
            "updated_at": latest_ref.get("updated_at"),
        }

    return {
        "id": row.get("id"),
        "transaction_id": row.get("transaction_id"),
        "transfer_id": row.get("transfer_id"),
        "opus_pc_id": row.get("opus_pc_id"),
        "type": type_code,
        "type_label": TYPE_LABELS.get(type_code, "Unknown"),
        "points": row.get("points"),
        "status": status_code,
        "status_label": STATUS_LABELS.get(status_code, "Unknown"),
        "reason": row.get("reason"),
        "reason_message": row.get("reason_message"),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
        "tds": row.get("tds"),
        "tds_percentage": row.get("tds_percentage"),
        "net_amount": row.get("net_amount"),
        "reference": reference,
    }


def get_cash_transfer_history(opus_pc_id: str, limit: int = 3) -> Dict[str, Any]:
    """Return the last N cash transfer requests for an opus_pc_id.

    Args:
        opus_pc_id: Opus ID of the caller (accepts loose formats; normalized to PC-XXXXXX)
        limit: Number of latest transfers to return (default 3)

    Returns:
        success flag, normalized opus id, compact entries list, and a small summary.
    """
    try:
        data_path = _get_cash_transfer_file_path()
        if not os.path.exists(data_path):
            return {"success": False, "error": f"Cash transfer file not found at {data_path}"}

        target_norm = _normalize_opus_pc_id(opus_pc_id)
        if not target_norm:
            return {"success": False, "error": "opus_pc_id is required"}

        rows: List[Dict[str, str]] = []
        with open(data_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if (row.get("opus_pc_id") or "").strip() == target_norm:
                    rows.append(row)

        # rows may be empty; still return balance and eligibility

        # Sort rows (desc)
        rows.sort(key=_sort_key, reverse=True)

        # Limit
        lim = max(1, int(limit)) if limit else 3
        limited_rows = rows[:lim]

        # Load reference map and build entries
        # Join primarily on transfer_id (cash_transfer.csv) -> cash_transfer_id (reference)
        # Fallback to id (cash_transfer.csv) -> cash_transfer_id (reference) for legacy datasets
        ref_map = _load_reference_map()
        entries: List[Dict[str, Any]] = []
        for r in limited_rows:
            key_by_transfer = (r.get("transfer_id") or "").strip()
            key_by_id = (r.get("id") or "").strip()
            ref_rows = ref_map.get(key_by_transfer) or ref_map.get(key_by_id, [])
            entries.append(_row_to_entry(r, ref_rows))

        # Compute summary
        counts_by_status: Dict[str, int] = {}
        for r in limited_rows:
            sc = (r.get("status") or "").strip().upper()
            counts_by_status[sc] = counts_by_status.get(sc, 0) + 1

        latest_block = None
        if len(limited_rows) > 0:
            latest_block = {
                "status": limited_rows[0].get("status"),
                "status_label": STATUS_LABELS.get((limited_rows[0].get("status") or "").strip().upper(), "Unknown"),
                "type": limited_rows[0].get("type"),
                "type_label": TYPE_LABELS.get((limited_rows[0].get("type") or "").strip().upper(), "Unknown"),
                "points": limited_rows[0].get("points"),
                "created_at": limited_rows[0].get("created_at"),
            }

        summary = {
            "total_records": len(limited_rows),
            "counts_by_status": {
                code: {"count": count, "label": STATUS_LABELS.get(code, "Unknown")} for code, count in counts_by_status.items()
            },
            "latest": latest_block,
        }

        # Compose a short message for quick speaking by the agent
        if summary["latest"] is not None:
            latest = summary["latest"]
            message = (
                f"Latest transfer: {latest['type_label']} of {latest['points']} points is {latest['status_label']} on {latest['created_at']}."
            )
        else:
            message = "No prior cash transfers found for this Opus ID."

        # Attach point balance
        point_balance_info = _compute_point_balance(target_norm)

        # Determine first-time vs repeat redemption using ANY successful transfer (status=Y)
        any_success_rows = [r for r in rows if (r.get("status") or "").strip().upper() == "Y"]
        is_first_redemption = len(any_success_rows) == 0
        required_min_points = 5000 if is_first_redemption else 500
        current_balance = point_balance_info.get("balance") or 0
        meets_min_requirement = current_balance >= required_min_points
        missing_points = required_min_points - current_balance if current_balance < required_min_points else 0

        latest_success = None
        if any_success_rows:
            # Sort by created_at desc and pick first
            any_success_rows.sort(key=lambda r: _parse_dt(r.get("created_at", "")) or datetime.min, reverse=True)
            s = any_success_rows[0]
            latest_success = {
                "id": s.get("id"),
                "transaction_id": s.get("transaction_id"),
                "transfer_id": s.get("transfer_id"),
                "points": s.get("points"),
                "type": s.get("type"),
                "created_at": s.get("created_at"),
            }

        # Eligibility advice and message
        advice: List[Dict[str, Any]] = []
        if not meets_min_requirement:
            advice.append({
                "type": "INSUFFICIENT_POINTS",
                "first_time": is_first_redemption,
                "required_min_points": required_min_points,
                "current_balance": current_balance,
                "missing_points": missing_points,
                "next_action": "create_enquiry_for_minimum_points_guidance",
            })
        else:
            advice.append({
                "type": "POINTS_SUFFICIENT",
                "first_time": is_first_redemption,
                "required_min_points": required_min_points,
                "current_balance": current_balance,
                "next_action": "proceed_with_redemption_checks",
            })

        eligibility_message = (
            f"Balance {current_balance}. "
            f"Minimum required is {required_min_points} ({'first' if is_first_redemption else 'repeat'} redemption). "
            f"Status: {'Eligible' if meets_min_requirement else f'Insufficient by {missing_points} points'}."
        )
        # If points are sufficient, surface the most recent non-accepted reason (P/N/R)
        latest_non_accepted_detail = None
        non_accepted_statuses = {"P", "N", "R"}
        if meets_min_requirement and rows:
            for r in rows:  # rows already sorted desc
                st = (r.get("status") or "").strip().upper()
                if st in non_accepted_statuses:
                    latest_non_accepted_detail = {
                        "id": r.get("id"),
                        "transaction_id": r.get("transaction_id"),
                        "transfer_id": r.get("transfer_id"),
                        "status": st,
                        "status_label": STATUS_LABELS.get(st, "Unknown"),
                        "reason": r.get("reason"),
                        "reason_message": r.get("reason_message"),
                        "type": r.get("type"),
                        "created_at": r.get("created_at"),
                        "updated_at": r.get("updated_at"),
                    }
                    break

        # Build a user-facing reason if found
        non_accepted_snippet = ""
        if latest_non_accepted_detail:
            st_label = latest_non_accepted_detail.get("status_label")
            reason_msg = (latest_non_accepted_detail.get("reason_message") or latest_non_accepted_detail.get("reason") or "No reason provided").strip()
            when = latest_non_accepted_detail.get("created_at")
            non_accepted_snippet = f" Last attempt status: {st_label}. Reason: {reason_msg}. Date: {when}."
            advice.append({
                "type": "PAYMENT_NOT_ACCEPTED",
                "status": latest_non_accepted_detail.get("status"),
                "status_label": st_label,
                "reason_message": latest_non_accepted_detail.get("reason_message"),
                "reason": latest_non_accepted_detail.get("reason"),
                "created_at": when,
            })

        # Combine into main message succinctly
        message = f"{message} {eligibility_message}{non_accepted_snippet}".strip()

        return {
            "success": True,
            "opus_pc_id": target_norm,
            "entries": entries,
            "summary": summary,
            "message": message,
            "point_balance": point_balance_info.get("balance"),
            "point_balance_meta": {
                "source": point_balance_info.get("source"),
                "as_of": point_balance_info.get("as_of"),
            },
            "redemption_eligibility": {
                "is_first_redemption": is_first_redemption,
                "required_min_points": required_min_points,
                "current_balance": current_balance,
                "meets_min_requirement": meets_min_requirement,
                "missing_points": missing_points,
                "latest_successful_transfer": latest_success,
                "successful_transfer_count": len(any_success_rows),
                "message": eligibility_message,
            },
            "advice": advice,
            "latest_non_accepted_transfer": latest_non_accepted_detail,
        }

    except Exception as e:
        return {"success": False, "error": f"Error reading cash transfer history: {str(e)}"}


# Export the main function for LiveKit use
# The agent.py will wrap this with @function_tool() decorator
cash_transfer_history_func = get_cash_transfer_history

@function_tool()
async def cash_transfer_history_tool(context: RunContext, opus_pc_id: str, limit: int = 3) -> dict:
    """Get cash transfer history and point balance for redemption checks."""
    return cash_transfer_history_func(opus_pc_id=opus_pc_id, limit=limit)
