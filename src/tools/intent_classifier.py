"""
Intent Classification Tool for Birla Opus Customer Care (LiveKit Version)

This tool identifies the customer's intent based on their initial complaint
and routes them to the appropriate instruction flow.
"""

import re
from typing import Dict, Tuple


class IntentClassifier:
    """Classifies customer intents based on their queries"""
    
    def __init__(self):
        # Define intent keywords and patterns
        self.intent_patterns = {
            'KYC_APPROVAL': [
                # English patterns
                r'\b(?:kyc|approval|approve|verification|verify|pending|account.*approv|30.*day|contractor.*approv)\b',
                # Hindi/Hinglish patterns
                r'\b(?:approval.*nahi|account.*approve.*nahi|kyc.*pending|verification.*pending)\b',
                # Common phrases
                r'\b(?:id.*verify.*nahi|account.*active.*nahi|contractor.*ban.*nahi)\b',
                # Devanagari (Hindi) patterns
                r'(?:के\s*वाई\s*सी|केवाईसी)',
                r'(?:वेरिफिकेशन|सत्यापन).*?(?:नहीं|नहि|पेंडिंग|लंबित)',
                r'(?:अप्रूव|स्वीकृत|स्वीकृति).*?(?:नहीं|नहि|पेंडिंग|लंबित)',
                r'(?:खाता|अकाउंट|एकाउंट).*?(?:अप्रूव|स्वीकृत).*?(?:नहीं|नहि)',
                r'(?:के\s*वाई\s*सी|केवाईसी).*?(?:नहीं|नहि).*(?:हुआ|approve)'
            ],
            'POINT_REDEMPTION': [
                # English patterns
                r'\b(?:point|redeem|cash|redemption|5000.*point|500.*point|paise.*nahi)\b',
                # Hindi/Hinglish patterns
                r'\b(?:point.*redeem.*nahi|cash.*nahi.*mil|paise.*withdraw.*nahi|redeem.*kar.*nahi)\b',
                # Common phrases
                r'\b(?:point.*problem|cash.*issue|withdrawal.*issue)\b',
                # Devanagari (Hindi) patterns
                r'(?:पॉइंट|पॉइंट्स|अंक).*?(?:रिडीम|रिडीम\s*कर|निकाल).*?(?:नहीं|नहि|नहीं हो)',
                r'(?:कैश|नकद).*?(?:नहीं|नहि).*?(?:मिल|निकाल)',
                r'पॉइंट.*समस्या',
                r'रिडीम.*न(?:हीं|हि).*हो',
                r'पैसे.*न(?:हीं|हि).*मिल'
            ],
            'QR_SCANNING': [
                # English patterns
                r'\b(?:qr.*code|scan|barcode|already.*scan|invalid.*code|code.*scan.*nahi)\b',
                # Hindi/Hinglish patterns
                r'\b(?:qr.*scan.*nahi|code.*work.*nahi|already.*scan|scan.*problem)\b',
                r'\b(?:code.*chal.*nahi|code.*kaam.*nahi|scan.*nahi.*ho)\b',
                # Common phrases
                r'\b(?:code.*invalid|barcode.*issue|scanning.*error)\b',
                # Devanagari (Hindi) patterns
                r'(?:क्यू\s*आर|क्यूआर|क्यू आर).*स्कैन',
                r'कोड.*स्कैन',
                r'बारकोड',
                r'स्कैन\s*नहीं',
                r'(?:अमान्य|इनवैलिड)\s*कोड',
                r'पहले\s*से\s*स्कैन',
                r'स्कैनिंग\s*समस्या',
                r'कोड.*(?:चल|काम).*?(?:नहीं|नहि)',
                r'(?:एरर|त्रुटि|फेल).*?(?:स्कैन|कोड)',
                r'(?:स्कैन|कोड).*?(?:एरर|त्रुटि|फेल)',
                r'(?:स्कैन|कोड).*?(?:नहीं|नहि).*?हो\s*रहा'
            ],
            'ACCOUNT_BLOCKED': [
                # English patterns
                r'\b(?:account.*block|login.*nahi|access.*nahi|blocked|app.*open.*nahi)\b',
                # Hindi/Hinglish patterns
                r'\b(?:account.*band|login.*problem|app.*nahi.*khul|access.*deny)\b',
                # Common phrases
                r'\b(?:account.*suspend|id.*block|login.*error)\b',
                # Devanagari (Hindi) patterns
                r'(?:अकाउंट|एकाउंट|खाता).*?(?:ब्लॉक|बंद)',
                r'लॉगिन.*?(?:नहीं|नहि).*?(?:हो रहा|हो रही)',
                r'ऐप.*?(?:नहीं|नहि).*?(?:खुल|ओपन)',
                r'लॉगिन.*समस्या',
                r'(?:अकाउंट|एकाउंट|खाता).*?(?:लॉक|अवरुद्ध)'
            ]
        }
        
        # Intent descriptions for better understanding
        self.intent_descriptions = {
            'KYC_APPROVAL': 'Customer has issues with KYC approval, account verification, or contractor approval process',
            'POINT_REDEMPTION': 'Customer cannot redeem points, facing cash withdrawal issues, or redemption errors',
            'QR_SCANNING': 'Customer facing QR code scanning issues, already scanned errors, or invalid barcode problems',
            'ACCOUNT_BLOCKED': 'Customer account is blocked, facing login issues, or access problems',
            'UNCLEAR': 'Customer intent is not clear from the initial statement'
        }
    
    def classify_intent(self, customer_query: str) -> Tuple[str, float, str]:
        """
        Classify customer intent based on their query
        
        Args:
            customer_query: Customer's initial complaint or query
            
        Returns:
            Tuple of (intent, confidence_score, description)
        """
        if not customer_query:
            return 'UNCLEAR', 0.0, self.intent_descriptions['UNCLEAR']
        
        # Convert to lowercase for pattern matching
        query_lower = customer_query.lower()
        
        # Score each intent using unique pattern hits (robust to long first messages)
        intent_unique_hits = {}
        
        for intent, patterns in self.intent_patterns.items():
            unique_match_count = 0
            for pattern in patterns:
                if re.search(pattern, query_lower, re.IGNORECASE):
                    unique_match_count += 1
            intent_unique_hits[intent] = (unique_match_count, len(patterns))
        
        # Select the intent with the most unique pattern hits
        best_intent, (best_hits, total_patterns) = max(
            intent_unique_hits.items(), key=lambda item: item[1][0]
        )
        
        # If nothing matched, it's unclear
        if best_hits == 0:
            return 'UNCLEAR', 0.0, self.intent_descriptions['UNCLEAR']
        
        # Confidence: base + fraction of patterns matched (keeps >= ~0.2 when any match)
        confidence = min(0.2 + 0.6 * (best_hits / max(total_patterns, 1)), 0.95)
        
        # If confidence is still too low (very unlikely), mark as unclear
        if confidence < 0.15:
            return 'UNCLEAR', confidence, self.intent_descriptions['UNCLEAR']
        
        return best_intent, confidence, self.intent_descriptions[best_intent]
    
    def get_instruction_flow(self, intent: str) -> str:
        """
        Get the corresponding instruction flow for an intent
        
        Args:
            intent: Classified intent
            
        Returns:
            Instruction flow identifier
        """
        flow_mapping = {
            'KYC_APPROVAL': 'Enhanced_KYC_Approval_Contractor',
            'POINT_REDEMPTION': 'Unable_to_redeem_points',
            'QR_SCANNING': 'QR_Scanning_Merged',
            'ACCOUNT_BLOCKED': 'Painter_Contractor_Account_Blocked',
            'UNCLEAR': 'General_Inquiry'
        }
        
        return flow_mapping.get(intent, 'General_Inquiry')


# Initialize classifier instance (singleton)
_classifier = IntentClassifier()


def classify_customer_intent_func(customer_query: str) -> Dict:
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
        - next_steps: Recommended next steps for the agent
    """
    
    intent, confidence, description = _classifier.classify_intent(customer_query)
    instruction_flow = _classifier.get_instruction_flow(intent)
    
    # Provide next steps based on intent
    next_steps_mapping = {
        'KYC_APPROVAL': 'Haan sir, main samajh pa rhi hun. Follow Enhanced KYC Approval process - verify phone number, check KYC status, create complaint/enquiry as needed',
        'POINT_REDEMPTION': 'Haan sir, main samajh pa rhi hun. Follow Point Redemption process - verify KYC status, check point balance, check account blocking status',
        'QR_SCANNING': 'Haan sir, main samajh pa rhi hun. Follow QR Scanning process - identify user type, validate code type, check scan history',
        'ACCOUNT_BLOCKED': 'Haan sir, main samajh pa rhi hun. Follow Account Blocked process - check account status, provide appropriate resolution',
        'UNCLEAR': 'Use short response: "Pareshani kai liye hume khed hai, kaise sahayata kar sakti hun main aapki?" Do not generate long messages until issue is clear.'
    }
    
    return {
        'intent': intent,
        'confidence': round(confidence, 2),
        'description': description,
        'instruction_flow': instruction_flow,
        'next_steps': next_steps_mapping.get(intent, 'Ask for more details about the issue'),
        'query_analyzed': customer_query
    }


def get_intent_clarification_questions_func() -> Dict:
    """
    Get clarifying questions to ask when customer intent is unclear.
    
    Returns:
        Dictionary with suggested clarifying questions for different scenarios
    """
    
    return {
        'general_questions': [
            "Pareshani kai liye hume khed hai, kaise sahayata kar sakti hun main aapki?",
            "Kya specific problem hai aapko?",
            "Kaise madad kar sakti hun?"
        ],
        'follow_up_questions': {
            'account_related': [
                "Account approve nahi hua?",
                "Login problem hai?",
                "App mein error aa raha hai?"
            ],
            'points_related': [
                "Points redeem nahi ho rahe?",
                "Cash withdraw problem hai?",
                "Point balance issue hai?"
            ],
            'scanning_related': [
                "QR code scan nahi ho raha?",
                "Already scanned message aa raha hai?",
                "Barcode error show kar raha hai?"
            ]
        },
        'usage_tip': 'Keep questions SHORT and concise when intent is unclear. Use the specific phrase for general questions.'
    }


