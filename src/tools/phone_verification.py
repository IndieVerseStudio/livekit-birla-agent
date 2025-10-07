"""
Phone verification tool for KYC Customer Care Bot.
Verifies if customer is calling from registered phone number.
"""

import csv
import os
from typing import Dict, Any, List
from livekit.agents import function_tool, RunContext


def _get_data_file_path() -> str:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(current_dir))  # Go up two levels from src/tools/
    return os.path.join(project_root, "data", "mock.csv")

@function_tool()
async def verify_phone_number(context: RunContext, phone_number: str) -> dict:
    """Verify if phone number is registered and get associated accounts."""
    try:
        clean_phone = ''.join(filter(str.isdigit, phone_number))
        
        if len(clean_phone) != 10:
            return {
                "success": False,
                "error": "Invalid phone number format. Please provide a 10-digit phone number."
            }
        
        data_file = _get_data_file_path()
        
        if not os.path.exists(data_file):
            return {
                "success": False,
                "error": f"Customer data file not found at {data_file}"
            }
        
        accounts = []
        with open(data_file, 'r', encoding='utf-8') as file:
            csv_reader = csv.DictReader(file)
            
            for row in csv_reader:
                row_mobile = ''.join(filter(str.isdigit, row.get('mobile_number', '')))
                
                if row_mobile == clean_phone:
                    accounts.append({
                        "opus_id": row.get('opus_id', ''),
                        "name": f"{row.get('first_name', '')} {row.get('last_name', '')}".strip(),
                        "email": row.get('email', ''),
                        "kyc_status": row.get('kyc_status', ''),
                        "account_status": row.get('status', ''),
                        "data_created": row.get('data_created', '')
                    })
        
        if not accounts:
            return {
                "success": True,
                "is_registered": False,
                "message": f"No accounts found for phone number {phone_number}",
                "accounts": []
            }
        
        return {
            "success": True,
            "is_registered": True,
            "message": f"Found {len(accounts)} account(s) for phone number {phone_number}",
            "accounts": accounts,
            "multiple_accounts": len(accounts) > 1
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Error during phone verification: {str(e)}"
        }




