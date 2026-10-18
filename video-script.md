# TrustShift — Video Script (~2m45s)

Narrated screen capture of `python3 app/demo.py` plus the PDF deck. Total runtime target: 3 minutes max.

---

**[0:00–0:20 — Title card / deck slide 1]**
"This is TrustShift — trustless P2P payments on Solana. Every payment app today leans on a middleman that can hold, block, or reverse your money. TrustShift replaces that middleman with an on-chain program."

**[0:20–0:50 — Terminal, start demo, slide 2–3 in voice-over]**
"We picked the freelancer–client relationship. The client locks the payment into a program-owned escrow with a settle deadline. Watch: `lock` — the payer deposits one SOL. The escrow PDA is created by the program itself, and the payer, payee, deadline, and amount are all readable in the account data."

**[0:50–1:20 — Demo continues]**
"Before the deadline, the payer can `cancel` and take the money back — that's the dispute window. But watch what happens if anyone tries to settle early: rejected. The program is the only judge."

**[1:20–2:10 — The key moment]**
"Now the crux. We warp past the deadline, and a completely random third-party keypair — someone with zero authority over this escrow — calls `settle`. No payer signature involved. The program moves the entire escrow balance to the payee. Once the deadline passes, the payer cannot block settlement. Nobody can. That's the moment the intermediary disappears."

**[2:10–2:35 — Slide 7–9, verification]**
"Everything is verified with asserts: lock rejects past deadlines, zero amounts, and duplicate escrows; cancel rejects strangers and late calls; settle rejects early calls and wrong payees. The full demo runs in-process with LiteSVM — `pip install solders litesvm` and go. The compiled program is committed to the repo, so it runs out of the box."

**[2:35–2:50 — Slide 10, close]**
"TrustShift: finance without intermediaries. The repo is public, the demo passes all checks, and the terms live on-chain. Thanks for watching."

---

## Production notes
- Record the terminal at 1440×900 or higher, dark background matching the deck (#0f1120-ish).
- Pause ~2s after each demo section so the logs are readable.
- Export 1080p MP4, under 3 minutes.
