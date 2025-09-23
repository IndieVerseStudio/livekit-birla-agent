import logging
import csv
import os
from datetime import datetime, timedelta

from dotenv import load_dotenv
from livekit.agents import (
    NOT_GIVEN,
    Agent,
    AgentFalseInterruptionEvent,
    AgentSession,
    JobContext,
    JobProcess,
    MetricsCollectedEvent,
    RoomInputOptions,
    RunContext,
    WorkerOptions,
    cli,
    metrics,
)
from livekit.agents.llm import function_tool
from livekit.plugins import cartesia, deepgram, noise_cancellation, openai, silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

# Import helper functions from tools
from tools.customer_lookup import _find_customers, _get_data_file_path as get_customer_data_path
from tools.kyc_status_checker import _get_data_file_path as get_kyc_data_path
from tools.phone_verification import _get_data_file_path as get_phone_data_path
from tools.complaint_manager import _load_complaints, _save_complaints, _get_complaints_file_path
from tools.hardcoded_context import hardcoded_context_tool, set_caller_context_tool
from livekit.plugins import google

logger = logging.getLogger("agent")

load_dotenv(".env.local")


class Assistant(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions="""You are Anjali, a 23-year-old professional female customer care agent at Birla Opus specialized in KYC approval and account verification for painters and contractors.

        **STEP 1: INITIAL GREETING (MANDATORY FIRST STEP)**
        - Begin with: "Namaste, welcome to Birla Opus. Mera naam Anjali hai, kaise sahayata kar sakti hun aapki?"
        - LISTEN CAREFULLY to understand the customer's specific issue/problem
        - Wait for customer to fully explain their concern about KYC or account approval
        - Use continuous acknowledgments: 'Ji', 'Haan', 'Okay' throughout the conversation

        **STEP 2: IDENTIFY CUSTOMER AND VERIFY PHONE NUMBER**
        Once you understand they need help with KYC/account approval:
        - First ASK: "Kya aap apne registered mobile number se call kar rahe hain?" (Are you calling from your registered mobile number?)
        - Wait for customer response
        - If customer says YES: Use `hardcoded_context_tool` to get their phone number
        - If customer says NO: Ask: "Kya aap apna Opus ID bata sakte hain verification ke liye?" (Can you provide your Opus ID for verification?)

        **STEP 3: CUSTOMER LOOKUP AND VERIFICATION**
        Based on what information you have:
        - If you have phone number from hardcoded context: Use `customer_lookup_tool` with the phone number
        - If customer provided Opus ID: Use `customer_lookup_by_opus_id_tool` with the provided Opus ID
        - If phone lookup fails: Ask for Opus ID using `customer_lookup_by_opus_id_tool`
        - If customer provides a 10-digit phone number directly: Use `verify_phone_number` tool
        
        **IMPORTANT FALLBACK**: If phone lookup returns "PHONE_LOOKUP_FAILED" or "No accounts found", immediately ask: "Kya aap apna Opus ID bata sakte hain verification ke liye?"

        **STEP 4: CONFIRM CUSTOMER IDENTITY**
        After successful lookup:
        - State the customer's name and ASK for confirmation: "Aapka naam [Customer Name] hai, kya ye sahi hai?"
        - Wait for customer to confirm before proceeding
        - Only after confirmation, say: "Naam confirm karne ke liye dhanyawad"
        - If multiple accounts exist, ask: "Aap jis account ke baare mein baat kar rahe hain uska please mujhe Opus ID bata dijiye"

        **STEP 5: CHECK KYC STATUS AUTOMATICALLY**
        After confirming customer identity:
        - AUTOMATICALLY run `kyc_status_checker_tool` with the customer's opus_id
        - DO NOT ask the customer if their KYC is complete - check it automatically
        - Analyze the results internally before responding to customer

        **STEP 6: EXPLAIN KYC STATUS TO CUSTOMER**
        Based on KYC status results, explain the situation:
        
        **If KYC Status = 'F' (Full KYC Complete):**
        - Calculate days since completion using timeline_info
        - If within 30 days: "Aapka KYC [X] din pehle complete hua hai, abhi [Y] din aur wait karna hoga. Standard process 30 din ka hai."
        - If beyond 30 days: "Main dekh rahi hun aapka KYC [X] din pehle complete hua tha, 30 din ka standard time nikal gaya hai."

        **If KYC Status = 'P' (Partial KYC):**
        - "Main dekh rahi hun aapka KYC abhi complete nahi hua hai."
        - List missing documents from documents_status (Aadhar, PAN, Bank Details, UPI)
        - "Pehle ye documents complete karne honge: [missing documents]"

        **If KYC Status = 'R' (Rejected) or 'N' (Not Started):**
        - "Aapka KYC [rejected/not started] hai. Pehle KYC complete karna hoga."

        **STEP 7: OFFER APPROPRIATE HELP**
        Based on the situation:
        
        **For Beyond 30 Days (KYC Complete):**
        - "Main aapke liye complaint create kar sakti hun jo 7 din mein resolve hogi. Kya main proceed kar sakti hun?"
        - Wait for customer consent before creating complaint

        **For Within 30 Days (KYC Complete):**
        - "Main aapke liye ek enquiry create kar sakti hun tracking ke liye. Kya ye theek rahega?"
        - Wait for customer consent before creating enquiry

        **For Incomplete/Rejected KYC:**
        - "Main aapke liye enquiry create kar sakti hun guidance ke liye?"
        - Guide them to complete KYC first

        **STEP 8: CREATE COMPLAINT/ENQUIRY (ONLY AFTER CONSENT)**
        After customer agrees:
        - For timeline exceeded: Use `create_complaint_tool` with appropriate details
        - For within timeline or incomplete KYC: Use `create_enquiry_tool`
        - Provide confirmation: "Theek hai, main create kar rahi hun"

        **STEP 9: TSM CONTACT SUGGESTION**
        For beyond 30 days cases:
        - Suggest TSM contact: "Ek baar TSM se baat kijiye, Dealer se number le sakte hain"
        - "Please nazdiki dealer ke paas visit kijiye, TSM ka number le kar unse baat kar lijiye"

        **STEP 10: PROVIDE TICKET DETAILS AND CONSOLE**
        - Provide complaint/enquiry number with timeline
        - Console customer: "Nishchint rahiye, hamari team jald se jald aapki madad karegi"
        - Confirm customer received the information

        **STEP 11: ADDITIONAL SUPPORT CHECK**
        - Ask: "Kuch aur sahayata kar sakti hoon?"
        - If same issue clarification: Address additional questions
        - If no additional help needed: Thank and end call

        **STEP 12: CALL CLOSURE**
        - End with: "Birla Opus ke sath jude rehne ke liye dhanyawad, Aapka din shubh rahe"

        **CRITICAL RULES:**
        1. You are Anjali - a 23-year-old professional female customer care agent
        2. ALWAYS ask if calling from registered number before using any lookup tools
        3. ALWAYS confirm customer name - don't assume they've confirmed it
        4. NEVER create complaints/enquiries without first explaining the situation and getting customer consent
        5. Use the correct lookup tool based on what customer provides (phone vs Opus ID)
        6. ALWAYS auto-run kyc_status_checker_tool after customer identification
        7. Create complaints for timeline exceeded cases, enquiries for within timeline/incomplete KYC
        8. Always console customers experiencing delays
        9. **NEVER ASK CUSTOMERS TO CALL BACK LATER** - Always find a way to help them immediately
        10. If phone lookup fails, immediately ask for Opus ID
        11. Use natural, conversational language instead of robotic phrases

        **AVAILABLE TOOLS (USE ONLY THESE):**
        1. `hardcoded_context_tool` - Get caller phone context (when they say YES to registered number)
        2. `customer_lookup_tool` - Look up by mobile number (use phone from hardcoded context)
        3. `customer_lookup_by_opus_id_tool` - Look up by Opus ID (when customer provides Opus ID)
        4. `verify_phone_number` - Verify phone number and get account details
        5. `kyc_status_checker_tool` - Check KYC completion status and timeline (auto-run after identification)
        6. `create_complaint_tool` - Create complaints for delayed approvals (with consent)
        7. `create_enquiry_tool` - Create enquiries for timeline/incomplete KYC cases (with consent)
        8. `auto_create_complaint_tool` - Auto-suggest complaint creation for delays (with consent)

        **LANGUAGE & TONE:**
        - Use mix of Hindi and English as shown in examples
        - Be empathetic and understanding, especially for delayed approvals
        - Maintain professional yet warm tone like a 23-year-old agent
        - Use provided Hindi phrases exactly as specified
        - Always say "Contractor" and "Painter" (don't translate to Hindi)

        **TOOL USAGE ORDER:**
        1. Ask: "Kya aap apne registered mobile number se call kar rahe hain?"
        2. `hardcoded_context_tool` (if YES) OR ask for Opus ID (if NO)
        3. `customer_lookup_tool` OR `customer_lookup_by_opus_id_tool` OR `verify_phone_number`
        4. Confirm customer name
        5. `kyc_status_checker_tool` (automatically after identification)
        6. Explain situation and get consent
        7. `create_complaint_tool` OR `create_enquiry_tool` (after consent)""",
        )

    @function_tool()
    async def hardcoded_context_tool(self, context: RunContext) -> str:
        """Get hardcoded context including the caller's phone number."""
        try:
            phone_number = "9812345769"  # Using a phone number that exists in mock data
            return f"Caller is calling from registered number: {phone_number}"
        except Exception as e:
            return f"Error retrieving hardcoded context: {str(e)}"

    @function_tool()
    async def set_caller_context_tool(self, context: RunContext, phone_number: str) -> str:
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

    @function_tool()
    async def customer_lookup_tool(self, context: RunContext, mobile_number: str) -> str:
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
    async def customer_lookup_by_opus_id_tool(self, context: RunContext, opus_id: str) -> str:
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

    @function_tool()
    async def verify_phone_number(self, context: RunContext, phone_number: str) -> dict:
        """Verify if phone number is registered and get associated accounts."""
        try:
            clean_phone = ''.join(filter(str.isdigit, phone_number))
            
            if len(clean_phone) != 10:
                return {
                    "success": False,
                    "error": "Invalid phone number format. Please provide a 10-digit phone number."
                }
            
            data_file = get_phone_data_path()
            
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

    @function_tool()
    async def kyc_status_checker_tool(self, context: RunContext, opus_id: str) -> dict:
        """Check KYC status and calculate timeline for account approval."""
        try:
            data_file = get_kyc_data_path()
            
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

    @function_tool()
    async def auto_create_complaint_tool(self, context: RunContext, opus_id: str, customer_name: str, days_since_kyc: int) -> dict:
        """Automatically create a complaint if customer has been waiting more than 30 days since KYC completion."""
        try:
            # If more than 30 days, automatically create a complaint
            if days_since_kyc > 30:
                kyc_completion_date = (datetime.now() - timedelta(days=days_since_kyc)).strftime("%Y-%m-%d")
                
                complaint_result = await self.create_complaint_tool(
                    context=context,
                    opus_id=opus_id,
                    customer_name=customer_name,
                    complaint_type="high_priority",
                    subject=f"KYC Account Approval Delay - {days_since_kyc} days pending",
                    issue_description=f"Customer's KYC was completed on {kyc_completion_date} but account approval is still pending after {days_since_kyc} days.",
                    priority="high"
                )
                
                if complaint_result.get("success"):
                    return {
                        "success": True,
                        "auto_complaint_created": True,
                        "days_since_kyc": days_since_kyc,
                        "complaint_number": complaint_result.get("complaint_number"),
                        "message": f"Main aapke liye complaint create kar diya hun kyunki {days_since_kyc} din se zyada ho gaye hain. Aapka complaint number hai {complaint_result.get('complaint_number')}. Aap apne TSM se bhi contact kar sakte hain.",
                        "sms_confirmation": complaint_result.get("sms_confirmation"),
                        "complaint_details": complaint_result.get("complaint_details")
                    }
                else:
                    return {
                        "success": False,
                        "error": f"Failed to create auto-complaint: {complaint_result.get('error')}"
                    }
            else:
                # Within 30 days, no complaint needed
                days_remaining = 30 - days_since_kyc
                return {
                    "success": True,
                    "auto_complaint_created": False,
                    "days_since_kyc": days_since_kyc,
                    "days_remaining": days_remaining,
                    "message": f"Aapka KYC {days_since_kyc} din pehle complete hua tha. Aapko {days_remaining} din aur wait karna hoga account approval ke liye. Aap apne TSM se bhi contact kar sakte hain.",
                    "tsm_message": "Aap apne TSM se contact kar sakte hain additional support ke liye."
                }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Error in auto-complaint creation: {str(e)}"
            }

    @function_tool()
    async def create_complaint_tool(self, context: RunContext, opus_id: str, customer_name: str, complaint_type: str, 
                    subject: str, issue_description: str, priority: str) -> dict:
        """Create a new complaint."""
        try:
            complaints = _load_complaints()
            
            # Generate complaint number
            complaint_number = f"KYC{datetime.now().strftime('%Y%m%d')}{len(complaints) + 1:04d}"
            
            # Set timeline based on priority
            timeline_days = 3 if priority == "high" else 7
            
            # Create complaint record
            new_complaint = {
                "complaint_number": complaint_number,
                "opus_id": opus_id,
                "customer_name": customer_name,
                "type": complaint_type,
                "subject": subject,
                "issue_description": issue_description,
                "priority": priority,
                "status": "active",
                "created_date": datetime.now().isoformat(),
                "timeline_days": timeline_days,
                "expected_resolution": (datetime.now() + timedelta(days=timeline_days)).isoformat(),
                "category": "Painter/contractor Complaints" if complaint_type != "enquiry" else "General enquiries/Others",
                "sub_category": "Opus ID App" if complaint_type != "enquiry" else "Other Enquiries",
                "escalation_level": "high" if priority == "high" else "standard"
            }
            
            complaints.append(new_complaint)
            _save_complaints(complaints)
            
            return {
                "success": True,
                "complaint_created": True,
                "complaint_number": complaint_number,
                "timeline_days": timeline_days,
                "expected_resolution": (datetime.now() + timedelta(days=timeline_days)).strftime("%Y-%m-%d"),
                "message": f"Complaint {complaint_number} successfully created for {customer_name}",
                "sms_confirmation": f"आपका complaint number है {complaint_number}. {timeline_days} दिन में resolve होगा।",
                "complaint_details": new_complaint
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Error creating complaint: {str(e)}"
            }

    @function_tool()
    async def create_enquiry_tool(self, context: RunContext, opus_id: str, customer_name: str, enquiry_type: str, 
                  subject: str, description: str) -> dict:
        """Create a new enquiry (for informational purposes)."""
        try:
            complaints = _load_complaints()
            
            # Generate enquiry number
            enquiry_number = f"ENQ{datetime.now().strftime('%Y%m%d')}{len(complaints) + 1:04d}"
            
            new_enquiry = {
                "enquiry_number": enquiry_number,
                "opus_id": opus_id,
                "customer_name": customer_name,
                "type": "enquiry",
                "enquiry_type": enquiry_type,
                "subject": subject,
                "description": description,
                "status": "logged",
                "created_date": datetime.now().isoformat(),
                "category": "General enquiries/Others",
                "sub_category": "Other Enquiries",
                "issue": "Become a Painter/Contractor"
            }
            
            complaints.append(new_enquiry)
            _save_complaints(complaints)
            
            return {
                "success": True,
                "enquiry_created": True,
                "enquiry_number": enquiry_number,
                "message": f"Enquiry {enquiry_number} logged for {customer_name}",
                "expected_timeline": "2-3 working days for response",
                "enquiry_details": new_enquiry
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Error creating enquiry: {str(e)}"
            }


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


async def entrypoint(ctx: JobContext):
    # Logging setup
    # Add any other context you want in all log entries here
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    # Set up a voice AI pipeline using OpenAI, Cartesia, Deepgram, and the LiveKit turn detector
    session = AgentSession(
        # A Large Language Model (LLM) is your agent's brain, processing user input and generating a response
        # See all providers at https://docs.livekit.io/agents/integrations/llm/
        llm=google.LLM(model="gemini-2.5-flash"),
        # Speech-to-text (STT) is your agent's ears, turning the user's speech into text that the LLM can understand
        # See all providers at https://docs.livekit.io/agents/integrations/stt/
        stt=google.STT(model="telephony", spoken_punctuation=False, languages=["en-IN", "hi-IN"], use_streaming=True),
        # Text-to-speech (TTS) is your agent's voice, turning the LLM's text into speech that the user can hear
        # See all providers at https://docs.livekit.io/agents/integrations/tts/
        tts=google.TTS(gender="female", voice_name="hi-IN-Chirp3-HD-Achernar", language="hi-IN", use_streaming=True),
        # VAD and turn detection are used to determine when the user is speaking and when the agent should respond
        # See more at https://docs.livekit.io/agents/build/turns
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        # allow the LLM to generate a response while waiting for the end of turn
        # See more at https://docs.livekit.io/agents/build/audio/#preemptive-generation
        preemptive_generation=True,
    )

    # To use a realtime model instead of a voice pipeline, use the following session setup instead:
    # session = AgentSession(
    #     # See all providers at https://docs.livekit.io/agents/integrations/realtime/
    #     llm=openai.realtime.RealtimeModel(voice="marin")
    # )

    # sometimes background noise could interrupt the agent session, these are considered false positive interruptions
    # when it's detected, you may resume the agent's speech
    @session.on("agent_false_interruption")
    def _on_agent_false_interruption(ev: AgentFalseInterruptionEvent):
        logger.info("false positive interruption, resuming")
        session.generate_reply(instructions=ev.extra_instructions or NOT_GIVEN)

    # Metrics collection, to measure pipeline performance
    # For more information, see https://docs.livekit.io/agents/build/metrics/
    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Usage: {summary}")

    ctx.add_shutdown_callback(log_usage)

    # # Add a virtual avatar to the session, if desired
    # # For other providers, see https://docs.livekit.io/agents/integrations/avatar/
    # avatar = hedra.AvatarSession(
    #   avatar_id="...",  # See https://docs.livekit.io/agents/integrations/avatar/hedra
    # )
    # # Start the avatar and wait for it to join
    # await avatar.start(session, room=ctx.room)

    # Start the session, which initializes the voice pipeline and warms up the models
    await session.start(
        agent=Assistant(),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            # LiveKit Cloud enhanced noise cancellation
            # - If self-hosting, omit this parameter
            # - For telephony applications, use `BVCTelephony` for best results
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )

    # Join the room and connect to the user
    await ctx.connect()


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
