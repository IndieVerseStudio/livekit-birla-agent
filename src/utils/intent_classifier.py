import re
from typing import Tuple
from constants.intents import intent_patterns
from constants.instruction_mapping import Instruction

class IntentClassifier:
    def classify_intent(self, customer_query: str) -> Tuple[str, float, str]:
        """
        Classify customer intent based on their query

        Args:
            customer_query: Customer's initial complaint or query

        Returns:
            Tuple of (intent, confidence_score, description)
        """
        if not customer_query:
            return 'UNCLEAR', 0.0, Instruction.UNCLEAR.DESCRIPTION

        query_lower = customer_query.lower()
        intent_unique_hits = {}

        for intent, patterns in intent_patterns.items():
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
            return 'UNCLEAR', 0.0, Instruction.UNCLEAR.DESCRIPTION

        # Confidence: base + fraction of patterns matched (keeps >= ~0.2 when any match)
        confidence = min(0.2 + 0.6 * (best_hits / max(total_patterns, 1)), 0.95)

        # If confidence is still too low (very unlikely), mark as unclear
        if confidence < 0.15:
            return 'UNCLEAR', confidence, Instruction.UNCLEAR.DESCRIPTION

        return best_intent, confidence, getattr(Instruction, best_intent).DESCRIPTION

    def get_intent_instruction(self, intent: str) -> str:
        mapping = getattr(Instruction, intent).SRC
        if mapping:
            return mapping

        return Instruction.UNCLEAR.SRC