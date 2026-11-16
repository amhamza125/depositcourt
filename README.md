# DepositCourt

An Intelligent Contract on GenLayer (Bradbury testnet) that decides rental
deposit disputes. The deposit sits in escrow inside the contract. When the
tenancy ends, the landlord files deduction claims; an AI jury reads the
lease, the messages between the parties, and the move-in / move-out photo
pairs, and decides each claim line by line. The money then splits exactly
as the verdicts say, and each party withdraws their own share.

## How a case flows

1. **Open and fund.** Either party opens a case; the tenant locks the
   deposit into the contract (escrow, held as `lockw` accounting — the
   contract balance always equals the sum of its locked, bonded, and
   claimable pots).
2. **Evidence.** The landlord files the lease (with clauses), a claim
   schedule (item, amount, lease clause per claim), move-in/move-out
   photo pairs, and invoices. The tenant files counter-messages,
   counter-photos, and their own lease copy. Every photo and invoice is
   bound by SHA-256 at filing time; at assessment the contract fetches
   the bytes and verifies the hash before the jury sees them — a swapped
   or unreachable landlord artifact fails closed and that claim is
   excluded at bucket 0. Tenant counter-photos go through the same
   binding, plus an image-format and size check, before they are judged;
   counter-photos that fail verification are recorded as UNVERIFIED on
   the verdict line and carry no weight. The landlord gets exactly one evidence revision;
   a revision re-opens a fresh 24-hour challenge window for the tenant.
3. **Freeze.** After the challenge window, anyone can freeze the
   evidence. A snapshot hash of every bound artifact is recorded.
4. **Jury.** Each claim is assessed in its own transaction: the jury
   (validator consensus under `strict_eq`) sees the lease clause, the
   claim, both parties' messages, and the claim's two photos, and returns
   one line — category (WEAR_AND_TEAR / TENANT_DAMAGE /
   LANDLORD_RESPONSIBILITY / PRE_EXISTING / INCONCLUSIVE), a deduction
   bucket (0/25/50/75/100), a reason code, and whether the messages
   support the claim. TENANT_DAMAGE must rest on the photos. Assessment
   is permissionless and retryable by design: a failed jury round changes
   no state and can simply be called again.
   **Counter-photo stage.** If a claim line comes back as a photo-based
   TENANT_DAMAGE deduction and the tenant filed counter-photos for that
   line, the line is not stored yet. A second, separate consensus-bound
   jury call judges the tenant's own move-in / move-out pair for that
   line and answers one question — do the counter-photos rebut the
   damage finding? Its verdict (REBUTS_PRE_EXISTING /
   REBUTS_NO_DAMAGE / DOES_NOT_REBUT) is merged into the line by
   deterministic code: a rebuttal rewrites the line to bucket 0 with the
   matching category and reason code; anything else leaves the first
   verdict untouched. The outcome is recorded on the stored line as
   `counter_verdict`, so the basis of every split can be read back from
   chain state. If the counter-photo stage cannot reach a verdict, the
   assessment fails as retryable — a photo-based deduction is never
   stored for a line whose verified counter-photos have not been judged.
5. **Verdict and appeal.** When every claim has a line, finalize computes
   the provisional split deterministically from the recorded lines. The
   losing side may appeal once, posting a bond, for a blind second
   assessment; a failed appeal forfeits the bond to the winner.
6. **Release and withdrawal.** After the appeal window (or the appeal),
   the split is released into per-party claimable pots. Withdrawals use a
   pull pattern: claim, wait for the transfer to land, confirm. A stuck
   withdrawal can be restored by the owner and claimed again. At every
   point, time-based exits protect the deposit if a party disappears.

Parties can also settle bilaterally at any point before the verdict —
the contract records the agreed split and releases it through the same
pull-withdrawal machinery.

## Contract

- **Network:** GenLayer Bradbury (chain 4221)
- **Address:** `0xf396F412910D173CFEA65dC0081401343d330b6C`
- **Explorer:** https://scan.bradbury.genlayer.com/address/0xf396F412910D173CFEA65dC0081401343d330b6C
- **Deploy tx:** `0x7c8cbacbe6e65c70cafd46fdd378ee0f692faea79ef129fba4c0dd220560b2a4`
- **Source:** `DepositCourt.py` in this repo (sha256
  `a1bb02591b4241df7301c255aeda63eb5a9ab73570de298d31e9149038fca0ad`)
- **dApp:** https://depositcourt-ameer-hamza-s-projects2.vercel.app

## What is proven on chain

- **Full settlement lifecycle, exact to the wei:** a 0.05 GEN case
  settled tenant 0.04 / landlord 0.01; the tenant's claim moved the
  contract by exactly −0.04 GEN and the landlord's by exactly −0.01 GEN;
  the case closed with the contract balance back to 0 for it. Stray and
  wrong-amount payments are credited back exactly and recovered in full.
- **19/19 attack attempts blocked live** (wrong party, wrong state,
  early freeze, double revision, claim without a pot, non-owner admin,
  sweep with no excess, and more), each proven by an errored transaction
  plus unchanged read-back state. The exact error codes are pinned by the
  offline suite (`tests/test_pure.py`, stubbed GenVM, conservation
  asserted after every scenario).
- **AI jury verdicts recorded on chain** for the wall-stain scenario
  (lease clause 7, tenant's own message admitting the drawings):
  TENANT_DAMAGE, bucket 100, CLAUSE_BREACH — reached by validator
  majority on the fast-clock twin of this contract
  (tx `0x352289046176bbd442b43bcaddb9a39312f1ca731174d7a48d3dc6cc001e874e`)
  and again on a verbatim replica of the production jury
  (tx `0x225363b2e0bbfa7f11dedab38d03e84fc77e61a6baeec0f2b9b84e7a2cfa7ce6`),
  byte-identical verdict lines.
- **Tenant counter-photo stage, proven live** on the fast-clock twin of
  this exact source (twin `0x220629736311851090bb81E233E0F81b3F929163`,
  identical except the two evidence windows run at 600 seconds): in the
  rebuttal case the tenant's counter move-in photo showed the wall stain
  already present at move-in — stage 1 had found TENANT_DAMAGE from the
  landlord's pair, the counter stage returned REBUTS_PRE_EXISTING, and
  the stored line was rewritten to PRE_EXISTING, bucket 0, deduction
  0 wei; the tenant withdrew the full 0.05 GEN deposit (assessment tx
  `0x2e23b12ab9cd432c2d2d384d8e1fc168c62c8fdeef25d881d7a08ecc6c7dc0d4`).
  In the control case the tenant's own photos confirmed the damage
  appeared during the tenancy — the counter stage returned
  DOES_NOT_REBUT and the deduction stood at the full claimed 0.03 GEN
  (split: tenant 0.02 GEN, landlord 0.0299 GEN, protocol fee 0.0001 GEN;
  assessment tx
  `0xb96c0a8cdd953bf0f89ef61e4deac7051785efe3a5688404cb3b922a7e7079fa`).
  Both cases settled end to end through release and pull withdrawals.
- **Fund conservation** held at every recorded checkpoint on every
  deployment: contract balance == locked + bonds + claimable + pending.

One honest operational note: on Bradbury today, vision jury rounds are
the slow part of the system — a round can fail at the network level and
need retries before a verdict lands. The contract is built for that
(permissionless assessment, an attempts counter, and exits that never
depend on the jury answering), and no deposit can be stranded by jury
silence.
