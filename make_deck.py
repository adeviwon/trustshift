#!/usr/bin/env python3
"""Build the TrustShift pitch deck (max 10 slides) as PDF via reportlab."""
import os
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "deck", "trustshift-deck.pdf")
os.makedirs(os.path.dirname(OUT), exist_ok=True)
W, H = landscape(A4)

c = canvas.Canvas(OUT, pagesize=(W, H))

def slide(title, bullets, footer=None, big=None):
    c.setFillColorRGB(0.06, 0.07, 0.12)
    c.rect(0, 0, W, H, fill=1, stroke=0)
    # accent bar
    c.setFillColorRGB(0.36, 0.80, 0.62)
    c.rect(0, H - 14, W, 14, fill=1, stroke=0)
    c.setFillColorRGB(1, 1, 1)
    c.setFont("Helvetica-Bold", 34)
    c.drawString(25 * mm, H - 40 * mm, title)
    y = H - 60 * mm
    if big:
        c.setFont("Helvetica-Bold", 64)
        c.setFillColorRGB(0.36, 0.80, 0.62)
        c.drawCentredString(W / 2, H - 95 * mm, big)
        y = H - 115 * mm
    c.setFont("Helvetica", 19)
    c.setFillColorRGB(0.92, 0.93, 0.96)
    for b in bullets:
        c.drawString(30 * mm, y, b)
        y -= 13 * mm
    if footer:
        c.setFont("Helvetica", 12)
        c.setFillColorRGB(0.55, 0.58, 0.63)
        c.drawString(25 * mm, 12 * mm, footer)
    c.showPage()

slide(
    "TrustShift",
    ["Trustless P2P payments on Solana — the middleman is the program."],
    "Superteam Poland Track — HackYeah 2026",
    big="Finance without intermediaries",
)
slide(
    "The problem: the middleman owns your money",
    [
        "• Every P2P payment leans on a bank, PSP, or app that can hold, block,",
        "  reverse, or freeze funds — and decides who gets served.",
        "• Freelancers invoice strangers and wait, exposed to platform freezes",
        "  and unilateral reversals.",
        "• The trust requirement is the product. Remove it, and payments become",
        "  as programmable — and as neutral — as math.",
    ],
)
slide(
    "What TrustShift is",
    [
        "• A Solana program (devnet-first) holding the terms of a P2P transfer.",
        "• lock    — payer deposits into a program-owned escrow PDA with a deadline.",
        "• cancel  — BEFORE the deadline, the payer reclaims.",
        "• settle  — AFTER the deadline, ANYONE pushes the funds to the payee.",
        "• No backend. No multisig service. No arbiter. ~300 lines of Rust.",
    ],
)
slide(
    "The key property",
    [
        "• Once the deadline passes, the payer cannot block settlement.",
        "• Nobody can. The program is the only judge.",
        "• A third party with zero authority over the escrow can force",
        "  settlement permissionlessly — proven in the demo, where a random",
        "  keypair settles and the payer's key is never used again.",
    ],
)
slide(
    "Target user & rationale",
    [
        "• Freelancers and online sellers invoicing clients they don't fully trust.",
        "• The intermediary today: the invoicing/payment platform that can",
        "  freeze the payout or side with either party arbitrarily.",
        "• With TrustShift: the client locks funds up front — provably committed",
        "  on-chain and payable at the agreed deadline.",
        "• The client keeps a cancel window for disputes — BEFORE the deadline only.",
    ],
)
slide(
    "The user flow (devnet)",
    [
        "• Connect wallet → lock transaction → escrow PDA visible in explorer →",
        "  settle transaction → payout visible in explorer.",
        "• The escrow account exposes payer, payee, deadline, and amount",
        "  in plain account data — auditable by anyone.",
        "• After settle, the emptied escrow and the payee's new balance",
        "  are both explorer-visible.",
    ],
)
slide(
    "Why it's trustless for real",
    [
        "• The deadline check, the settle authorization, and the fund movement",
        "  all execute inside the on-chain program — not a backend.",
        "• lock rejects past deadlines, zero amounts, duplicate escrows.",
        "• cancel rejects strangers and late calls.",
        "• settle rejects early calls, wrong payees, and tampered accounts.",
    ],
)
slide(
    "Demo",
    [
        "• app/demo.py runs the full flow in-process (LiteSVM, no network):",
        "  lock → state verify → early-settle rejected → cancel → refund →",
        "  time-warp → permissionless third-party settle.",
        "• Assert-based: exits non-zero on any failure. ALL CHECKS PASSED.",
    ],
)
slide(
    "Real-world potential",
    [
        "• Escrow-as-a-primitive for freelance, marketplace, and B2B settlement.",
        "• Composable: deadline + permissionless settle is the trust kernel other",
        "  flows (milestones, conditional refunds, revenue shares) can extend.",
        "• Zero marginal infrastructure: no servers to run or trust.",
    ],
)
slide(
    "Links",
    [
        "• Public repo: github.com/adeviwon/trustshift",
        "• Program: 6FoeU1wFmhh7DrWUvaeGVyFFJNx67VzS78hRjpq6Jpo8 (devnet)",
        "• Run the demo: pip install solders litesvm && python3 app/demo.py",
    ],
)
c.save()
print("wrote", OUT)
