"""
Hardcoded Context tool for KYC Customer Care Bot.
Provides predefined context about the caller's phone number.
"""

from typing import Dict, Any
from livekit.agents import function_tool

@function_tool()
async def hardcoded_context_tool() -> str:
    """
    Get hardcoded context including the caller's phone number.
    This tool simulates getting the caller's phone number from the call infrastructure.
    """
    try:
        phone_number = "9812345769"
        return f"Caller is calling from registered number: {phone_number}"
        
    except Exception as e:
        return f"Error retrieving hardcoded context: {str(e)}"

@function_tool()
async def set_caller_context_tool(phone_number: str) -> str:
    """
    Set caller context with a specific phone number.
    This is a placeholder and might not be needed if hardcoded_context_tool is used.
    """
    try:
        context = {
            "success": True,
            "caller_phone": phone_number,
            "is_registered_number": True,
            "context_message": f"Setting caller context for phone number {phone_number}",
            "verification_status": "verified",
            "instructions": f"Use phone number {phone_number} for all subsequent customer lookups"
        }
        
        return str(context)
        
    except Exception as e:
        return f"Error setting caller context: {str(e)}"