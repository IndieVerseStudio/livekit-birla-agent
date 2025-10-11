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
    inference,
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

# Import new tools
from tools.intent_classifier import classify_customer_intent_func, get_intent_clarification_questions_func
from tools.instruction_loader import load_instructions_for_intent_func, get_available_instruction_flows_func, validate_instruction_files_func
from tools.code_history_tool import query_code_history_func
from tools.cash_transfer_tool import cash_transfer_history_func
from tools.account_block_status import account_block_status_func

from livekit.plugins import google

logger = logging.getLogger("agent")

load_dotenv(".env.local")


def load_system_prompt() -> str:
    """Load the system prompt from external file for easier management"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    prompt_file = os.path.join(project_root, 'data', 'Instructions', '_SYSTEM_PROMPT.txt')
    
    try:
        with open(prompt_file, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        logger.error(f"System prompt file not found at {prompt_file}")
        return "You are Anjali, a customer care agent at Birla Opus."
    except Exception as e:
        logger.error(f"Error loading system prompt: {str(e)}")
        return "You are Anjali, a customer care agent at Birla Opus."


class Assistant(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=load_system_prompt(),
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

    # Intent Classification & Instruction Loading Tools
    @function_tool()
    async def classify_customer_intent(self, context: RunContext, customer_query: str) -> dict:
        """Classify customer intent based on their initial query/complaint."""
        return classify_customer_intent_func(customer_query)
    
    @function_tool()
    async def load_instructions_for_intent(self, context: RunContext, intent: str, scenario: str = None) -> dict:
        """Load the appropriate instruction flow based on customer intent."""
        return load_instructions_for_intent_func(intent, scenario)
    
    @function_tool()
    async def get_intent_clarification_questions(self, context: RunContext) -> dict:
        """Get clarifying questions to ask when customer intent is unclear."""
        return get_intent_clarification_questions_func()
    
    @function_tool()
    async def get_available_instruction_flows(self, context: RunContext) -> dict:
        """Get list of all available instruction flows."""
        return get_available_instruction_flows_func()

    # QR Code / Code History Tool
    @function_tool()
    async def code_history_tool(self, context: RunContext, 
                               opus_pc_id: str = None,
                               coupon_code: str = None,
                               limit: int = None,
                               order: str = None,
                               user_type: str = None,
                               caller_opus_pc_id: str = None) -> dict:
        """Query code history by opus_pc_id or coupon_code for QR scanning issues."""
        return query_code_history_func(
            opus_pc_id=opus_pc_id,
            coupon_code=coupon_code,
            limit=limit,
            order=order,
            user_type=user_type,
            caller_opus_pc_id=caller_opus_pc_id
        )

    # Cash Transfer / Point Redemption Tool
    @function_tool()
    async def cash_transfer_history_tool(self, context: RunContext, opus_pc_id: str, limit: int = 3) -> dict:
        """Get cash transfer history and point balance for redemption checks."""
        return cash_transfer_history_func(opus_pc_id=opus_pc_id, limit=limit)

    # Account Block Status Tool
    @function_tool()
    async def account_block_status_tool(self, context: RunContext, 
                                       opus_id: str = None,
                                       mobile_number: str = None) -> dict:
        """Check account block status and provide recommendations."""
        return account_block_status_func(opus_id=opus_id, mobile_number=mobile_number)


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


async def entrypoint(ctx: JobContext):
    # Logging setup
    # Add any other context you want in all log entries here
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    # Set up a voice AI pipeline using OpenAI, Cartesia, Deepgram, and the LiveKit turn detector

    # TTS Configuration - Switch between Gemini and Cartesia by commenting/uncommenting one line
    # GEMINI TTS (currently active):
    # tts_provider = google.beta.GeminiTTS(
    #     model="gemini-2.5-flash-preview-tts",
    #     voice_name="callirrhoe",
    #     instructions="Speak in a friendly and engaging tone. Use a warm, professional voice suitable for customer service in Hindi.",
    # )

    # CARTESIA TTS (uncomment this line and comment the above to switch):
    tts_provider = inference.TTS(
        model="cartesia/sonic-2", 
        voice="f8f5f1b2-f02d-4d8e-a40d-fd850a487b3d",
        language="hi",
        extra_kwargs={"speed": 0.4}
    )

    session = AgentSession(
        llm = inference.LLM(
            model="google/gemini-2.5-flash",
            extra_kwargs={
                "max_completion_tokens": 800,
                "temperature": 0.5,
            }
        ),
        # stt=google.STT(model="telephony", spoken_punctuation=False, languages=["en-IN"], use_streaming=True),
        stt=deepgram.STT(
            model="nova-2", 
            language="hi",
            interim_results=True,  # Get partial results faster
        ),
        tts=tts_provider,
        vad=silero.VAD.load(),
        allow_interruptions=True,
        discard_audio_if_uninterruptible=False,
        
        # AGGRESSIVE EOU DETECTION (Vapi-style - responds in <0.5s after speech ends)
        min_interruption_duration=0.05,     # Reduced from 0.1s - faster interruption detection
        min_interruption_words=0,
        min_endpointing_delay=0.05,         # Reduced from 0.1s - start processing much faster!
        max_endpointing_delay=0.3,          # Reduced from 0.5s - confirm speech ended faster
        min_consecutive_speech_delay=0.0,
        
        resume_false_interruption=False,
        preemptive_generation=True,         # Already enabled - good!
        user_away_timeout=15.0,
        false_interruption_timeout=1.5,     # Reduced from 2.0s - faster false interruption recovery
        
        # STREAMING OPTIMIZATION - Sentence-by-sentence to TTS
        # NOTE: LiveKit AgentSession automatically streams LLM output sentence-by-sentence to TTS
        # This means TTS starts as soon as the first complete sentence is generated
        # No additional configuration needed - it's built into the pipeline!
    )

    # To use a realtime model instead of a voice pipeline, use the following session setup instead:
    # session = AgentSession(
    #     # See all providers at https://docs.livekit.io/agents/integrations/realtime/
    #     llm=openai.realtime.RealtimeModel(voice="marin")
    # )

    # sometimes background noise could interrupt the agent session, these are considered false positive interruptions
    # when it's detected, you may resume the agent's speec

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
            # noise_cancellation=noise_cancellation.BVC(),
        ),
    )

    await session.generate_reply(
        instructions="Greet the user and offer your assistance."
    )

    # Join the room and connect to the user
    await ctx.connect()


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
