import json
import os
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import uuid
from livekit.agents import function_tool, RunContext


def _get_complaints_file_path() -> str:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(current_dir))  # Go up two levels from src/tools/
    return os.path.join(project_root, "data", "complaints.json")

def _load_complaints() -> List[Dict]:
    """Load existing complaints from JSON file."""
    complaints_file = _get_complaints_file_path()
    
    if not os.path.exists(complaints_file):
        # Create data directory if it doesn't exist
        os.makedirs(os.path.dirname(complaints_file), exist_ok=True)
        return []
    
    try:
        with open(complaints_file, 'r', encoding='utf-8') as file:
            return json.load(file)
    except (json.JSONDecodeError, FileNotFoundError):
        return []


def _save_complaints(complaints: List[Dict]) -> None:
    """Save complaints to JSON file."""
    complaints_file = _get_complaints_file_path()
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(complaints_file), exist_ok=True)
    
    with open(complaints_file, 'w', encoding='utf-8') as file:
        json.dump(complaints, file, indent=2, ensure_ascii=False)

@function_tool()
async def auto_create_complaint_tool(context: RunContext, opus_id: str, customer_name: str, days_since_kyc: int) -> dict:
    """Automatically create a complaint if customer has been waiting more than 30 days since KYC completion."""
    try:
        # If more than 30 days, automatically create a complaint
        if days_since_kyc > 30:
            kyc_completion_date = (datetime.now() - timedelta(days=days_since_kyc)).strftime("%Y-%m-%d")
            
            complaint_result = await create_complaint_tool(
                context=context,
                opus_id=opus_id,
                customer_name=customer_name,
                complaint_type="high_priority",
                subject=f"KYC Account Approval Delay - {days_since_kyc} days pending",
                issue_description=f"Customer's KYC was completed on {kyc_completion_date} but account approval is still pending after {days_since_kyc} days.",
                priority="high"
            )
            
            if complaint_result.get("success"):
                return {
                    "success": True,
                    "auto_complaint_created": True,
                    "days_since_kyc": days_since_kyc,
                    "complaint_number": complaint_result.get("complaint_number"),
                    "message": f"Main aapke liye complaint create kar diya hun kyunki {days_since_kyc} din se zyada ho gaye hain. Aapka complaint number hai {complaint_result.get('complaint_number')}. Aap apne TSM se bhi contact kar sakte hain.",
                    "sms_confirmation": complaint_result.get("sms_confirmation"),
                    "complaint_details": complaint_result.get("complaint_details")
                }
            else:
                return {
                    "success": False,
                    "error": f"Failed to create auto-complaint: {complaint_result.get('error')}"
                }
        else:
            # Within 30 days, no complaint needed
            days_remaining = 30 - days_since_kyc
            return {
                "success": True,
                "auto_complaint_created": False,
                "days_since_kyc": days_since_kyc,
                "days_remaining": days_remaining,
                "message": f"Aapka KYC {days_since_kyc} din pehle complete hua tha. Aapko {days_remaining} din aur wait karna hoga account approval ke liye. Aap apne TSM se bhi contact kar sakte hain.",
                "tsm_message": "Aap apne TSM se contact kar sakte hain additional support ke liye."
            }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Error in auto-complaint creation: {str(e)}"
            }

@function_tool()
async def create_complaint_tool(context: RunContext, opus_id: str, customer_name: str, complaint_type: str, 
                subject: str, issue_description: str, priority: str) -> dict:
    """Create a new complaint."""
    try:
        complaints = _load_complaints()
        
        # Generate complaint number
        complaint_number = f"KYC{datetime.now().strftime('%Y%m%d')}{len(complaints) + 1:04d}"
        
        # Set timeline based on priority
        timeline_days = 3 if priority == "high" else 7
        
        # Create complaint record
        new_complaint = {
            "complaint_number": complaint_number,
            "opus_id": opus_id,
            "customer_name": customer_name,
            "type": complaint_type,
            "subject": subject,
            "issue_description": issue_description,
            "priority": priority,
            "status": "active",
            "created_date": datetime.now().isoformat(),
            "timeline_days": timeline_days,
            "expected_resolution": (datetime.now() + timedelta(days=timeline_days)).isoformat(),
            "category": "Painter/contractor Complaints" if complaint_type != "enquiry" else "General enquiries/Others",
            "sub_category": "Opus ID App" if complaint_type != "enquiry" else "Other Enquiries",
            "escalation_level": "high" if priority == "high" else "standard"
        }
        
        complaints.append(new_complaint)
        _save_complaints(complaints)
        
        return {
            "success": True,
            "complaint_created": True,
            "complaint_number": complaint_number,
            "timeline_days": timeline_days,
            "expected_resolution": (datetime.now() + timedelta(days=timeline_days)).strftime("%Y-%m-%d"),
            "message": f"Complaint {complaint_number} successfully created for {customer_name}",
            "sms_confirmation": f"आपका complaint number है {complaint_number}. {timeline_days} दिन में resolve होगा।",
            "complaint_details": new_complaint
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Error creating complaint: {str(e)}"
        }

@function_tool()
async def create_enquiry_tool(context: RunContext, opus_id: str, customer_name: str, enquiry_type: str, 
                subject: str, description: str) -> dict:
    """Create a new enquiry (for informational purposes)."""
    try:
        complaints = _load_complaints()
        
        # Generate enquiry number
        enquiry_number = f"ENQ{datetime.now().strftime('%Y%m%d')}{len(complaints) + 1:04d}"
        
        new_enquiry = {
            "enquiry_number": enquiry_number,
            "opus_id": opus_id,
            "customer_name": customer_name,
            "type": "enquiry",
            "enquiry_type": enquiry_type,
            "subject": subject,
            "description": description,
            "status": "logged",
            "created_date": datetime.now().isoformat(),
            "category": "General enquiries/Others",
            "sub_category": "Other Enquiries",
            "issue": "Become a Painter/Contractor"
        }
        
        complaints.append(new_enquiry)
        _save_complaints(complaints)
        
        return {
            "success": True,
            "enquiry_created": True,
            "enquiry_number": enquiry_number,
            "message": f"Enquiry {enquiry_number} logged for {customer_name}",
            "expected_timeline": "2-3 working days for response",
            "enquiry_details": new_enquiry
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Error creating enquiry: {str(e)}"
        }

##-----------Need to Check these tools-----------------------
@function_tool()
async def create_record_from_code_history(
    context: RunContext,
    opus_id: str,
    customer_name: str,
    coupon_code: str,
    latest_status: str,
    advice_types: List[str],
    user_type: str
) -> Dict[str, Any]:
    """Create an enquiry or complaint based on code-history outcomes.

    Rules:
    - WRONG_CODE_TYPE => Enquiry (guidance)
    - ADVISE_WAIT (Pending) => Enquiry (timeline info)
    - GEO_RESTRICTED => Enquiry (guidance)
    - REJECTED_PROFILE => Complaint if KYC complete (caller should check KYC upstream); default Enquiry
    - CREATE_COMPLAINT_FOR_FRAUD_SCAN => Complaint (fraud/another user scanned)
    - EXPIRED (E) => Enquiry
    - Otherwise => Enquiry by default
    
    Args:
        opus_id: Customer's Opus ID
        customer_name: Customer's full name
        coupon_code: The QR/coupon code in question
        latest_status: Latest status code (Y, A, E, P, R, Z, G, etc.)
        advice_types: List of advice type strings from code_history_tool
        user_type: PAINTER or CONTRACTOR
        
    Returns:
        Dictionary with record creation result
    """
    try:
        advice_set = set(advice_types or [])
        latest_status = (latest_status or "").upper()

        if "CREATE_COMPLAINT_FOR_FRAUD_SCAN" in advice_set:
            return {
                "success": True,
                "requires_confirmation": True,
                "recommendation": "create_complaint",
                "message": "Complaint recommended: QR code scanned by a different user.",
                "proposed_complaint": {
                    "complaint_type": "standard",
                    "subject": f"QR code scanned by different user - {coupon_code}",
                    "issue_description": (
                        f"Reported by {customer_name} ({opus_id}). Code {coupon_code} appears scanned by another user. Needs investigation."
                    ),
                    "priority": "standard",
                },
            }

        if latest_status in {"E"}:
            return await create_enquiry_tool(
                opus_id=opus_id,
                customer_name=customer_name,
                enquiry_type="QR Guidance",
                subject=f"Expired QR code - {coupon_code}",
                description=f"Expired code. Educated user to use a valid code. User type: {user_type}.",
            )

        if "WRONG_CODE_TYPE" in advice_set:
            return await create_enquiry_tool(
                opus_id=opus_id,
                customer_name=customer_name,
                enquiry_type="QR Guidance",
                subject=f"Wrong code type scanned - {coupon_code}",
                description=f"Explained L (12-digit) vs C (13-digit) and inside/outside rule. User type: {user_type}.",
            )

        if "ADVISE_WAIT" in advice_set:
            return await create_enquiry_tool(
                opus_id=opus_id,
                customer_name=customer_name,
                enquiry_type="Timeline",
                subject=f"Pending status guidance - {coupon_code}",
                description="Advised user to scan again after 2–3 days; KYC may be required.",
            )

        if "GEO_RESTRICTED" in advice_set or latest_status == "G":
            return await create_enquiry_tool(
                opus_id=opus_id,
                customer_name=customer_name,
                enquiry_type="QR Guidance",
                subject=f"Geo restricted scan - {coupon_code}",
                description="Advised user to scan more than 22 meters away from contractor location.",
            )

        if "REJECTED_PROFILE" in advice_set or latest_status in {"R", "Z"}:
            # Recommend complaint if KYC already complete; otherwise enquiry
            return {
                "success": True,
                "requires_confirmation": True,
                "recommendation": "create_complaint",
                "message": "Complaint may be needed for rejected profile if KYC is complete.",
                "proposed_complaint": {
                    "complaint_type": "standard",
                    "subject": f"Profile rejected - {coupon_code}",
                    "issue_description": (
                        "Profile rejected; investigation requested. If KYC is not complete, complete KYC first."
                    ),
                    "priority": "standard",
                },
                "fallback": {
                    "type": "enquiry",
                    "enquiry": {
                        "enquiry_type": "KYC Guidance",
                        "subject": f"Profile rejected guidance - {coupon_code}",
                        "description": "Advised to complete KYC or escalate via complaint/TSM if already complete.",
                    },
                },
            }

        # Default: Enquiry
        return await create_enquiry_tool(
            opus_id=opus_id,
            customer_name=customer_name,
            enquiry_type="General",
            subject=f"QR scan support - {coupon_code}",
            description=f"Recorded support interaction for code {coupon_code}. User type: {user_type}",
        )
    except Exception as e:
        return {"success": False, "error": f"Error creating record from code history: {str(e)}"}


@function_tool()
async def create_record_from_account_block(
    context: RunContext,
    opus_id: str,
    customer_name: str,
    block_status: str,
    advice_types: List[str],
    timeline_info: Optional[Dict[str, Any]] = None,
    block_through_label: Optional[str] = None,
) -> Dict[str, Any]:
    """Create enquiry/complaint based on account-block outcome.

    Rules:
    - U (Unblocked) => Enquiry (status confirmation)
    - A (Automatic):
      * If advice includes WAIT_UNTIL_48_HOURS => Enquiry (timeline guidance)
      * If advice includes RAISE_COMPLAINT_OVER_48_HOURS => Complaint (investigation)
    - M (Manual) => Complaint (TSM decision)
    - P (Permanent) => Complaint (backend investigation)
    - Unknown => Complaint by default
    
    Args:
        opus_id: Customer's Opus ID
        customer_name: Customer's full name
        block_status: Block status code (U, A, M, P)
        advice_types: List of advice type strings from account_block_status_tool
        timeline_info: Optional timeline info dict
        block_through_label: Optional label for block reason (OTP related, Suspicious scans)
        
    Returns:
        Dictionary with record creation result
    """
    try:
        advice_set = set(advice_types or [])
        status = (block_status or "").upper()

        # Build helpful description add-ons
        when_str = None
        if timeline_info and timeline_info.get("block_date"):
            when_str = timeline_info.get("block_date")

        # U: not blocked, enquiry for confirmation
        if status == "U" or status == "":
            return await create_enquiry_tool(
                opus_id=opus_id,
                customer_name=customer_name,
                enquiry_type="Status Check",
                subject="Account unblocked confirmation",
                description="Customer verified account is unblocked.",
            )

        # A: Automatic blocks
        if status == "A":
            if "WAIT_UNTIL_48_HOURS" in advice_set:
                expected_date = (timeline_info or {}).get("expected_auto_unblock_date")
                desc = (
                    f"Account automatically blocked. Expected auto-unblock by {expected_date or 'within 48 hours'}. "
                    f"Reason: {block_through_label or 'Automatic detection'}."
                )
                return await create_enquiry_tool(
                    opus_id=opus_id,
                    customer_name=customer_name,
                    enquiry_type="Timeline",
                    subject="Auto-block timeline guidance",
                    description=desc,
                )
            elif "RAISE_COMPLAINT_OVER_48_HOURS" in advice_set:
                desc = (
                    f"Account automatically blocked on {when_str or 'unknown date'}; 48 hours elapsed. "
                    f"Reason: {block_through_label or 'Automatic'}. Needs backend investigation."
                )
                return {
                    "success": True,
                    "requires_confirmation": True,
                    "recommendation": "create_complaint",
                    "message": "Complaint recommended: automatic block exceeded 48 hours.",
                    "proposed_complaint": {
                        "complaint_type": "standard",
                        "subject": "Auto-block not cleared after 48 hours",
                        "issue_description": desc,
                        "priority": "standard",
                    },
                }
            else:
                # Generic auto-block enquiry
                return await create_enquiry_tool(
                    opus_id=opus_id,
                    customer_name=customer_name,
                    enquiry_type="Status Check",
                    subject="Automatic block detected",
                    description=f"Account blocked automatically. Reason: {block_through_label or 'Automatic'}.",
                )

        # M: Manual block => Complaint for TSM decision
        if status == "M":
            desc = (
                f"Account manually blocked by backend on {when_str or 'unknown date'}. "
                "Requires TSM/territory decision for unblock."
            )
            return {
                "success": True,
                "requires_confirmation": True,
                "recommendation": "create_complaint",
                "message": "Complaint recommended: manual block requires TSM review.",
                "proposed_complaint": {
                    "complaint_type": "standard",
                    "subject": "Manual block - TSM review needed",
                    "issue_description": desc,
                    "priority": "standard",
                },
            }

        # P: Permanent block => Complaint for investigation
        if status == "P":
            desc = (
                f"Account permanently blocked on {when_str or 'unknown date'}. "
                "Needs backend investigation and review."
            )
            return {
                "success": True,
                "requires_confirmation": True,
                "recommendation": "create_complaint",
                "message": "Complaint recommended: permanent block requires investigation.",
                "proposed_complaint": {
                    "complaint_type": "standard",
                    "subject": "Permanent block - investigation needed",
                    "issue_description": desc,
                    "priority": "standard",
                },
            }

        # Unknown status => Complaint by default
        return {
            "success": True,
            "requires_confirmation": True,
            "recommendation": "create_complaint",
            "message": "Complaint recommended: unknown block status.",
            "proposed_complaint": {
                "complaint_type": "standard",
                "subject": "Unknown block status - investigation needed",
                "issue_description": f"Unknown block status: {block_status}. Needs investigation.",
                "priority": "standard",
            },
        }
    except Exception as e:
        return {"success": False, "error": f"Error creating record from account block: {str(e)}"}


@function_tool()
async def ensure_record_creation_tool(
    context: RunContext,
    opus_id: str,
    customer_name: str,
) -> Dict[str, Any]:
    """Ensure an enquiry/complaint record exists for this conversation.

    Heuristics (generic):
    - If context.suggest_complaint == True or context.severity in {"high", "fraud"} => Complaint
    - Else create Enquiry with subject from context.subject or "General support"
    - Always return created record number and type
    
    Args:
        opus_id: Customer's Opus ID
        customer_name: Customer's full name
        context: Dictionary with keys like suggest_complaint, severity, subject, description, enquiry_type
        
    Returns:
        Dictionary with record creation result
    """
    try:
        suggest_complaint = bool(context.get("suggest_complaint"))
        severity = (context.get("severity") or "").lower()
        subject = context.get("subject") or "General support"
        description = context.get("description") or "Recorded support interaction"
        complaint_priority = "high" if severity == "high" else "standard"

        if suggest_complaint or severity in {"high", "fraud"}:
            # Do not create complaint automatically; return recommendation
            return {
                "success": True,
                "requires_confirmation": True,
                "recommendation": "create_complaint",
                "message": "Complaint recommended based on context; seek user consent before creation.",
                "proposed_complaint": {
                    "complaint_type": "standard" if complaint_priority == "standard" else "high_priority",
                    "subject": subject,
                    "issue_description": description,
                    "priority": complaint_priority,
                },
            }
        else:
            return await create_enquiry_tool(
                opus_id=opus_id,
                customer_name=customer_name,
                enquiry_type=context.get("enquiry_type") or "General",
                subject=subject,
                description=description,
            )
    except Exception as e:
        return {"success": False, "error": f"Error ensuring record: {str(e)}"}

