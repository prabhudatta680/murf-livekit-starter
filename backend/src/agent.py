import logging

from dotenv import load_dotenv
from livekit import rtc
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    JobProcess,
    RunContext,
    cli,
    function_tool,
    inference,
    tokenize,
    room_io,
)
from livekit.plugins import murf, silero, google, deepgram, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel

from db import lookup_caller, save_caller_info

logger = logging.getLogger("agent")

load_dotenv(".env.local")

# Change this prompt to change what your voice agent does.
# See README.md for example prompts (customer support, language tutor, receptionist).
SYSTEM_PROMPT = """
IDENTITY
You are Abhinav, a voice assistant for farmers in India, built for the Farm & Field
program. You are not a government official, not a licensed agronomist, and not a
substitute for a local agriculture officer â€” you are a helpful first point of contact.

OBJECTIVES
A successful call does one of these:
1. Gives the farmer a clear, practical next step for their crop, weather, or scheme question.
2. Clearly flags any price or scheme information as something to verify locally, never as guaranteed fact.
3. Escalates anything serious or uncertain to a real person instead of guessing.

KNOWLEDGE
You can discuss general crop care practices, common pest and weather patterns, how
government agricultural schemes typically work, and how to find local market prices.
You do NOT have live access to today's actual market prices, weather forecasts, or
scheme approval status. When asked for these, say so plainly and suggest where to check
(local mandi board, Krishi Vigyan Kendra, official scheme portal).

LANGUAGE
Mirror the user's language and mix. If they speak Hindi, reply in Hindi. If they mix
Hindi and English mid-sentence, reply in that same mixed register rather than switching
to pure Hindi or pure English. If they speak another Indian language, reply in that
language if you can, or tell them honestly which languages you support. Keep formality
casual and warm, like a knowledgeable neighbor, not a government office.

MEMORY
You can remember callers across calls using the lookup_caller_info and remember_caller
tools. At the very start of a call, use lookup_caller_info to check if you already know
this person. If you do, greet them by name and naturally reference what you already know
(e.g. "Namaste Ramesh, last time we spoke about your cotton. Did the spraying help?").
If you learn something new and worth remembering (their name, crops, land size, district,
irrigation type), ASK PERMISSION FIRST, e.g. "I'd like to remember that you grow cotton on
5 acres, is that okay?" Only call remember_caller if they clearly agree. If they decline or
don't respond clearly, do not save anything.

GUARDRAILS
- Never state a market price as current fact without a source and date attached.
  Instead say something like: "I don't have today's confirmed price â€” check your
  local mandi board or krishi price app for the latest."
- Never guarantee that a government scheme application will be approved, or that
  someone is definitely eligible. Only explain how eligibility generally works and
  how to apply or check officially.
- Never diagnose a crop disease with certainty from a description alone. Offer
  possibilities, then recommend confirming with a local agriculture officer.
- If the situation sounds urgent or serious (major crop loss, pesticide poisoning,
  injury, livestock emergency), immediately say: "This needs someone who can actually
  see your field or the situation in person. Please contact your nearest Krishi Vigyan
  Kendra or local agriculture officer right away â€” I can't confirm this myself."
- Never claim to be a government official, doctor, or certified agronomist.
- Never save anything to memory without the caller's explicit spoken consent first.

STYLE
Short sentences. Practical, plain language, no jargon. No complex formatting, emojis,
or symbols, since this is spoken aloud. If the user pauses or is silent, gently check
in rather than repeating yourself.
"""


class Assistant(Agent):
    def __init__(self, user_id: str) -> None:
        super().__init__(instructions=SYSTEM_PROMPT)
        # user_id identifies the caller across calls so we can look up and save
        # their record. It comes from the LiveKit participant identity.
        self.user_id = user_id

    @function_tool
    async def lookup_caller_info(self, context: RunContext):
        """Use this once, early in the call, to check whether you have spoken
        with this caller before.

        Returns the caller's saved name, language preference, and farming facts
        if they exist, or indicates this is a new caller if there's no record yet.
        """
        logger.info(f"Looking up caller {self.user_id}")
        record = lookup_caller(self.user_id)
        if record is None:
            return {"found": False}
        return {"found": True, **record}

    @function_tool
    async def remember_caller(
        self,
        context: RunContext,
        name: str,
        crops: str = "",
        land_size: str = "",
        district: str = "",
        irrigation_type: str = "",
        language_preference: str = "en",
    ):
        """Call this ONLY after the caller has clearly and explicitly agreed to
        let you remember this information about them. Do not call this if they
        declined or if consent was not clearly given.

        Args:
            name: The caller's name.
            crops: Crops they grow, if mentioned and agreed to save.
            land_size: Size of their land, if mentioned and agreed to save.
            district: Their district/location, if mentioned and agreed to save.
            irrigation_type: Their irrigation method, if mentioned and agreed to save.
            language_preference: Language they prefer to speak in, e.g. "hi" or "en".
        """
        facts = {
            k: v
            for k, v in {
                "crops": crops,
                "land_size": land_size,
                "district": district,
                "irrigation_type": irrigation_type,
            }.items()
            if v
        }
        logger.info(f"Saving caller {self.user_id}: name={name}, facts={facts}")
        save_caller_info(self.user_id, name, facts, language_preference)
        return "Saved."


server = AgentServer()


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


@server.rtc_session(agent_name="my-agent")
async def my_agent(ctx: JobContext):
    # Logging setup
    # Add any other context you want in all log entries here
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    # Connect to the room first so we can identify who's calling before starting
    # the session. The participant's identity becomes our user_id for memory lookups.
    await ctx.connect()
    participant = await ctx.wait_for_participant()
    user_id = participant.identity
    logger.info(f"Caller connected with identity: {user_id}")

    # Set up a voice AI pipeline using Murf Falcon, Gemini, Deepgram, and the LiveKit turn detector
    session = AgentSession(
        # Speech-to-text (STT) is your agent's ears, turning the user's speech into text that the LLM can understand
        # See all available models at https://docs.livekit.io/agents/models/stt/
        stt=deepgram.STT(model="nova-3", language="multi"),
        # A Large Language Model (LLM) is your agent's brain, processing user input and generating a response
        # See all available models at https://docs.livekit.io/agents/models/llm/
        llm=google.LLM(
                model="gemini-3.5-flash-lite",
            ),
        # Text-to-speech (TTS) is your agent's voice, turning the LLM's text into speech that the user can hear
        # See all available models as well as voice selections at https://docs.livekit.io/agents/models/tts/
        tts=murf.TTS(
                voice="Abhinav",
                style="Conversational",
                tokenizer=tokenize.basic.SentenceTokenizer(min_sentence_len=2),
                text_pacing=True
            ),
        # VAD and turn detection are used to determine when the user is speaking and when the agent should respond
        # See more at https://docs.livekit.io/agents/build/turns
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        # allow the LLM to generate a response while waiting for the end of turn
        # See more at https://docs.livekit.io/agents/build/audio/#preemptive-generation
        preemptive_generation=True,
    )

    # Start the session, which initializes the voice pipeline and warms up the models
    await session.start(
        agent=Assistant(user_id=user_id),
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                noise_cancellation=lambda params: (
                    noise_cancellation.BVCTelephony()
                    if params.participant.kind
                    == rtc.ParticipantKind.PARTICIPANT_KIND_SIP
                    else noise_cancellation.BVC()
                ),
            ),
        ),
    )


if __name__ == "__main__":
    cli.run_app(server)
