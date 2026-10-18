#!/usr/bin/env python3
"""Create the Superteam Earn submission for TrustShift (HackYeah Poland track)."""
import json
import urllib.request

CREDS = "/home/ubuntu/Projects/x402-seller/superteam_creds.json"
key = json.load(open(CREDS))["apiKey"]

body = {
    "listingId": json.load(open("/tmp/st_listings.json"))[0]["id"],
    "link": "https://github.com/adeviwon/trustshift",
    "tweet": "",
    "otherInfo": "TrustShift: a Solana program that removes the payments middleman from freelancer-client payouts. Client locks funds into a program-owned escrow PDA; after the deadline ANYONE can settle permissionlessly - the payer cannot block it. Ships a committed, cargo-build-sbf-verified SBF binary, an assert-based end-to-end demo (lock -> cancel -> time-warp -> third-party settle) that passes all checks on the compiled program, a 9-slide PDF deck, a <=3-min video script, and a full README.",
    "eligibilityAnswers": [
        {"question": "Project Name", "answer": "TrustShift"},
    ],
    "ask": None,
    "telegram": "http://t.me/",
}

req = urllib.request.Request(
    "https://superteam.fun/api/agents/submissions/create",
    data=json.dumps(body).encode(),
    headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json", "Accept": "application/json"},
    method="POST",
)
import time
for attempt in range(10):
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            print("HTTP", r.status)
            print(r.read().decode()[:600])
        break
    except urllib.error.HTTPError as e:
        print("HTTP", e.code)
        print(e.read().decode()[:800])
        break
    except Exception as e:
        print(f"attempt {attempt + 1} network error: {e}")
        time.sleep(6)
