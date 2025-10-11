from typing import Dict, Any
from livekit.agents import function_tool, RunContext

@function_tool()
async def hardcoded_context_tool(context: RunContext) -> str:
    """Get hardcoded context including the caller's phone number."""
    try:
        phone_number = "9812345769"
        return f"Caller is calling from registered number: {phone_number}"
    except Exception as e:
        return f"Error retrieving hardcoded context: {str(e)}"

@function_tool()
async def set_caller_context_tool(context: RunContext, phone_number: str) -> str:
    """Set caller context with a specific phone number."""
    try:
        context_data = {
            "success": True,
            "caller_phone": phone_number,
            "is_registered_number": True,
            "context_message": f"Setting caller context for phone number {phone_number}",
            "verification_status": "verified",
            "instructions": f"Use phone number {phone_number} for all subsequent customer lookups"
        }
        return str(context_data)
    except Exception as e:
        return f"Error setting caller context: {str(e)}"