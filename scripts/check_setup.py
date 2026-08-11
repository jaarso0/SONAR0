#can cutoff before pushing to github


import os, sys, asyncio, httpx
from dotenv import load_dotenv

load_dotenv()
ok = True

def report(name, passed, detail=""):
    global ok
    print(f"{'PASS' if passed else 'FAIL'}  {name}  {detail}")
    ok = ok and passed

async def main():
    report("python>=3.10", sys.version_info >= (3, 10), sys.version.split()[0])

    for var in ["LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET",
                "SARVAM_API_KEY", "GROQ_API_KEY"]:
        report(f"env {var}", bool(os.getenv(var)))

    async with httpx.AsyncClient(timeout=30) as http:
        r = await http.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {os.getenv('GROQ_API_KEY')}"},
            json={"model": "openai/gpt-oss-120b",
                  "messages": [{"role": "user", "content": "say ok"}],
                  "max_tokens": 5},
        )
        report("groq llm", r.status_code == 200, r.text[:120])

        r = await http.post(
            "https://api.sarvam.ai/text-to-speech",
            headers={"api-subscription-key": os.getenv("SARVAM_API_KEY")},
            json={"text": "नमस्ते", "target_language_code": "hi-IN",
                  "model": "bulbul:v3", "speaker": "shubh"},
        )
        report("sarvam tts", r.status_code == 200, r.text[:120])

    from livekit import api
    async with api.LiveKitAPI() as lk:
        await lk.room.list_rooms(api.ListRoomsRequest())
    report("livekit creds", True)

asyncio.run(main())
sys.exit(0 if ok else 1)