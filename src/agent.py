import logging

from dotenv import load_dotenv
from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    JobProcess,
    MetricsCollectedEvent,
    RoomInputOptions,
    WorkerOptions,
    cli,
    metrics,
)
from livekit.plugins import silero

from tools.hardcoded_context import hardcoded_context_tool, set_caller_context_tool
from livekit.plugins import google
from constants.instruction import agent_instruction
from tools.hardcoded_context import hardcoded_context_tool, set_caller_context_tool
from tools.customer_lookup import customer_lookup_tool, customer_lookup_by_opus_id_tool
from tools.phone_verification import verify_phone_number
from tools.kyc_status_checker import kyc_status_checker_tool
from tools.complaint_manager import auto_create_complaint_tool, create_complaint_tool, create_enquiry_tool

logger = logging.getLogger("agent")

load_dotenv(".env.local")


class Assistant(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=agent_instruction,
            tools=[
                hardcoded_context_tool, 
                set_caller_context_tool, 
                customer_lookup_tool, 
                customer_lookup_by_opus_id_tool, 
                verify_phone_number,
                kyc_status_checker_tool, 
                auto_create_complaint_tool, 
                create_complaint_tool, 
                create_enquiry_tool
                ]
            )

def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


async def entrypoint(ctx: JobContext):
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    session = AgentSession(
        llm=google.LLM(model="gemini-2.5-flash"),
        stt=google.STT(model="telephony", spoken_punctuation=False, languages=["en-IN"], use_streaming=True),
        tts=google.TTS(gender="female", voice_name="hi-IN-Chirp3-HD-Achernar", language="hi-IN", use_streaming=True),
        vad=silero.VAD.load(),
        allow_interruptions=True,
        discard_audio_if_uninterruptible=False,
        min_interruption_duration=0.1,
        min_interruption_words=0,
        min_endpointing_delay=0.1,
        max_endpointing_delay=0.5,
        resume_false_interruption=False,
        user_away_timeout=15.0,
        false_interruption_timeout=2.0,
        min_consecutive_speech_delay=0.0,
    )

    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Usage: {summary}")

    ctx.add_shutdown_callback(log_usage)

    await session.start(
        agent=Assistant(),
        room=ctx.room,
        room_input_options=RoomInputOptions(),
    )

    await session.generate_reply(
        instructions="Greet the user and offer your assistance."
    )

    await ctx.connect()


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
