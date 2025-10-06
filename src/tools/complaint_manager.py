"""
Complaint Management tool for KYC Customer Care Bot.
Handles complaint creation, tracking, and status management.
"""

import json
import os
from datetime import datetime, timedelta
from typing import Dict, Any, List
import uuid
from livekit.agents import function_tool
from livekit.agents import RunContext


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
async def auto_create_complaint_tool(self, context: RunContext, opus_id: str, customer_name: str, days_since_kyc: int) -> dict:
    """Automatically create a complaint if customer has been waiting more than 30 days since KYC completion."""
    try:
        # If more than 30 days, automatically create a complaint
        if days_since_kyc > 30:
            kyc_completion_date = (datetime.now() - timedelta(days=days_since_kyc)).strftime("%Y-%m-%d")
            
            complaint_result = await self.create_complaint_tool(
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
async def create_complaint_tool(self, context: RunContext, opus_id: str, customer_name: str, complaint_type: str, 
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
async def create_enquiry_tool(self, context: RunContext, opus_id: str, customer_name: str, enquiry_type: str, 
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
