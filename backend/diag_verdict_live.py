"""Run current public verification pipeline; no native AI shortcut."""
import asyncio
import json
import os
import httpx

TEST_CLAIM = "Kepala Badan Gizi Nasional (BGN) Dadan ditangkap atas kasus korupsi"

async def main():
    async with httpx.AsyncClient(timeout=120, trust_env=False) as client:
        response = await client.post(
            os.getenv("FAKTAIN_API_URL", "http://127.0.0.1:8000").rstrip("/") + "/analyze",
            json={"text": TEST_CLAIM},
        )
        response.raise_for_status()
        print(json.dumps(response.json(), ensure_ascii=False, indent=2))

if __name__ == "__main__":
    asyncio.run(main())
