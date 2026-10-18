//! TrustShift — trustless P2P payments on Solana, zero intermediary.
//!
//! The relationship redesigned: payer → payee value transfer, whose current
//! intermediary is the payments platform (bank, PSP, or app) that can block,
//! reverse, or freeze the money. Here the terms of the transfer live in this
//! on-chain program:
//!
//! * `lock`   — payer deposits lamports into a program-owned PDA escrow,
//!              setting a settle deadline, the payee, and the amount.
//! * `cancel` — BEFORE the deadline, the payer takes the money back.
//! * `settle` — AFTER the deadline, ANYONE (usually the payee) can push the
//!              escrowed lamports to the payee with no signature from the
//!              payer at all. The payer cannot block settlement once the
//!              deadline passes; the program is the only judge.
//!
//! No backend, no multisig service, no arbiter. Devnet-first.

use solana_program::{
    account_info::{next_account_info, AccountInfo},
    clock::Clock,
    entrypoint,
    entrypoint::ProgramResult,
    msg,
    program::invoke_signed,
    program_error::ProgramError,
    pubkey::Pubkey,
    system_instruction,
    sysvar::{rent::Rent, Sysvar},
};

solana_program::declare_id!("6FoeU1wFmhh7DrWUvaeGVyFFJNx67VzS78hRjpq6Jpo8");

/// Instruction data:
///   [0]      = discriminator: 0 = Lock, 1 = Cancel, 2 = Settle
///   [1..9]   = Lock: settle deadline, unix seconds, LE
///   [9..17]  = Lock: amount, lamports, LE
#[derive(Debug, PartialEq)]
enum TrustShiftIx {
    Lock { deadline: u64, amount: u64 },
    Cancel,
    Settle,
}

#[derive(Debug)]
struct InvalidInstruction;
impl From<InvalidInstruction> for ProgramError {
    fn from(_: InvalidInstruction) -> Self {
        ProgramError::InvalidInstructionData
    }
}

impl TrustShiftIx {
    fn unpack(data: &[u8]) -> Result<Self, ProgramError> {
        match data.first() {
            Some(&0u8) => {
                if data.len() < 17 {
                    return Err(InvalidInstruction.into());
                }
                Ok(TrustShiftIx::Lock {
                    deadline: u64::from_le_bytes(data[1..9].try_into().unwrap()),
                    amount: u64::from_le_bytes(data[9..17].try_into().unwrap()),
                })
            }
            Some(&1u8) => Ok(TrustShiftIx::Cancel),
            Some(&2u8) => Ok(TrustShiftIx::Settle),
            _ => Err(InvalidInstruction.into()),
        }
    }
}

/// Serialized escrow state, living in the PDA account this program owns.
pub struct Escrow {
    pub payer: Pubkey,
    pub payee: Pubkey,
    /// Unix seconds after which `settle` becomes permissionless.
    pub deadline: u64,
    pub amount: u64,
    pub bump: u8,
}

pub const ESCROW_LEN: usize = 32 + 32 + 8 + 8 + 1;
pub const ESCROW_SEED: &[u8] = b"trustshift";

#[derive(Debug)]
struct EscrowError(u32);
const ERR_INVALID_DEADLINE: u32 = 0;
const ERR_ESCROW_EXISTS: u32 = 1;
const ERR_INVALID_ESCROW_PDA: u32 = 2;
const ERR_INSUFFICIENT_FUNDS: u32 = 3;
const ERR_WRONG_SIGNER: u32 = 4;
const ERR_DEADLINE_PASSED: u32 = 5;
const ERR_DEADLINE_NOT_REACHED: u32 = 6;
const ERR_WRONG_PAYEE: u32 = 7;
const ERR_OVERFLOW: u32 = 8;
impl From<EscrowError> for ProgramError {
    fn from(e: EscrowError) -> Self {
        ProgramError::Custom(e.0)
    }
}

fn escrow_pda(payer: &Pubkey) -> (Pubkey, u8) {
    Pubkey::find_program_address(&[ESCROW_SEED, payer.as_ref()], &id())
}

fn escrow_pda_with_bump(payer: &Pubkey, bump: u8) -> Pubkey {
    Pubkey::create_program_address(&[ESCROW_SEED, payer.as_ref(), &[bump]], &id())
        .expect("valid PDA")
}

fn unpack_escrow(data: &[u8]) -> Result<Escrow, ProgramError> {
    if data.len() < ESCROW_LEN {
        return Err(ProgramError::AccountDataTooSmall);
    }
    Ok(Escrow {
        payer: Pubkey::new_from_array(data[0..32].try_into().unwrap()),
        payee: Pubkey::new_from_array(data[32..64].try_into().unwrap()),
        deadline: u64::from_le_bytes(data[64..72].try_into().unwrap()),
        amount: u64::from_le_bytes(data[72..80].try_into().unwrap()),
        bump: data[80],
    })
}

fn pack_escrow(e: &Escrow, dst: &mut [u8]) {
    dst[0..32].copy_from_slice(e.payer.as_ref());
    dst[32..64].copy_from_slice(e.payee.as_ref());
    dst[64..72].copy_from_slice(&e.deadline.to_le_bytes());
    dst[72..80].copy_from_slice(&e.amount.to_le_bytes());
    dst[80] = e.bump;
}

entrypoint!(process_instruction);

pub fn process_instruction(
    program_id: &Pubkey,
    accounts: &[AccountInfo],
    instruction_data: &[u8],
) -> ProgramResult {
    match TrustShiftIx::unpack(instruction_data)? {
        TrustShiftIx::Lock { deadline, amount } => lock(program_id, accounts, deadline, amount),
        TrustShiftIx::Cancel => cancel(program_id, accounts),
        TrustShiftIx::Settle => settle(program_id, accounts),
    }
}

fn lock(
    program_id: &Pubkey,
    accounts: &[AccountInfo],
    deadline: u64,
    amount: u64,
) -> ProgramResult {
    msg!("TrustShift: lock amount={} deadline={}", amount, deadline);
    let ais = &mut accounts.iter();
    let payer = next_account_info(ais)?;
    let escrow_ai = next_account_info(ais)?;
    let payee = next_account_info(ais)?;
    let sys = next_account_info(ais)?;
    let now = Clock::get()?.unix_timestamp as u64;

    if !payer.is_signer {
        return Err(ProgramError::MissingRequiredSignature);
    }
    if deadline <= now {
        msg!("deadline in the past");
        return Err(EscrowError(ERR_INVALID_DEADLINE).into());
    }
    if amount == 0 {
        return Err(EscrowError(ERR_INSUFFICIENT_FUNDS).into());
    }
    // New escrows only: PDA must be fresh.
    if escrow_ai.lamports() != 0 || !escrow_ai.data_is_empty() {
        return Err(EscrowError(ERR_ESCROW_EXISTS).into());
    }
    let (expected_pda, bump) = escrow_pda(payer.key);
    if *escrow_ai.key != expected_pda {
        return Err(EscrowError(ERR_INVALID_ESCROW_PDA).into());
    }

    let rent_exempt = Rent::get()?.minimum_balance(ESCROW_LEN);
    let total = rent_exempt.checked_add(amount).ok_or(EscrowError(ERR_OVERFLOW))?;
    if payer.lamports() < total {
        msg!("payer balance {} < needed {}", payer.lamports(), total);
        return Err(EscrowError(ERR_INSUFFICIENT_FUNDS).into());
    }

    invoke_signed(
        &system_instruction::create_account(
            payer.key,
            escrow_ai.key,
            total,
            ESCROW_LEN as u64,
            program_id,
        ),
        &[payer.clone(), escrow_ai.clone(), sys.clone()],
        &[&[ESCROW_SEED, payer.key.as_ref(), &[bump]]],
    )?;

    pack_escrow(
        &Escrow {
            payer: *payer.key,
            payee: *payee.key,
            deadline,
            amount,
            bump,
        },
        &mut escrow_ai.try_borrow_mut_data()?[..ESCROW_LEN],
    );
    msg!("TrustShift: locked, payee={}", payee.key);
    Ok(())
}

fn cancel(program_id: &Pubkey, accounts: &[AccountInfo]) -> ProgramResult {
    msg!("TrustShift: cancel");
    let ais = &mut accounts.iter();
    let payer = next_account_info(ais)?;
    let escrow_ai = next_account_info(ais)?;
    let sys = next_account_info(ais)?;
    let now = Clock::get()?.unix_timestamp as u64;

    if !payer.is_signer {
        return Err(ProgramError::MissingRequiredSignature);
    }
    let e = unpack_escrow(&escrow_ai.try_borrow_data()?)?;
    if e.payer != *payer.key {
        return Err(EscrowError(ERR_WRONG_SIGNER).into());
    }
    if *escrow_ai.key != escrow_pda_with_bump(payer.key, e.bump)
        || escrow_ai.owner != program_id
    {
        return Err(EscrowError(ERR_INVALID_ESCROW_PDA).into());
    }
    if now >= e.deadline {
        msg!("deadline passed; payer can no longer cancel");
        return Err(EscrowError(ERR_DEADLINE_PASSED).into());
    }

    // Close pattern: an owned program may move an account's lamports by
    // direct mutation and zero its data (garbage-collected at epoch end).
    // A raw system transfer FROM an account that still carries data is
    // rejected ("from must not carry data"), so we zero the data first,
    // then hand over the entire balance — amount + rent — to the recipient.
    let lamports = **escrow_ai.try_borrow_lamports()?;
    {
        let mut data = escrow_ai.try_borrow_mut_data()?;
        for b in data.iter_mut() {
            *b = 0;
        }
    }
    **escrow_ai.lamports.borrow_mut() = 0;
    **payer.lamports.borrow_mut() = payer
        .lamports()
        .checked_add(lamports)
        .ok_or(EscrowError(ERR_OVERFLOW))?;
    msg!("TrustShift: cancelled, {} lamports returned to payer", lamports);
    Ok(())
}

fn settle(program_id: &Pubkey, accounts: &[AccountInfo]) -> ProgramResult {
    let ais = &mut accounts.iter();
    let _caller = next_account_info(ais)?; // anyone; usually the payee
    let escrow_ai = next_account_info(ais)?;
    let payee = next_account_info(ais)?;
    let sys = next_account_info(ais)?;
    let now = Clock::get()?.unix_timestamp as u64;

    let e = unpack_escrow(&escrow_ai.try_borrow_data()?)?;
    if *escrow_ai.key != escrow_pda_with_bump(&e.payer, e.bump)
        || escrow_ai.owner != program_id
    {
        return Err(EscrowError(ERR_INVALID_ESCROW_PDA).into());
    }
    if now < e.deadline {
        msg!("not yet settleable; deadline {} > now {}", e.deadline, now);
        return Err(EscrowError(ERR_DEADLINE_NOT_REACHED).into());
    }
    if *payee.key != e.payee {
        return Err(EscrowError(ERR_WRONG_PAYEE).into());
    }
    // Permissionless: `caller` needs NO authority over the escrow — the
    // program is the sole judge of settlement.
    // Close pattern (same as `cancel`): zero data, then move the entire
    // balance to the payee by direct lamports mutation.
    let lamports = **escrow_ai.try_borrow_lamports()?;
    {
        let mut data = escrow_ai.try_borrow_mut_data()?;
        for b in data.iter_mut() {
            *b = 0;
        }
    }
    **escrow_ai.lamports.borrow_mut() = 0;
    **payee.lamports.borrow_mut() = payee
        .lamports()
        .checked_add(lamports)
        .ok_or(EscrowError(ERR_OVERFLOW))?;
    msg!("TrustShift: settled {} lamports to payee, permissionlessly", lamports);
    Ok(())
}
