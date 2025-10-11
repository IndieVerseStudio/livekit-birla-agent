from typing import Dict
from livekit.agents import function_tool, RunContext
from utils.intent_classifier import IntentClassifier

_classifier = IntentClassifier()

@function_tool()
async def classify_customer_intent_tool(context: RunContext, customer_query: str) -> Dict:
    """
    Classify customer intent based on their initial query/complaint.
    
    This tool analyzes what the customer is saying and determines which type of issue 
    they are facing so the agent can follow the appropriate instruction flow.
    
    Args:
        customer_query: The customer's initial complaint or description of their issue
        
    Returns:
        Dictionary containing:
        - intent: The classified intent (KYC_APPROVAL, POINT_REDEMPTION, QR_SCANNING, ACCOUNT_BLOCKED, or UNCLEAR)
        - confidence: Confidence score (0.0 to 1.0)
        - description: Human-readable description of the intent
        - instruction_flow: The instruction flow file to follow
    """

    intent, confidence, description = _classifier.classify_intent(customer_query)
    instruction_flow = _classifier.get_intent_instruction(intent)

    return {
        'intent': intent,
        'confidence': round(confidence, 2),
        'description': description,
        'instruction_flow': instruction_flow,
    }