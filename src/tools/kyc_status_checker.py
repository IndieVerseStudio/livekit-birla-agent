"""
KYC Status Checker tool for KYC Customer Care Bot.
Checks KYC completion status and calculates timeline information.
"""

import csv
import os
from datetime import datetime, timedelta
from typing import Dict, Any
from livekit.agents import function_tool, RunContext

def _get_data_file_path() -> str:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(current_dir))  # Go up two levels from src/tools/
    return os.path.join(project_root, "data", "mock.csv")

@function_tool()
async def kyc_status_checker_tool(context: RunContext, opus_id: str) -> dict:
    """Check KYC status and calculate timeline for account approval."""
    try:
        data_file = _get_data_file_path()
        
        if not os.path.exists(data_file):
            return {
                "success": False,
                "error": f"Customer data file not found at {data_file}"
            }
        
        # Find the customer record
        customer_record = None
        with open(data_file, 'r', encoding='utf-8') as file:
            csv_reader = csv.DictReader(file)
            
            for row in csv_reader:
                if row.get('opus_id', '') == opus_id:
                    customer_record = row
                    break
        
        if not customer_record:
            return {
                "success": False,
                "error": f"No customer found with Opus ID: {opus_id}"
            }
        
        # Extract KYC information
        kyc_status = customer_record.get('kyc_status', '')
        is_aadhar_added = customer_record.get('is_aadhar_added', '').lower() == 'true'
        is_pan_added = customer_record.get('is_pan_added', '').lower() == 'true'
        is_bank_added = customer_record.get('is_bank_added', '').lower() == 'true'
        is_upi_added = customer_record.get('is_upi_added', '').lower() == 'true'
        data_created_days = int(customer_record.get('data_created', 0))
        
        # Calculate registration date (assuming data_created is days ago)
        registration_date = datetime.now() - timedelta(days=data_created_days)
        
        # Determine KYC completion status
        kyc_documents_complete = is_aadhar_added and is_pan_added and is_bank_added
        
        # Analyze KYC status
        if kyc_status == 'F':  # Full KYC Complete
            days_since_kyc = data_created_days  # Assuming KYC completed at registration
            days_remaining = max(0, 30 - days_since_kyc)
            
            if days_since_kyc <= 30:
                recommendation = "within_timeline"
                message = f"KYC is done dont you need to wait {days_remaining} days"
            else:
                recommendation = "timeline_exceeded"
                message = "KYC completion 30 days passed. Contact TSM or raise a complaint."
                
        elif kyc_status == 'P':  # Partial KYC
            recommendation = "partial_kyc"
            missing_docs = []
            if not is_aadhar_added:
                missing_docs.append("Aadhar")
            if not is_pan_added:
                missing_docs.append("PAN")
            if not is_bank_added:
                missing_docs.append("Bank Details")
            if not is_upi_added:
                missing_docs.append("UPI")
                
            message = f"KYC is not complete. Please complete {', '.join(missing_docs)}"
            
        elif kyc_status == 'R':  # Rejected
            recommendation = "kyc_rejected"
            message = "KYC is rejected. Please submit documents again."
            
        elif kyc_status == 'N':  # Not Started
            recommendation = "kyc_not_started"
            message = "KYC is not started. Please complete KYC process."
            
        else:
            recommendation = "unknown_status"
            message = "KYC status unclear. Please check with technical team."
        
        return {
            "success": True,
            "opus_id": opus_id,
            "kyc_status": kyc_status,
            "kyc_status_description": {
                'F': 'Full KYC Complete',
                'P': 'Partial KYC',
                'R': 'KYC Rejected',
                'N': 'KYC Not Started'
            }.get(kyc_status, 'Unknown'),
            "documents_status": {
                "aadhar": is_aadhar_added,
                "pan": is_pan_added,
                "bank": is_bank_added,
                "upi": is_upi_added
            },
            "timeline_info": {
                "registration_date": registration_date.strftime("%Y-%m-%d"),
                "days_since_registration": data_created_days,
                "days_remaining_for_approval": max(0, 30 - data_created_days) if kyc_status == 'F' else None,
                "timeline_exceeded": data_created_days > 30 and kyc_status == 'F'
            },
            "recommendation": recommendation,
            "message": message,
            "customer_name": f"{customer_record.get('first_name', '')} {customer_record.get('last_name', '')}".strip()
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Error checking KYC status: {str(e)}"
        }

