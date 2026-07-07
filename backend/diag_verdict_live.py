"""
Diagnostic script: Reproduce verdict-source contradiction bug

User reported: claim "Kepala BGN Dadan ditangkap korupsi" returned verdict
KEMUNGKINAN HOAKS (score 12) with reasoning "tidak ada bukti resmi", but all
sources found are legitimate news confirming Dadan was detained (Kejagung,
detik, Antara). This is a dangerous inversion.

This script:
1. Runs _web_research to see what brief + sources are gathered
2. Runs analyze_text to see final verdict
3. Prints intermediate + final output to diagnose the root cause
"""
import asyncio
import json
import sys
import os

# Add backend dir to path so we can import app modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from app.services.llm_service import _web_research, analyze_text, _chat_completion, ANALYSIS_PROMPT
from datetime import datetime, timezone, timedelta

# Test claim from user report
TEST_CLAIM = "Kepala Badan Gizi Nasional (BGN) Dadan ditangkap atas kasus korupsi"


async def main():
    print("=" * 80)
    print("DIAGNOSTIC: Verdict-Source Contradiction Bug")
    print("=" * 80)
    print(f"\nTest claim: {TEST_CLAIM}\n")
    
    today = datetime.now(timezone(timedelta(hours=7))).strftime("%d %B %Y")
    print(f"Analysis date: {today}\n")
    
    # --- Step 1: Web research (what does the search return?) ---
    print("=" * 80)
    print("STEP 1: Web Research (_web_research)")
    print("=" * 80)
    try:
        brief, sources = await _web_research(TEST_CLAIM, today)
        print("\n[BRIEF RETURNED]:")
        print(brief)
        print("\n[SOURCES FOUND]:")
        if sources:
            for i, src in enumerate(sources, 1):
                print(f"{i}. {src['title']}")
                print(f"   URL: {src['url']}")
                print(f"   Credibility: {src['credibility']}")
        else:
            print("(no sources returned)")
    except Exception as e:
        print(f"ERROR in web research: {e}")
        brief, sources = "", []
    
    # --- Step 2: Full analysis (does it misread the brief?) ---
    print("\n" + "=" * 80)
    print("STEP 2: Full Analysis (analyze_text)")
    print("=" * 80)
    try:
        result = await analyze_text(TEST_CLAIM)
        print("\n[VERDICT]:", result.get("verdict"))
        print("[CONFIDENCE SCORE]:", result.get("confidence_score"))
        print("[REASONING]:", result.get("reasoning"))
        print("\n[VERIFIED CLAIMS]:")
        for claim in result.get("verified_claims", []):
            print(f"  - {claim.get('claim')}")
            print(f"    Status: {claim.get('status')}")
            print(f"    Explanation: {claim.get('explanation')}")
        print("\n[SOURCES IN FINAL RESULT]:")
        for i, src in enumerate(result.get("sources_found", []), 1):
            print(f"{i}. {src['title']} ({src['credibility']})")
    except Exception as e:
        print(f"ERROR in analysis: {e}")
    
    # --- Diagnosis ---
    print("\n" + "=" * 80)
    print("DIAGNOSIS")
    print("=" * 80)
    print("\nPossible root causes:")
    print("1. Brief mischaracterized sources (e.g. said 'debunked' when sources confirm)")
    print("2. Analysis prompt misinterpreted 'klarifikasi' in brief as 'claim debunked'")
    print("3. Date confusion (sources from June 2026, current date is June 2026)")
    print("4. Model hallucinated a 'no evidence' conclusion despite brief having evidence")
    print("\nCheck the BRIEF output above to see if it correctly summarized the sources.")


if __name__ == "__main__":
    asyncio.run(main())
