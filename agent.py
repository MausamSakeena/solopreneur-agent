import os
import re
import json
import time
import requests
from datetime import datetime

# ── CONFIG ────────────────────────────────────────────────────────────────────
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
SHEET_ID = "1QZNmClClOrN0Lr40c9cZg-rNbDpv8Yu_FBmNzs5BjEA"
GUMROAD_LINK = "https://midskilled.gumroad.com/l/Zero-BudgetSolopreneurOS2026"
PRODUCT_NAME = "Solopreneur OS 2026 – The AI-Powered Side Hustle & Freelance Toolkit"
PRODUCT_PRICE = "$29"

PRODUCT_SUMMARY = """
The Solopreneur OS 2026 is a complete AI-powered toolkit for anyone starting a side hustle or freelance business with zero startup budget.

What's included:
- 8-tab Excel workbook: income tracker, client CRM, invoice generator, hustle idea validator with ROI calculator, content calendar, budget planner, goals tracker
- 6 professional PDFs: freelance contract, client proposal, 25 copy-paste email templates, 30-day first-sale plan, 100+ AI prompts for Claude/ChatGPT, Notion OS guide
- Notion Business OS: 7 linked databases for tasks, projects, clients, content, finances, knowledge, and goals
- Zero-cost marketing kit with 8 promo post templates

Price: $29 one-time. No subscription. Yours forever.
"""

PLATFORM_INSTRUCTIONS = {
    "quora": "Write a detailed, genuinely helpful answer to a Quora question about starting a side hustle or freelancing. Provide real value (3-5 specific tips). At the end, naturally mention the toolkit as a resource — don't make it the focus. Tone: knowledgeable, warm, personal.",
    "facebook": "Write a Facebook group comment or post that feels human and community-oriented. Start by engaging with the topic, share a useful insight, then mention the toolkit casually as something that might help. Tone: friendly, conversational, not salesy.",
    "pinterest": "Write a Pinterest pin description for a pin about side hustles, freelancing, or AI tools. Include relevant keywords naturally. End with a soft CTA and the link. Keep it under 150 words. Tone: inspiring, punchy, benefit-focused.",
}

SHEET_API_BASE = f"https://sheets.googleapis.com/v4/spreadsheets/{SHEET_ID}"

# ── GOOGLE SHEETS (via public API with API key, or service account) ───────────
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")

def get_sheet_rows():
    """Fetch all rows from the sheet."""
    url = f"{SHEET_API_BASE}/values/Sheet1!A2:D1000?key={GOOGLE_API_KEY}"
    r = requests.get(url, timeout=15)
    data = r.json()
    rows = data.get("values", [])
    return rows

def update_sheet_cell(row_index, col, value):
    """Update a single cell. row_index is 1-based (row 2 = index 1 in data = row 2 in sheet)."""
    sheet_row = row_index + 2  # +2 because row 1 is header, data starts at row 2
    range_notation = f"Sheet1!{col}{sheet_row}"
    url = f"{SHEET_API_BASE}/values/{range_notation}?valueInputOption=RAW&key={GOOGLE_API_KEY}"
    body = {"values": [[value]]}
    r = requests.put(url, json=body, timeout=15)
    return r.status_code == 200

# ── FETCH URL CONTENT ─────────────────────────────────────────────────────────
def fetch_url_content(url):
    """Try to get readable text from a URL."""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; SoloAgentBot/1.0)"}
        r = requests.get(url, headers=headers, timeout=10)
        # strip HTML tags naively
        text = re.sub(r"<[^>]+>", " ", r.text)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:3000]  # limit context
    except Exception as e:
        return f"Could not fetch URL: {e}"

# ── OPENROUTER AI CALL ────────────────────────────────────────────────────────
def generate_reply(platform, url, page_content):
    """Call OpenRouter free model to draft a reply."""
    platform_key = platform.lower().strip()
    instructions = PLATFORM_INSTRUCTIONS.get(platform_key, PLATFORM_INSTRUCTIONS["facebook"])

    system_prompt = f"""You are a helpful solopreneur who genuinely wants to help people start side hustles and freelance businesses. You have a product that you mention naturally — never spammily.

Product: {PRODUCT_NAME}
Price: {PRODUCT_PRICE}
Link: {GUMROAD_LINK}
Details: {PRODUCT_SUMMARY}

Rules:
- Always lead with genuine value. Help first, promote second.
- Only mention the product once, near the end, and only if it's relevant.
- Never say "as an AI" or reveal you're automated.
- Sound like a real person who's been through the freelancing struggle.
- Keep replies focused and under 300 words unless it's Quora (up to 500 words is fine).
"""

    user_prompt = f"""Platform: {platform}
URL: {url}
Page content (excerpt): {page_content[:1500]}

Task: {instructions}

Write the reply now."""

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://midskilled.gumroad.com",
    }

    body = {
        "model": "mistralai/mistral-7b-instruct:free",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "max_tokens": 600,
        "temperature": 0.8,
    }

    r = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers=headers,
        json=body,
        timeout=30,
    )

    if r.status_code == 200:
        data = r.json()
        return data["choices"][0]["message"]["content"].strip()
    else:
        return f"ERROR: OpenRouter returned {r.status_code}: {r.text[:200]}"

# ── MAIN AGENT LOOP ───────────────────────────────────────────────────────────
def run_agent():
    print(f"\n{'='*50}")
    print(f"Agent run started: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'='*50}")

    rows = get_sheet_rows()

    if not rows:
        print("No rows found in sheet. Add URLs to column A and platform to column B.")
        return

    processed = 0
    skipped = 0

    for i, row in enumerate(rows):
        # pad row to 4 columns
        while len(row) < 4:
            row.append("")

        url, platform, status, draft = row[0], row[1], row[2], row[3]

        if not url or not platform:
            skipped += 1
            continue

        if status.lower() in ("done", "posted", "skip", "error"):
            skipped += 1
            continue

        if status.lower() == "ready":
            skipped += 1
            continue

        print(f"\nProcessing row {i+2}: [{platform}] {url[:60]}...")

        # fetch page content
        page_content = fetch_url_content(url)
        print(f"  Fetched {len(page_content)} chars from URL")

        # generate reply
        draft_reply = generate_reply(platform, url, page_content)
        print(f"  Generated reply ({len(draft_reply)} chars)")

        # write back to sheet: status = Ready, draft = the reply
        update_sheet_cell(i, "C", "Ready")
        update_sheet_cell(i, "D", draft_reply)
        print(f"  ✓ Written to sheet row {i+2}")

        processed += 1
        time.sleep(2)  # be polite to OpenRouter rate limits

    print(f"\nDone. Processed: {processed} | Skipped: {skipped}")

if __name__ == "__main__":
    run_agent()
