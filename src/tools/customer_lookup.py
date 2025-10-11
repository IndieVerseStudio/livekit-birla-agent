import csv
import os
from typing import Dict, Any, List
from livekit.agents import function_tool, RunContext

def _get_data_file_path() -> str:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(current_dir))
    return os.path.join(project_root, "data", "mock.csv")
    

# All the field are harcoded now cause in future we will rely on api call, so no need to refactor this for now
def _find_customers(key: str, value: str) -> List[Dict[str, Any]]:
    data_file = _get_data_file_path()
    if not os.path.exists(data_file):
        raise FileNotFoundError(f"Customer data file not found at {data_file}")

    accounts = []
    with open(data_file, 'r', encoding='utf-8') as file:
        csv_reader = csv.DictReader(file)
        for row in csv_reader:
            if key == 'mobile_number':
                row_value = ''.join(filter(str.isdigit, row.get(key, '')))
                if row_value == value:
                    accounts.append({
                        "opus_id": row.get('opus_id', ''),
                        "name": f"{row.get('first_name', '')} {row.get('last_name', '')}".strip(),
                        "email": row.get('email', ''),
                        "kyc_status": row.get('kyc_status', ''),
                        "account_status": row.get('status', ''),
                        "data_created": row.get('data_created', '')
                    })
            else:
                row_value = row.get(key, '')
                if row_value.lower() == value.lower():
                    accounts.append({
                        "opus_id": row.get('opus_id', ''),
                        "name": f"{row.get('first_name', '')} {row.get('last_name', '')}".strip(),
                        "email": row.get('email', ''),
                        "kyc_status": row.get('kyc_status', ''),
                        "account_status": row.get('status', ''),
                        "data_created": row.get('data_created', '')
                    })
    return accounts

@function_tool()
async def customer_lookup_tool(context: RunContext, mobile_number: str) -> str:
    """Looks up customer details using their 10-digit mobile number."""
    try:
        clean_phone = ''.join(filter(str.isdigit, mobile_number))
        if len(clean_phone) != 10:
            return "Invalid phone number format. Please provide a 10-digit phone number."

        accounts = _find_customers('mobile_number', clean_phone)

        if not accounts:
            return f"PHONE_LOOKUP_FAILED: No accounts found for mobile number {mobile_number}. Please ask customer for their Opus ID for verification."
        
        return f"Found {len(accounts)} account(s): {accounts}. Multiple accounts: {len(accounts) > 1}."

    except Exception as e:
        return f"An error occurred during customer lookup: {str(e)}"

@function_tool()
async def customer_lookup_by_opus_id_tool(context: RunContext, opus_id: str) -> str:
    """Looks up customer details using their Opus ID."""
    try:
        if not opus_id:
            return "Opus ID was not provided."

        accounts = _find_customers('opus_id', opus_id)

        if not accounts:
            return f"No account found for Opus ID {opus_id}."
        
        return f"Found account: {accounts[0]}."

    except Exception as e:
        return f"An error occurred during customer lookup by Opus ID: {str(e)}"