#!/usr/bin/env python3
"""TrustShift demo client — Python (solders + LiteSVM).

Runs the full user flow against the compiled TrustShift program in an
in-process Solana VM (no network, no validator):

  1. lock     — payer deposits into the program-owned escrow PDA.
                The PROGRAM creates the PDA via invoke_signed (the system
                program demands a signature for the new account that a PDA
                can only give through the program's seeds — pre-creating
                the account client-side fails with "must sign").
  2. settle   — before the deadline, settlement is rejected.
  3. cancel   — payer reclaims funds BEFORE the deadline. One escrow PDA
                exists per payer, so each demo step uses a fresh payer.
  4. settle   — AFTER the deadline, a THIRD PARTY (no payer signature
                authority, just a random keypair paying the fee) pushes
                the escrowed lamports to the payee.

Note on balances: the rent-exempt minimum for the 81-byte escrow is
1,454,640 lamports, so the payee receives amount + rent.

Run:  python3 app/demo.py
"""
import os
import struct
import sys

from solders.instruction import AccountMeta, Instruction
from solders.keypair import Keypair
from solders.litesvm import LiteSVM
from solders.pubkey import Pubkey
from solders.system_program import ID as SYSID
from solders.transaction import Transaction

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PROGRAM_ID = Pubkey.from_string("6FoeU1wFmhh7DrWUvaeGVyFFJNx67VzS78hRjpq6Jpo8")
SO_PATH = os.path.join(ROOT, "program", "target", "deploy", "trustshift.so")
ESCROW_SEED = b"trustshift"
LAMPORTS = 1_000_000_000  # 1 SOL worth of lamports
RENT = (128 + 81) * 3480 * 2  # rent-exempt minimum for the 81-byte escrow
DAY = 86_400


def find_escrow_pda(payer: Pubkey) -> tuple[Pubkey, int]:
    return Pubkey.find_program_address([ESCROW_SEED, bytes(payer)], PROGRAM_ID)


def ix_lock(payer: Pubkey, escrow: Pubkey, payee: Pubkey, deadline: int, amount: int) -> Instruction:
    return Instruction(
        program_id=PROGRAM_ID,
        accounts=[
            AccountMeta(payer, is_signer=True, is_writable=True),
            AccountMeta(escrow, is_signer=False, is_writable=True),
            AccountMeta(payee, is_signer=False, is_writable=False),
            AccountMeta(SYSID, is_signer=False, is_writable=False),
        ],
        data=bytes([0]) + struct.pack("<QQ", deadline, amount),
    )


def ix_cancel(payer: Pubkey, escrow: Pubkey) -> Instruction:
    return Instruction(
        program_id=PROGRAM_ID,
        accounts=[
            AccountMeta(payer, is_signer=True, is_writable=True),
            AccountMeta(escrow, is_signer=False, is_writable=True),
            AccountMeta(SYSID, is_signer=False, is_writable=False),
        ],
        data=bytes([1]),
    )


def ix_settle(caller: Pubkey, escrow: Pubkey, payee: Pubkey) -> Instruction:
    return Instruction(
        program_id=PROGRAM_ID,
        accounts=[
            AccountMeta(caller, is_signer=True, is_writable=True),  # fee payer only
            AccountMeta(escrow, is_signer=False, is_writable=True),
            AccountMeta(payee, is_signer=False, is_writable=True),
            AccountMeta(SYSID, is_signer=False, is_writable=False),
        ],
        data=bytes([2]),
    )


def run(svm: LiteSVM, tx: Transaction, label: str, expect_ok: bool = True) -> bool:
    res = svm.send_transaction(tx)
    # Success returns TransactionMetadata (compute_units_consumed attribute);
    # failure returns FailedTransactionMetadata (err() method, meta() method).
    def _cu(v) -> int:
        try:
            return int(v)
        except TypeError:
            return int(v())

    if hasattr(res, "err"):
        ok = res.err() is None
        meta = res.meta()
        cu = _cu(meta.compute_units_consumed)
    else:
        ok = True
        meta = res
        cu = _cu(res.compute_units_consumed)
    if ok == expect_ok:
        print(f"  [{label}] {'ok — CU used: %d' % cu if ok else 'correctly rejected'}")
        for line in meta.logs():
            if "TrustShift" in line or "trustshift" in line:
                print(f"      log: {line}")
    else:
        print(f"  [{label}] UNEXPECTED (ok={ok}) err={getattr(res, 'err', lambda: 'n/a')()}")
        for line in meta.logs():
            print(f"      log: {line}")
    return ok == expect_ok


def main() -> int:
    svm = LiteSVM()
    svm.add_program_from_file(PROGRAM_ID, SO_PATH)
    print(f"program deployed in-VM at {PROGRAM_ID}")

    payee = Keypair()
    svm.airdrop(payee.pubkey(), 1_000_000)  # floor so balance reads never return None
    third_party = Keypair()  # settles without any payer authority
    svm.airdrop(third_party.pubkey(), LAMPORTS)
    print(f"payee  = {payee.pubkey()}")
    print(f"third  = {third_party.pubkey()}  (will run settle)")

    now = svm.get_clock().unix_timestamp

    def fresh_payer() -> tuple[Keypair, Pubkey]:
        kp = Keypair()
        svm.airdrop(kp.pubkey(), 10 * LAMPORTS)
        escrow, bump = find_escrow_pda(kp.pubkey())
        print(f"payer  = {kp.pubkey()}")
        print(f"escrow PDA = {escrow} (bump {bump})")
        return kp, escrow

    # ---- 1. lock -----------------------------------------------------------
    print("\n== 1. lock: payer escrows 1 SOL, payable to payee after 1 day")
    payer, escrow = fresh_payer()
    tx = Transaction.new_with_payer(
        [ix_lock(payer.pubkey(), escrow, payee.pubkey(), now + DAY, LAMPORTS)],
        payer.pubkey(),
    )
    tx.sign([payer], svm.latest_blockhash())
    assert run(svm, tx, "lock")
    acct = svm.get_account(escrow)
    assert acct.lamports == LAMPORTS + RENT, acct.lamports
    assert bytes(acct.data[0:32]) == bytes(payer.pubkey())
    assert bytes(acct.data[32:64]) == bytes(payee.pubkey())
    dl, amt = struct.unpack("<QQ", acct.data[64:80])
    assert dl == now + DAY and amt == LAMPORTS
    print("  escrow state verified: payer/payee/deadline/amount/rent all correct")

    # ---- 2. early settle must fail ------------------------------------------
    print("\n== 2. early settle attempt (deadline not reached) -> must fail")
    tx = Transaction.new_with_payer(
        [ix_settle(payee.pubkey(), escrow, payee.pubkey())], payee.pubkey()
    )
    tx.sign([payee], svm.latest_blockhash())
    assert run(svm, tx, "early-settle", expect_ok=False)

    # ---- 3. cancel path (fresh payer => fresh PDA) ---------------------------
    print("\n== 3. cancel: payer reclaims BEFORE the deadline")
    payer2, escrow2 = fresh_payer()
    tx = Transaction.new_with_payer(
        [ix_lock(payer2.pubkey(), escrow2, payee.pubkey(), now + 2, LAMPORTS)],
        payer2.pubkey(),
    )
    tx.sign([payer2], svm.latest_blockhash())
    assert run(svm, tx, "lock#2")
    bal_before = svm.get_balance(payer2.pubkey())
    tx = Transaction.new_with_payer([ix_cancel(payer2.pubkey(), escrow2)], payer2.pubkey())
    tx.sign([payer2], svm.latest_blockhash())
    assert run(svm, tx, "cancel")
    assert (svm.get_balance(escrow2) or 0) == 0, "escrow should be empty after cancel"
    assert svm.get_balance(payer2.pubkey()) > bal_before - 20_000, "payer refunded"
    print("  escrow emptied, payer refund verified")

    # ---- 4. settle path: permissionless --------------------------------------
    print("\n== 4. warp past the deadline, then THIRD PARTY settles — no payer key involved")
    payer3, escrow3 = fresh_payer()
    tx = Transaction.new_with_payer(
        [ix_lock(payer3.pubkey(), escrow3, payee.pubkey(), now + 2, LAMPORTS)],
        payer3.pubkey(),
    )
    tx.sign([payer3], svm.latest_blockhash())
    assert run(svm, tx, "lock#3")
    clock = svm.get_clock()
    clock.unix_timestamp = now + 10
    svm.set_clock(clock)
    payee_before = svm.get_balance(payee.pubkey())
    tx = Transaction.new_with_payer(
        [ix_settle(third_party.pubkey(), escrow3, payee.pubkey())], third_party.pubkey()
    )
    tx.sign([third_party], svm.latest_blockhash())  # ONLY the third party signs
    assert run(svm, tx, "settle")
    got = svm.get_balance(payee.pubkey()) - payee_before
    assert got == LAMPORTS + RENT, f"payee received {got}"
    assert (svm.get_balance(escrow3) or 0) == 0
    print(f"  payee received exactly {got} lamports (amount + rent); escrow emptied; payer never signed")

    print("\nALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
