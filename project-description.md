# TrustShift — Project Description (HackYeah / Superteam Poland Track)

**Project:** TrustShift — trustless P2P payments on Solana
**Track:** Finance Without Intermediaries
**Program ID:** `6FoeU1wFmhh7DrWUvaeGVyFFJNx67VzS78hRjpq6Jpo8` (devnet)

## The relationship we redesigned

Freelancer ↔ client payment. The intermediary today is the payments platform
(bank, PSP, PayPal-style app) that can hold, block, reverse, or freeze the
money and decides who gets served. TrustShift moves the terms of that
transfer into an on-chain program that executes automatically and
identically for every participant, and that no one can change unilaterally.

## What changed once the intermediary is gone

- The client's money is **provably committed** the moment it's locked — the
  freelancer sees the escrow on-chain, not a promise in a dashboard.
- The payout is **automatic and permissionless**: after the deadline, anyone
  (usually the payee) can push the funds. The payer cannot block settlement,
  and no support ticket exists.
- The client keeps a **cancel window before the deadline only** — a fair,
  time-bounded dispute mechanism enforced by code, not by a company's mood.
- Nobody can unilaterally change the terms after the lock.

## Architecture

- **Solana program** (`program/src/lib.rs`, Rust, `solana-program` 2.3,
  no Anchor — plain BPF for auditability):
  - `lock(payer, escrow PDA, payee, deadline, amount)` — creates the
    program-owned escrow PDA via `invoke_signed` and stores payer, payee,
    deadline, amount.
  - `cancel(payer, escrow)` — before the deadline, payer reclaims.
  - `settle(caller, escrow, payee)` — after the deadline, anyone pushes the
    entire escrow balance to the payee; `caller` needs no authority.
- **Demo client** (`app/demo.py`): end-to-end user flow in an in-process
  Solana VM (LiteSVM): connect (keypair) → lock transaction → escrow state
  verified → early settle rejected → cancel → refund verified → time-warp →
  permissionless settle by a third party. Assert-based; exits non-zero on
  any failure.
- **No backend.** All intermediary logic lives in the program.

## Why this is not a mockup

- The compiled SBF binary is committed (`program/target/deploy/trustshift.so`)
  and builds clean with `cargo-build-sbf`.
- The demo executes real transactions against the real compiled program and
  verifies balances and account state after each step.
- The full user flow (wallet → transaction → explorer-visible result) maps
  1:1 to devnet: the same three instructions, the same account layout.

## Target user & design rationale

Freelancers and online sellers invoicing clients they don't fully trust.
See README "Target user" section; deck slide 5.

## Deliverables in this submission

1. Public repo: https://github.com/adeviwon/trustshift (README included)
2. PDF deck (9 slides, under the 10-slide cap): `deck/trustshift-deck.pdf`
3. Video script + production notes for the ≤3-minute walkthrough:
   `video-script.md` (screen-capture of the passing demo run)
