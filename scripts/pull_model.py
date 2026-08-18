import os
import sys
import httpx
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8')

# Load .env variables from root or backend
load_dotenv(dotenv_path="/.env")
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", "backend", ".env"))

def main():
    model_name = os.getenv("LLM_MODEL", "qwen2.5-coder:14b")
    base_url = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")
    
    # Deriving Ollama root endpoint from OpenAI-compatible endpoint
    ollama_api = base_url.replace("/v1", "/api/pull")

    print("=== TMATH OLLAMA MODEL PULLER ===")
    print(f"Target Model   : {model_name}")
    print(f"Ollama API     : {ollama_api}")
    print("---------------------------------")
    print(f"Sending pull request to Ollama...")

    try:
        with httpx.stream("POST", ollama_api, json={"name": model_name}, timeout=None) as response:
            if response.status_code == 200:
                print("Pulling model layers... (this may take a few minutes depending on network speed)")
                for line in response.iter_lines():
                    if line:
                        print(f"--> {line}")
                print("\n✅ SUCCESS: Model pulled and ready for inference!")
            else:
                print(f"❌ Error: Received status code {response.status_code}")
                print(response.text)
    except Exception as e:
        print(f"❌ Failed to connect to Ollama at {ollama_api}.")
        print(f"Details: {e}")
        print("Tip: Make sure Ollama container or desktop app is running (`docker-compose up -d`).")

if __name__ == "__main__":
    main()
