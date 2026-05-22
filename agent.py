import os
import re
import time
import requests
from datetime import datetime

# ── CONFIG ────────────────────────────────────────────────────────────────────
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")

SHEET_ID      = "1QZNmClClOrN0Lr40c9cZg-rNbDpv8Yu_FBmNzs5BjEA"
GUMROAD_LINK  = "https://midskilled.gumroad.com/l/Zero-BudgetSolopreneurOS2026"
PRODUCT_NAME  = "Solopreneur OS 2026 – The AI-Powered Side Hustle & Freelance Toolkit"
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
    "quora":    "Write a detailed, genuinely helpful answer to a Quora question about starting a side hustle or freelancing. Provide real value (3-5 specific tips). At the end, naturally mention the toolkit as a resource — don't make it the focus. Tone: knowledgeable, warm, personal. Up to 500 words.",
    "facebook": "Write a Facebook group comment that feels human and community-oriented. Start by engaging with the topic, share a useful insight, then mention the toolkit casually as something that might help. Tone: friendly, conversational, not salesy. Under 200 words.",
    "pinterest":"Write a Pinterest pin description about side hustles, freelancing, or AI tools. Include relevant keywords naturally. End with a soft CTA and the Gumroad link. Under 150 words. Tone: inspiring, punchy, benefit-focused.",
}

# ── READ GOOGLE SHEET ─────────────────────────────────────────────────────────
def get_sheet_rows():
    url = (
        f"https://sheets.googleapis.com/v4/spreadsheets/{SHEET_ID}"
        f"/values/Sheet1!A2:B1000"
        f"?key={os.environ.get('GOOGLE_API_KEY')}"
    )
    try:
        r = requests.get(url, timeout=15)
        return r.json().get("values", [])
    except Exception as e:
        print(f"Sheet read error: {e}")
        return []

# ── FETCH URL CONTENT ─────────────────────────────────────────────────────────
def fetch_url_content(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=10)
        text = re.sub(r"<[^>]+>", " ", r.text)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:2000]
    except Exception as e:
        return f"Could not fetch URL: {e}"

# ── GENERATE DRAFT ────────────────────────────────────────────────────────────
def generate_reply(platform, url, page_content):
    platform_key = platform.lower().strip()
    instructions = PLATFORM_INSTRUCTIONS.get(platform_key, PLATFORM_INSTRUCTIONS["facebook"])

    system_prompt = f"""You are a helpful solopreneur who genuinely wants to help people start side hustles and freelance businesses. You have a product you mention naturally — never spammily.

Product: {PRODUCT_NAME}
Price: {PRODUCT_PRICE}
Link: {GUMROAD_LINK}
Details: {PRODUCT_SUMMARY}

Rules:
- Lead with genuine value. Help first, promote second.
- Mention the product only once, near the end, only if relevant.
- Never reveal you are automated or an AI.
- Sound like a real person who has been through the freelancing struggle.
"""

    user_prompt = f"""Platform: {platform}
URL: {url}
Page content excerpt: {page_content[:1200]}

Task: {instructions}

Write the reply now."""

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://midskilled.gumroad.com",
    }
    body = {
        "model": "meta-llama/llama-3.1-8b-instruct:free",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
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
        return r.json()["choices"][0]["message"]["content"].strip()
    return f"ERROR {r.status_code}: {r.text[:200]}"

# ── SAVE DRAFTS TO FILE ───────────────────────────────────────────────────────
def save_drafts(drafts):
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        f"SOLOPRENEUR AGENT DRAFTS — {timestamp}",
        f"{len(drafts)} draft(s) ready to post.",
        "=" * 60,
    ]

    for i, d in enumerate(drafts, 1):
        lines += [
            f"\n#{i} [{d['platform'].upper()}]",
            f"URL: {d['url']}",
            f"\n{d['draft']}",
            "\n" + "-" * 60,
        ]

    lines += [
        "\nHOW TO USE:",
        "1. Copy each draft above",
        "2. Go to the platform URL",
        "3. Paste and post",
        f"\nProduct link: {GUMROAD_LINK}",
    ]

    output = "\n".join(lines)

    # save to file for GitHub Actions artifact
    with open("drafts.txt", "w") as f:
        f.write(output)

    # also print to console so it shows in GitHub Actions logs
    print("\n" + "=" * 60)
    print("DRAFTS READY:")
    print("=" * 60)
    print(output)

# ── MAIN ──────────────────────────────────────────────────────────────────────
def run_agent():
    print(f"\n{'='*50}")
    print(f"Agent run: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'='*50}")

    rows = get_sheet_rows()
    if not rows:
        print("Sheet is empty. Add URLs to column A and platform to column B.")
        return

    drafts = []

    for i, row in enumerate(rows):
        if len(row) < 2:
            continue
        url, platform = row[0].strip(), row[1].strip()
        if not url or not platform:
            continue

        print(f"\nRow {i+2}: [{platform}] {url[:70]}")
        page_content = fetch_url_content(url)
        print(f"  Fetched {len(page_content)} chars")

        draft = generate_reply(platform, url, page_content)
        print(f"  Draft generated ({len(draft)} chars)")

        drafts.append({"platform": platform, "url": url, "draft": draft})
        time.sleep(2)

    save_drafts(drafts)
    print(f"\nDone. {len(drafts)} draft(s) processed.")

if __name__ == "__main__":
    run_agent()
