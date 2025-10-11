from constants.instruction_mapping import Instruction

intent_patterns = {
    Instruction.KYC_APPROVAL.NAME: [
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
    Instruction.POINT_REDEMPTION.NAME: [
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
    Instruction.QR_SCANNING.NAME: [
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
    Instruction.ACCOUNT_BLOCKED.NAME: [
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

