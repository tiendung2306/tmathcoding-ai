import asyncio
import sys
import os

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stdin.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

# Ensure app package is importable both inside Docker (/app) and on Host
sys.path.insert(0, "/app")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from pydantic import BaseModel, Field
from app.core.config import settings
from app.core.llm_adapter import llm_adapter

class InteractiveChatResponse(BaseModel):
    thinking: str = Field(description="Brief internal reasoning step of the model")
    reply: str = Field(description="Main response to the user in Vietnamese")

def clean_input_string(s: str) -> str:
    """Removes invalid UTF-8 surrogate characters from terminal stdin."""
    return s.encode('utf-8', 'ignore').decode('utf-8')

async def interactive_cli():
    print("==========================================================")
    print("      🤖 TMATH INTERACTIVE AI CHAT CLI SESSION 🤖         ")
    print("==========================================================")
    print(f" LLM Provider   : {settings.LLM_PROVIDER}")
    print(f" Base URL       : {settings.LLM_BASE_URL}")
    print(f" Model Name     : {settings.LLM_MODEL}")
    print(f" Temperature    : {settings.LLM_TEMPERATURE}")
    print(f" Max Tokens     : {settings.LLM_MAX_TOKENS}")
    print(f" Context Window : {settings.LLM_CONTEXT_WINDOW} tokens (num_ctx)")
    print("----------------------------------------------------------")
    print(" Instructions:")
    print("  - Type your question and press Enter.")
    print("  - Type 'clear' or '/clear' to reset chat memory.")
    print("  - Type 'exit' or 'quit' to terminate the session.")
    print("==========================================================\n")

    history = [
        {"role": "system", "content": "You are a helpful, expert AI Coding Assistant for the tmath Online Judge platform. Reply in Vietnamese clearly and concisely."}
    ]

    loop = asyncio.get_event_loop()

    while True:
        try:
            # Non-blocking async input from user
            raw_input = await loop.run_in_executor(None, input, "\n🧑 You > ")
            user_input = clean_input_string(raw_input.strip())

            if not user_input:
                continue

            if user_input.lower() in ["exit", "quit", "q"]:
                print("\n👋 Exiting AI CLI session. Goodbye!")
                break

            if user_input.lower() in ["clear", "/clear"]:
                history = [history[0]]
                print("🧹 Chat history cleared!")
                continue

            # Add user message to history
            history.append({"role": "user", "content": user_input})

            # Sliding Window Memory: Keep system prompt + last 8 turns (16 messages) to prevent context overflow
            max_history_turns = 8
            if len(history) > (1 + max_history_turns * 2):
                history = [history[0]] + history[-(max_history_turns * 2):]

            print("🤖 AI is thinking...")

            # Format full prompt for LLMAdapter
            conversation_prompt = "\n".join([f"{m['role'].capitalize()}: {m['content']}" for m in history[1:]])

            response = await llm_adapter.generate_structured(
                response_model=InteractiveChatResponse,
                prompt=conversation_prompt,
                system_prompt=history[0]["content"]
            )

            # Store assistant response in history
            clean_reply = clean_input_string(response.reply)
            history.append({"role": "assistant", "content": clean_reply})

            print("\n----------------------------------------------------------")
            print(f"💭 Reasoning: {clean_input_string(response.thinking)}")
            print(f"🤖 AI > {clean_reply}")
            print("----------------------------------------------------------")

        except KeyboardInterrupt:
            print("\n\n👋 Session interrupted by user. Goodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error calling LLM Engine: {e}")

if __name__ == "__main__":
    asyncio.run(interactive_cli())
