# TrustShift — trustless P2P payments on Solana, zero intermediary

**Bounty:** Finance Without Intermediaries — Superteam Poland Track at HackYeah
**Program ID:** `6FoeU1wFmhh7DrWUvaeGVyFFJNx67VzS78hRjpq6Jpo8`
**Network:** Solana devnet-first (tested in-process on LiteSVM)

## The problem

Every digital payment today leans on a trusted middleman — a bank, a payment
provider, or an app — that can hold, block, reverse, or freeze the money.
TrustShift removes that intermediary for the most common P2P relationship:
*payer promises to pay payee, possibly later, possibly conditionally*.

## The design

The terms of the transfer live entirely in an on-chain program. There is no
backend, no multisig service, no arbiter. Three instructions:

| Instruction | Who | When | Effect |
|---|---|---|---|
| `lock` | payer | any time | Deposits lamports into a program-owned escrow PDA with a **settle deadline** and payee |
| `cancel` | payer | **before** deadline | Refunds the payer — the "I changed my mind" window |
| `settle` | **anyone** | **after** deadline | Pushes the full escrow balance to the payee — **no payer signature needed** |

The key property: once the deadline passes, the payer cannot block settlement.
Nobody can. The program is the only judge. A third party with no authority
over the escrow can force settlement permissionlessly — this is what removes
the intermediary that would otherwise "release" or "hold" funds.

**Target user:** freelancers and online sellers who invoice clients they don't
fully trust. The intermediary today is the invoicing/payment platform
(PayPal-style) that can freeze the payout or side with either party
arbitrarily. With TrustShift the client locks the funds up front; the
freelancer knows the money is provably committed on-chain and becomes
payable at the agreed deadline, and the client keeps a cancel window for
disputes *before* the deadline only.

## Repository layout

```
program/        Solana program (Rust, solana-program 2.3, no Anchor)
  src/lib.rs    the whole program (~300 lines)
  target/deploy/trustshift.so   compiled SBF binary
app/demo.py     end-to-end demo client (solders + LiteSVM, in-process VM)
tests/          (the demo IS the test — see below)
```

## Running the demo

Prerequisites: Python 3 with `solders` and `litesvm` (`pip install solders litesvm`).
The compiled `.so` is committed under `program/target/deploy/`.

```bash
python3 app/demo.py
```

Expected output (all checks pass):

```
== 1. lock: payer escrows 1 SOL, payable to payee after 1 day
  [lock] ok — CU used: 12976
  escrow state verified: payer/payee/deadline/amount/rent all correct
== 2. early settle attempt (deadline not reached) -> must fail
  [early-settle] correctly rejected
== 3. cancel: payer reclaims BEFORE the deadline
  [cancel] ok — CU used: 3428
  escrow emptied, payer refund verified
== 4. warp past the deadline, then THIRD PARTY settles — no payer key involved
  [settle] ok — CU used: 3609
  payee received exactly 1001454640 lamports (amount + rent); escrow emptied; payer never signed
ALL CHECKS PASSED
```

The settle step is the crux: only a random third-party keypair signs the
transaction, yet the payee receives the full escrow. The payer's key is never
involved after the deadline.

## Full user flow (devnet)

`connect wallet → lock transaction → explorer-visible escrow account →
settle transaction → explorer-visible payout`

1. Connect a wallet (any devnet wallet).
2. `lock` — creates the escrow PDA (program-owned, ~81 bytes) and transfers
   the agreed amount plus rent into it. The escrow account is visible on
   [Solana Explorer](https://explorer.solana.com/?cluster=devnet) with its
   payer, payee, deadline, and amount readable in the account data.
3. Wait past the deadline (or `cancel` before it to reclaim).
4. `settle` — anyone (usually the payee) sends the settle instruction; the
   program moves the entire escrow balance to the payee. Both the emptied
   escrow and the payee's balance change are visible in the explorer.

## Rebuilding the program

With Solana SBF toolchain (e.g. Agave v1.57 / `cargo-build-sbf`):

```bash
cd program
cargo-build-sbf
cp target/sbpfv3-solana-solana/release/trustshift.so target/deploy/
```

## Verification

- `lock` rejects: past deadlines, zero amounts, duplicate escrows
  (one PDA per payer), non-signing payers.
- `cancel` rejects: anyone but the payer, calls after the deadline.
- `settle` rejects: calls before the deadline, wrong payee, tampered or
  foreign escrow accounts (PDA + owner checks).
- All of the above are exercised in `app/demo.py` (assert-based, exits
  non-zero on any failure).
- Builds clean with `cargo-build-sbf` (5 warnings: unused `sys` accounts
  retained for CPI clarity; overflow checks on, LTO fat).

## Why the intermediary is really gone

The logic that replaces the intermediary lives in the on-chain program, not
in any backend: the deadline check, the permissionless settle authorization,
and the fund movement all execute inside `trustshift.so` on Solana's runtime.
No server can reverse a settlement, and no server is needed to trigger one.
