# Voice Agent Issues Analysis & Fixes

## Issue Summary
Date: 2025-10-11
Agent: Anjali (Birla Opus Customer Care)
Test Conversation: KYC Approval Flow

---

## 🔴 Issue #1: Double/Repeated Responses ("Ap nishchint rahiye" said twice)

### Problem Description
When the bot handles KYC queries, it responds with a message first (e.g., "Pareshani ke liye maafi chahungi, kaise sahayata kar sakti hun main aapki?"), then executes tool calls, and then responds AGAIN with a similar reassurance message ("Ap nishchint rahiye, main aapki puri sahayata karungi").

### Evidence from Transcript
```
AGENT: "Pareshani ke liye maafi chahungi, kaise sahayata kar sakti hun main aapki?"
YOU: "Mujhe KYC karvani hai"
AGENT: 
  "Haan sir, main samajh pa rhi hun. Ap nishchint rahiye, main aapki puri sahayata karungi."
  "Haan sir, main samajh pa rhi hun ki aapko apni KYC karwani hai. Ap nishchint rahiye main aapki puri sahayata karungi."
  "Kya aap apne registered mobile number se call kar rahe hain?"
```

### Root Cause Analysis

**Core Files to Investigate:**
1. `src/agent.py` (lines 46-182) - Main agent instructions
2. `data/Instructions/Enhanced_KYC_Approval_Contractor.txt` - KYC flow instructions
3. LLM behavior with tool calling

**Probable Causes:**

1. **Instruction Conflict**: Two sets of instructions are active simultaneously:
   - **Base Agent Instructions** (line 177 in `agent.py`): `"When helping: 'Ap nishchint rahiye, main aapki puri sahayata karungi'"`
   - **Loaded KYC Flow Instructions** (Enhanced_KYC_Approval_Contractor.txt): Contains similar reassurance patterns

2. **Tool Call Flow**:
   - Step 1: LLM receives user message "Mujhe KYC karvani hai"
   - Step 2: LLM calls `classify_customer_intent` tool
   - Step 3: Tool returns intent = KYC_APPROVAL
   - Step 4: LLM generates response acknowledging understanding
   - Step 5: LLM calls `load_instructions_for_intent` tool
   - Step 6: **NEW instructions loaded into context**
   - Step 7: LLM generates ANOTHER response based on newly loaded instructions
   - Result: **Double response pattern**

3. **Missing Consolidation Rule**: The agent instructions say to do "SILENT MULTI-TOOL EXECUTION" (line 90) but this isn't being enforced consistently.

### Proposed Fixes

**Fix Option A: Modify Agent Base Instructions** (Recommended)
- Remove the generic reassurance phrase from line 177
- Make consolidation rule more explicit and strict
- Add instruction: "After loading intent-specific instructions, DO NOT send acknowledgment. Proceed directly with the loaded flow."

**Fix Option B: Modify Loaded Instructions**
- Update Enhanced_KYC_Approval_Contractor.txt to remove redundant reassurance
- Streamline the greeting/acknowledgment phase

**Fix Option C: Add LLM Instruction Enforcement**
- Add explicit rule: "After calling `classify_customer_intent` and `load_instructions_for_intent`, combine all responses into ONE message only."
- Update Step 5A to be more forceful about single consolidated replies

---

## 🔴 Issue #2: TTS Pronunciation of "Aap" as "A P" (Letter-by-letter)

### Problem Description
When the LLM generates text containing "Ap" or "aap", the Google TTS speaks it as individual letters "A" "P" instead of the Hindi word "आप" (aap - formal you).

### Evidence
```
Text generated: "Ap nishchint rahiye"
TTS output: "A P nishchint rahiye" (speaks letters)
Expected: "Aap nishchint rahiye" (speaks word)
```

### Root Cause Analysis

**Core Files to Investigate:**
1. `src/agent.py` (line 631) - TTS configuration
2. Agent instruction templates containing "Ap"

**Probable Causes:**

1. **Spelling Inconsistency**: The instructions use "Ap" (without double 'a') which TTS interprets as an abbreviation/acronym
   - "Ap" → TTS thinks: abbreviation → spells out letters
   - "Aap" → TTS thinks: Hindi word → pronounces correctly

2. **TTS Language Model Ambiguity**: 
   - Current TTS config: `language="hi-IN"` but text contains mixed Hindi/English
   - TTS model may not reliably detect context for single/double letter words

3. **Instruction Template Issues**: Multiple instances in instructions use "Ap" instead of "Aap":
   - Line 177 in agent.py: `"Ap nishchint rahiye"`
   - Multiple instances in Enhanced_KYC_Approval_Contractor.txt

### Proposed Fixes

**Fix Option A: Standardize Spelling to "Aap"** (Recommended - Easiest)
1. Global search-replace all instances of " Ap " → " Aap "
2. Update agent instructions
3. Update all instruction files
4. This ensures TTS always recognizes it as the Hindi word

**Fix Option B: Use SSML Tags**
- Wrap "Ap" in SSML phoneme tags to force pronunciation
- Example: `<phoneme alphabet="ipa" ph="ɑːp">Ap</phoneme>`
- Requires checking if Google TTS plugin supports SSML in LiveKit

**Fix Option C: Replace with Full Hindi**
- Replace "Ap" with Devanagari "आप" in all templates
- More authentic but may cause other rendering issues

---

## 🔴 Issue #3: Phone Numbers Spoken as Large Numbers (e.g., "89 million")

### Problem Description
When the bot returns phone numbers, the TTS reads them as large numbers (e.g., "9812345769" becomes "nine hundred eighty-one million...") instead of reading digit-by-digit.

### Evidence
```
Expected: "nine eight one two three four five seven six nine"
Actual: "nine hundred eighty-one million, two hundred thirty-four thousand, five hundred seventy-six point nine"
```

### Root Cause Analysis

**Core Files to Investigate:**
1. `src/agent.py` (lines 185-301) - Tools that return phone numbers
2. `src/tools/customer_lookup.py` - Phone number formatting
3. `src/tools/phone_verification.py` - Phone number handling
4. TTS preprocessing

**Probable Causes:**

1. **Number Formatting**: Phone numbers are returned as raw digit strings "9812345769"
   - TTS naturally interprets continuous digits as numerical values
   - No formatting to indicate individual digits

2. **Tool Output Format**: Customer lookup tools return phone numbers as:
   ```python
   {"mobile_number": "9812345769"}  # Interpreted as number
   ```

3. **LLM Context**: When LLM mentions phone numbers, it writes them as continuous strings without spacing or formatting

### Proposed Fixes

**Fix Option A: Format with Spaces in Tool Output** (Recommended)
```python
# In customer_lookup_tool and verify_phone_number
phone_formatted = " ".join(phone_number)  # "9 8 1 2 3 4 5 7 6 9"
return f"Phone number: {phone_formatted}"
```

**Fix Option B: Format with Dashes**
```python
# Format as: 981-234-5769
phone_formatted = f"{phone[:3]}-{phone[3:6]}-{phone[6:]}"
```

**Fix Option C: Add LLM Instruction**
Add to agent instructions:
```
"When mentioning phone numbers, ALWAYS format them with spaces between each digit.
Example: Instead of '9812345769', say 'nine eight one two three four five seven six nine'
Or write as: '9 8 1 2 3 4 5 7 6 9'"
```

**Fix Option D: SSML Say-As Digit**
If TTS supports SSML:
```xml
<say-as interpret-as="digits">9812345769</say-as>
```

---

## 📋 Recommended Fix Priority

### Priority 1: Issue #2 (TTS "Ap" pronunciation) - **QUICK WIN**
- **Effort**: Low (simple find-replace)
- **Impact**: High (affects every conversation)
- **Fix**: Replace all " Ap " with " Aap " in instructions

### Priority 2: Issue #3 (Phone number pronunciation) - **MEDIUM EFFORT**
- **Effort**: Medium (update multiple tool functions)
- **Impact**: High (critical for verification flows)
- **Fix**: Format phone numbers with spaces in tool outputs + add LLM instruction

### Priority 3: Issue #1 (Double responses) - **REQUIRES TESTING**
- **Effort**: Medium-High (instruction refinement + testing)
- **Impact**: Medium (annoying but not breaking functionality)
- **Fix**: Strengthen consolidation rules + remove redundant phrases

---

## 🔧 Implementation Plan

1. **Phase 1: Quick Fixes**
   - Fix "Ap" → "Aap" spelling (Issue #2)
   - Format phone numbers with spaces (Issue #3)

2. **Phase 2: Instruction Optimization**
   - Consolidate and deduplicate agent instructions
   - Add strict single-response enforcement (Issue #1)

3. **Phase 3: Testing & Validation**
   - Test full KYC flow
   - Test point redemption flow
   - Test QR scanning flow
   - Verify all pronunciation and response patterns

---

## 📝 Files Requiring Changes

### For Issue #2 (Aap pronunciation):
- `src/agent.py` (line 177)
- `data/Instructions/Enhanced_KYC_Approval_Contractor.txt` (multiple lines)
- All other instruction files in `data/Instructions/`

### For Issue #3 (Phone numbers):
- `src/tools/customer_lookup.py`
- `src/tools/phone_verification.py`
- `src/agent.py` (lines 210-301 - tool implementations)

### For Issue #1 (Double responses):
- `src/agent.py` (lines 90-117 - consolidation rules)
- `src/agent.py` (lines 174-180 - conversational guide)
- Possibly: `data/Instructions/Enhanced_KYC_Approval_Contractor.txt`

---

## Next Steps

Would you like me to:
1. Start with Priority 1 (Quick win: Fix "Ap" → "Aap")?
2. Implement all Phase 1 quick fixes together?
3. Discuss and review each fix approach in detail before implementing?

