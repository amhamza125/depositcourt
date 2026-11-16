# DepositCourt — Build Record (Phase 1)

Started: 2026-11-12 (PKT). Authority: SPEC.md v2 (frozen). Chain: Bradbury 4221.
Decided defaults (Atlas): FEE_WEI = 10^14; APPEAL_BOND_WEI = 10^14;
BOND_MATERIALITY_FLOOR_WEI = 10^12; CLAIM_LIMIT = 8; two-step ownership.

## Probe outcome (from probes/ run artifacts, 2026-11-12; PROBE_RESULTS.md not yet written)
- ProbeA URL-form (URLs in prompt): jury BLIND — verdict colours "unknown/unknown".
- ProbeA bytes-form2 (fetch bytes in jury, `exec_prompt(..., response_format="json",
  images=[b_in, b_out])` under strict_eq): CORRECT (red/blue), MAJORITY_AGREE.
- ProbeA bytes-form3 (3 images): FINISHED_WITH_ERROR — 2-image cap respected in design.
- ProbeB (full assess pipeline, same transport form as bytes2): FINISHED_WITH_ERROR
  with near-empty nd_outs — internal to ProbeB; DepositCourt mirrors the proven
  bytes2 form and treats jury errors as JURY_FAILURE (retryable, no state change).
- => Assessment transport: fetch bytes inside the jury fn, hash-verify, attach
  exactly 2 images. Tenant counter-photos are hash-verified and described in the
  prompt text (never attached — 2-image cap).

## Case-record key map (storage codes; verdict/client JSON keeps spec names)
Record: L landlord, T tenant, cr creator, fu funder, fpath funding_path,
pref property_ref, dep deposit_wei (str), tstart/tend tenancy bounds (str unix),
lang lease_language, st status, cta created_at, fat funded_at, eoa
evidence_opened_at, cdl challenge_deadline, ffa first_frozen_at, snap
snapshot_hash, adl appeal_deadline, afa appeal_filed_at, acnt appeal_count,
app appellant, ares appeal_resolved, bst bond_state, att/aat assessment
attempts (normal/appeal), icr inconclusive re-open count, fee fee_wei charged,
ev evidence {L,T}x{lease,photos,messages}, cl claims, inv invoices, cvs/avv
verdict maps (cvs provisional, avs appeal), vd/avd verdict records, ofr
settlement offer, ent entitlements {T,L,owner}, ecl entitlement-claimed flags.
Claim: camt claimed_amount_wei (str), clid clause_id. Invoice: ref item_ref,
rurl receipt_url, rsha receipt_sha256. Photo slot: iu/ou URL lists, ih/oh hash
lists, sh slot hash. Any slot: ver version, rev primary revisions, ag
landlord-stamp the tenant slot was filed against. Pending: amt, iat issued_at.
Landlord record: ncd cases_decided, duw deductions_upheld_wei, naf
appeals_filed_against, nau appeals_upheld_against.
Aggregates: lockw (escrows), bondw (appeal bonds), tcw (claimable), tpw
(pending). Conservation: balance == lockw + bondw + tcw + tpw + genuine excess.

## Interpretation / deviation log
- D-1 SIZE: source had to fit the proven Bradbury deploy wall (~39,000 B;
  39,000 deployed OK for GrantFlow, 39,100 failed). Final: 38,872 B. To fit:
  (a) storage keys shortened to codes (map above); (b) nine §11 convenience
  views dropped — get_escrow, get_funder, get_challenge_deadline,
  get_appeal_bond, get_fee, get_clauses, get_invoices, get_claim_schedule,
  get_evidence_snapshot — every value remains available via get_case;
  get_appeal carries bond data; (c) get_cases_for_party view + party index
  dropped — case ids are sequential from 0, enumerable via get_case;
  (d) submit_counter_evidence dropped — the tenant files counter-evidence
  through submit_lease / submit_photos / submit_messages against their own
  slots; the supersede/stamp logic is identical (spec §11 listed it as a
  convenience alias); (e) per-case activity log + get_activity_history
  dropped — chain transactions are the audit trail (restore/confirm state is
  fully observable via get_pending / get_claimable); (f) protocol history
  ring buffer dropped; (g) datamarking simplified to §BEGIN_EVIDENCE§ fences
  (the UNTRUSTED labelling + neutralisation clause remain in the prompt, and
  the § character is still stripped from all party text by _clean).
- D-2 Payable-call rejections (wrong amount/sender/status/paused, stale
  tenancy, wrong/late/non-loser appeal bond) credit claimable per SPEC §5.4
  and RETURN a string starting with the exact error code instead of raising —
  a raise would strand the attached value with no record. Non-payable gates
  raise UserError with the exact code.
- D-3 Codes invented where the spec named none: LEASE_REQUIRED (schedule
  before lease), BAD_FUNDING_PATH (unknown funding_path string).
- D-4 Claim↔photo-pair alignment is by index (claim_i judged on pair_i), per
  SPEC §6.3's pair_id scheme.
- D-5 Excluded-artifact lines are recorded as category
  LANDLORD_RESPONSIBILITY / reason UNPROVEN_CLAIM / bucket 0 with an
  excluded_reason field (SPEC §6.3 requires the deterministic bucket-0 line;
  it names no category for it).
- D-6 Messages hash binds the stored excerpt (head+tail 2,800 chars) — the
  exact text the jury judges is the hashed text (self-consistent binding).
- D-7 INCONCLUSIVE re-open keeps the original evidence_opened_at, so the
  14-day abandoned-evidence clock runs from the first opening (favours the
  tenant's timeout exit; SPEC §6.7 does not reset it).
- D-8 Rejected appeal bonds (1e14 wei) fall below MIN_REFUNDABLE_WEI
  (2e15 wei) and become protocol excess per SPEC §5.4's own floor rule;
  a correct bond is never rejected.

## Adversarial self-audit (post pure-tests)
- A-1 confirm_withdrawal scans pendings keys for the ONLY_RECIPIENT check;
  the recipient path never scans. Accepted (cosmetic error-code risk only).
- A-2 claim_payout emits the transfer before zeroing the pot — identical
  order to GrantFlow v3.4 (shipped, payout-proven); emit_transfer is an
  async EVM message in GenVM, no synchronous re-entry. Accepted.
- A-3 Claim amounts are not capped at the deposit individually; overshoot is
  caught deterministically at finalize (MALFORMED_VERDICT, no state change)
  and per-invoice amounts ARE capped at the deposit. Accepted per SPEC §5.2/§6.6.
- A-4 _aone uses nested closures (fail/jury) — same pattern as GrantFlow's
  proven assess. Accepted.
- A-5 Pause gates exactly the SPEC §9 set (create, fund, evidence submits,
  assess). Freeze/finalize/release/expire/cancel/claim/confirm/appeal stay
  open so no exit is ever blocked by the pause. Verified in tests.

## Offline pure tests (tests/test_pure.py, stubbed GenVM)
22/22 test groups PASS (2026-11-12). Coverage: create validation (bounds,
stale tenancy, bad path/address), fund paths (wrong sender/amount credited,
dust-to-excess, tenant fund_dispute, double-fund), cancel (creator gate,
funder refund), evidence gates (lease-required, only-party/landlord, claim
limit, challenge window), landlord revision cap + tenant supersede/re-file,
photo validation (scheme/hash/shape), split math + fee + landlord record,
floor division, malformed verdicts (bad bucket, TENANT_DAMAGE w/o clause,
wear bucket>0, incomplete finalize), excluded artifact (hash mismatch ->
bucket 0), INCONCLUSIVE re-open then EXPIRED, total>escrow malformed,
appeal (non-loser rejected, wrong bond, window closed, upheld bond-to-other,
material-change path), pull payout cycle (pending, only-recipient confirm,
close-out to CLOSED), restore_pending (too-early, only-owner, re-credit),
all five expire paths + appeal expiry (no fee, bond refunded), settlement
(bad split, own-offer, outsider, accept, zero fee), pause + sweep +
two-step ownership, views. Fund conservation asserted after every scenario.

## Deployment (2026-11-12)
- Contract: **0x420447DD4a4d6561b6e579C61a18262C5d891254** (Bradbury 4221)
- Deploy tx: **0x44bd7d4ded9ab02fe6d86384de522a3432a7025c4e32ac645f8006afbd579653**
  (FINALIZED, MAJORITY_AGREE, FINISHED_WITH_RETURN; from test wallet A
  0xD2aF69BB67d446526661A80a280820599c601ed3, 0.2 GEN feeValue cap)
- Source: DepositCourt.py, 38,872 bytes, sha256
  6d4e262d1a1019b9d5a3dd66b281b9a1fc88435853ce8df157e2f54fa6d0fd7b
- Deployment record: ~/workspace/gmv-bradbury/v2/deployment-depositcourt-v1.json
- Explorer: https://explorer-bradbury.genlayer.com/address/0x420447DD4a4d6561b6e579C61a18262C5d891254

## On-chain results (tests/live-suite.mjs + live-suite2b.mjs, 2026-11-12)
Full log/results: tests/live-results.json; receipts in tests/receipts/.
- **23/23 lifecycle steps PASS, 19/19 attacks BLOCKED, conservation exact at
  every checkpoint** (final: balance == lockw == 100000000000000000 wei =
  the two staged escrows; bondw/tcw/tpw all 0; ncase 4; unpaused).
- Case 0 — SETTLEMENT LIFECYCLE (complete): create (run-1 tx
  0x682d9c738a96803d662975cd430ec74f7fb852391324adf6ec02b99d7a045d02) ->
  lock_deposit 0.05 GEN -> lease -> schedule -> propose (T 0.04 / L 0.01) ->
  accept -> SETTLED with claimable tenant 40000000000000000, landlord
  10000000000000000 exactly -> tenant claim_payout: contract balance delta
  **-40000000000000000 exact**, tenant native delta +39862535529998706
  (0.04 GEN minus the tenant's own claim-tx fee) -> confirm -> landlord
  claim+confirm (contract delta -10000000000000000 exact) -> case **CLOSED**,
  contract balance back to 0.
- Case 1 — EVIDENCE STAGED for the jury arc: created + funded by the TENANT
  via fund_dispute (0.05 GEN), landlord lease + 2-claim schedule + photo
  pairs (hosted probe images, sha256-bound), tenant counter-messages +
  counter-photos, landlord lease revision (ver 2, rev 1) SUPERSEDING the
  tenant's messages (stamp mismatch read back on-chain), tenant re-filed
  (live again). Freeze inside the window BLOCKED (CHALLENGE_OPEN); second
  landlord revision BLOCKED (EVIDENCE_LOCKED). State: EVIDENCE,
  challenge_deadline unix 1794572544.
- Case 2 — STRAY-CREDIT RECOVERY: wrong-amount lock (3e15 wei) returned
  ESCROW_MISMATCH path, credited claimable exactly, claimed back with
  contract delta -3000000000000000 exact; outsider C's full-deposit
  lock_deposit attempt credited C exactly 5e16 and C recovered it exactly.
  Case left CREATED/unfunded.
- Case 3 — EVIDENCE STAGED (second jury shot): funded, lease, 1-claim
  schedule, photo pair, plus a standing settlement offer (T 0.025 / L 0.025)
  left unaccepted. State: EVIDENCE, challenge_deadline unix 1794574131.
- Attacks blocked live (19): freeze-in-window (CHALLENGE_OPEN), revision cap
  (EVIDENCE_LOCKED), schedule-before-lease (LEASE_REQUIRED), schedule by
  tenant (ONLY_LANDLORD), outsider lease (ONLY_PARTY), assess before freeze
  (NOT_FROZEN), release without verdict (BAD_STATUS), claim without pot
  (NO_CLAIM), confirm without pending (NO_PENDING), restore by non-owner
  (ONLY_OWNER), sweep by non-owner (ONLY_OWNER), sweep with no excess
  (NO_EXCESS), cancel by non-creator (ONLY_CREATOR), expire fresh case
  (NOT_EXPIRED), bad settlement split (BAD_SPLIT), accept own offer
  (BAD_STATUS), accept by outsider (ONLY_PARTY), pause by non-owner
  (ONLY_OWNER), create while paused (PROTOCOL_PAUSED). On-chain receipts do
  not embed the error-code text; each block is proven by FINISHED_WITH_ERROR
  + read-back state unchanged, and the exact code is pinned by the offline
  suite against identical logic (each attacked state admits exactly one
  raise path).
- Driver incidents (not contract faults): run 1 crashed on a BigInt
  JSON.stringify in the driver AFTER case 0's create landed (resumed
  cleanly); run 2 crashed on a transient Bradbury RPC TLS failure during
  receipt polling (continued as live-suite2b.mjs with retrying waits; the
  in-flight submit_photos had in fact landed). No redeploy was ever needed.

## Jury-arc follow-up (the only unproven-on-chain segment — by the clock, not by failure)
The spec's real 24h windows make freeze/assess/finalize/release impossible
before 2026-11-13 ~17:22 PKT. The full arc (assess -> finalize -> provisional
-> appeal -> resolve -> release -> claim) is proven offline in the stubbed
suite (22/22 groups) and the payout machinery it ends in is proven live
above. To finish it live, from 2026-11-13 17:22 PKT (case 1) / 17:48 PKT
(case 3) onward, any wallet may call, in order:
  freeze_evidence(1) -> assess_claim(1, "claim_1") -> assess_claim(1,
  "claim_2") -> finalize_assessment(1) -> [24h appeal window] ->
  release_split(1) -> claim_payout(1)/confirm_withdrawal(1) per party.
Case 1 evidence is the ProbeB scenario (landlord pair img-b-in/img-b-out,
sha b551700f.../1d965288...; claim_1 wall stains 2e16 wei, claim_2 blinds
1e16 wei, clause_7). Case 3 is the single-claim backup (garden damage
1.5e16 wei). Jury transport is the probe-proven bytes form.

## Fast-clock twin jury arc (2026-11-13)

Purpose: prove the full AI-jury arc end-to-end TODAY without touching production.
Production v1.1 (0x3F46DbbA110Bf42EdE496f88e4a200392d9B2195) and v1
(0x420447DD4a4d6561b6e579C61a18262C5d891254) were NOT modified or redeployed.

### Twin source and the exact diff
- Production source confirmed: DepositCourt.py, sha256
  33760b54fccef0bd264db872e31b1857d6367af9b921a0d046a1c7db9460888a, identical to the
  v1.1 deployment record in ~/workspace/gmv-bradbury/v2/deployment-depositcourt-v1.1.json.
- Timing proof: DAY = 86400 (line 26) feeds exactly four window assignments -
  the landlord-revision challenge re-arm (line 192), the claim-schedule challenge
  deadline (line 370), the INCONCLUSIVE re-open deadline (line 518), and the appeal
  deadline set by finalize_assessment (line 537). All other DAY uses (30-day stale
  tenancy, 14/30-day expiry paths, date parsing) are unrelated and untouched.
- Twin: DepositCourt.twin.py, 38,971 bytes, sha256
  8f3e68d43934f04a33a547fa385ab6681d0e4ff5361767500b3aef41f50aff05, py_compile OK.
  Diff vs production = exactly 5 lines: one added line
  "WIN = 600 # TWIN FAST-CLOCK: test deployment only" after line 26, and DAY -> WIN
  at lines 192, 370, 518, 537. Return-message strings still say "24h" (cosmetic;
  left untouched to keep the diff minimal). Both 24h windows are therefore 600s
  on the twin; production keeps 24h.
- Offline harness (tests/harness.py) SKIPPED by design: it hardcodes the production
  source path and cannot run the twin without editing tooling.

### Deployment
- Twin address: 0x8f4A51E940e9dA2eb67364a91072fE0b40bDCc42
- Deploy tx: 0xf3052bedad8d5a1e1b48fba9d15dba0f923f691f74a12026140cb181b5f60f0f
  (FINALIZED / MAJORITY_AGREE / FINISHED_WITH_RETURN, 5 validators), deployed
  2026-11-13 12:32 PKT by test wallet A via ~/workspace/gmv-bradbury/v2/deploy-any.mjs;
  record ~/workspace/gmv-bradbury/v2/deployment-depositcourt-twin.json.

### Case 0 - exact mirror of v1 case 1 (PNG pair)
Tenant B created case "Flat 4 JLT" (DISPUTE_TIME) and funded 0.05 GEN; landlord A
filed lease + 2-claim schedule (claim_1 "wall stains and marker drawings"
20000000000000000 wei clause_7; claim_2 "broken blind slats" 10000000000000000 wei
clause_7) + photos (move_in [img-b-in, A1], move_out [img-b-out, A2]); B filed
counter-messages + counter-photos (move_in [A3], move_out [A1]); A filed lease
revision (ver 2, rev 1); B re-filed messages. All FINISHED_WITH_RETURN.
- create_dispute 0x8b7feb7b38055928db7cc183da204e30cf0f2f59f12ebde7b903d8ef622ff3a6 (12:34 PKT)
- fund_dispute   0xbb613c8aae03b49403ff717522e3eb1889755f2900f4edac7b505b04daa97c5a
- evidence txs   0xb3087286304b1eafa751ecd12579a83ce2aeb99a947efe3a8c366b3b5cb4d9af,
  0xbf7ff952a0b64081cd76ebf0f77824407cf55b6c8bdc3bc9adbb3d87c86eccd0,
  0x4d7692ef57596f087868a95e4a464b73a6f8a13a22a3f2cdc16af978a9cd4452,
  0x772e5dd9ab9330339e499e1981228ac56ad5a9a7b1c40e82f76f75bb4423c839,
  0xae8f73c772d27a0e33cb41c00bb1f150a76a5973d06abf2304d7eb71c0922dbe,
  0xba0a0489205fb030c6e07b181cbf6daf04f3df4f3540d04af3889e59368e9e08,
  0x4b715c0ffdff65f15d91988e37e2775e9cb2ee46d5a036dabee933ba896d4150
- freeze_evidence 0xc6d1188aee35c474211817ecf1d671fc417ae1c4acd5ac258931c42967184bf6
  (12:55 PKT) -> FROZEN, snapshot set. Challenge deadline had been 12:53 PKT (600s twin window).

### Case 1 - same scenario, JPEG-encoded photo pair (DEVIATION, see below)
Identical parties, lease + revision, claims, amounts and tenant evidence, except the
two B photographs were submitted as their JPEG-s encodings (the transport ProbeB2
proved on 2026-11-12): img-b-in-s.jpg sha256
2f1bc919c72a857baa57cc207c0ce5eb4bcfdbc3ca605d4f1cb448a867379ea3,
img-b-out-s.jpg sha256 92d1217455717e8c6c372d3c32b115c2d40659e31760980ed25cdd6cf5ab44cf.
- create_dispute 0xd251bd1a8b2820437b582c001fdc2ad238d7ff6b5463d8378ed65e40bb0658fe (13:22 PKT)
- fund_dispute   0xf3d07a6572c60d6d047f9546ebf6e07f0f73051d2a0bfd747b9cef29604fd1c8
- evidence txs   0x8acbbb39aeaac412369e3194dd2a12cd570117292d7da9c17095dd4d2b35bd80,
  0x6e7af85c10f742bc7a026cb8c337d5cceba084c888df6803c2b7f2f41bf3b575,
  0x11addcbdd7ae724bc786c5ab473ab120d95a9f30a3f324941a66fe1249b05c1e,
  0x9d2c6d09766b5f88b4803b2d965215bc21fb8e186fc4c14a6b46262c7d16387a,
  0x59964c5a0911c7c74cd978d18c4f1224be753f6532464970488aba41c13f3d1e,
  0x071e3414115985d360740c6758ca6c9357eaa47354133ccd6baf7d40493917ef,
  0x1347ce2e44c2e2c2618e31a1c290a6883573a5f75d775dfe7f6a3b37d79f7abd
- freeze_evidence 0xe4fd1940ea07d9e3b85b39e7cf059eb0eb294e23f92ebb7b2e709b21f961f82f
  (13:50 PKT) -> FROZEN, snapshot set.

### Jury phase - 87 assess_claim attempts, 1 verdict recorded
Direct attempts: case 0 claim_1 x5, claim_2 x4; case 1 claim_1 x3 - all failed.
Then retry loops (tests/twin-retry-loop.mjs, tests/twin-retry-c1.mjs) logged 74
further attempts, plus 1 attempt whose driver was killed mid-receipt-wait by a
runtime restart (no verdict resulted; chain-verified). Total 87 assess_claim
transactions. Every failure was fail-closed: case state untouched (FROZEN,
attempts counter and verdict map unchanged) after every single one.

Failure taxonomy across the day: the dominant mode was FINISHED_WITH_ERROR -
receipt eqBlocksOutputs decode to the GenVM runner crash (nd_outs exit_code 1),
the same failure probes/PROBE_RESULTS.md bisected on 2026-11-12 to this contract's
image-jury path - plus NO_MAJORITY, MAJORITY_TIMEOUT, MAJORITY_DISAGREE and
IDLE / NOT_VOTED outcomes. Bradbury's jury transport on 2026-11-13 was far worse
than on 2026-11-12, when the identical pipeline produced agreed verdicts in
ProbeB2 (2 in 8 attempts).

THE ONE VERDICT (case 1, claim_1): tx
0x352289046176bbd442b43bcaddb9a39312f1ca731174d7a48d3dc6cc001e874e,
2026-11-13 15:33 PKT, FINISHED_WITH_RETURN / MAJORITY_AGREE:
{"claim_id":"claim_1","category":"TENANT_DAMAGE","bucket_pct":100,
"reason_code":"CLAUSE_BREACH","msg_support":"NONE","photo_pair_id":"pair_1"}
Read back from chain state (get_case cvs), not from the receipt alone. It implies
a 20000000000000000 wei deduction on claim_1 IF the case finalizes with claim_2
also assessed - finalize_assessment has NOT run, so no entitlement or split
exists yet.

### Where the arc stopped (chain-verified 2026-11-13 ~19:10 PKT)
- Case 0: FROZEN, no verdicts. Case 1: FROZEN, claim_1 verdict recorded,
  claim_2 unassessed. finalize_assessment / release_split / claim_payout were
  therefore never reached on either case; no payout deltas exist to report.
- Conservation EXACT at every read: contract balance 100000000000000000 wei ==
  locked 100000000000000000 wei (both deposits), bondw/tcw/tpw all 0.
- Both cases remain FROZEN and resumable: nothing expires a FROZEN case, and
  assess_claim can be retried at any time. The remaining work is purely more
  assess_claim retries until claim_2 (case 1) lands, then finalize -> wait the
  600s appeal window -> release_split -> claim_payout + confirm_withdrawal
  per party (drivers: tests/live-twin-arc2.mjs finalize/release/claim phases).

### Deviations and incidents (all disclosed)
1. Offline harness skipped (hardcodes the production source path).
2. Case 1's photo pair submitted as JPEG-s re-encodings of the same two
   photographs (hashes above) instead of the PNG bytes - the transport ProbeB2
   proved; case 0 kept the exact PNG mirror and its 9 direct attempts all
   failed. The one verdict of the day landed on the JPEG case.
3. Driver misfire during case-1 staging: a sed-generated driver sent 6 evidence
   calls to the already-FROZEN case 0; its evidence gate rejected all 6, state
   unchanged (preserved in tests/twin-arc2-misfire-results.json and
   tests/receipts-twin2-misfire/). Fixed by correcting the case-id arguments.
4. Retry loops were interrupted twice by runtime restarts and once by a pkill
   self-match; after each interruption the chain state was read and verified
   before resuming, and no attempt was ever double-submitted against a claim
   that already held a verdict.
5. The drivers' pkt() label helper used UTC+4; all timestamps in this section
   were recomputed from epoch with UTC+5 (true PKT).

Drivers and data: tests/live-twin-arc.mjs, tests/live-twin-arc2.mjs,
tests/twin-retry-loop.mjs, tests/twin-retry-c1.mjs, tests/twin-arc-results.json,
tests/twin-arc2-results.json, tests/twin-retry-results.json (all 74 loop
attempts with tx hashes), tests/receipts-twin/, tests/receipts-twin2/,
tests/receipts-retry/.

## v1.3 — tenant counter-photo stage (2026-11-16)

### What the evidence path does now
Every claim line is decided in two consensus-bound stages inside one
assessment call. Stage 1 is the original jury over the landlord's photo
pair, the lease and both parties' messages. If stage 1 returns a
photo-based TENANT_DAMAGE line with a positive bucket and the tenant
filed counter-photos for that line, the line is cached in a per-case
scratch slot and a second jury call (stage 2) judges the tenant's own
move-in / move-out pair for that line. Stage 2's photos pass the same
SHA-256 binding as the landlord's, plus image-format magic bytes and a
5 MB size cap, before any prompt runs; photos that fail verification
record counter_verdict UNVERIFIED and the stage-1 line stands. A
verified pair returns one folded verdict — REBUTS_PRE_EXISTING,
REBUTS_NO_DAMAGE or DOES_NOT_REBUT — and deterministic code merges it:
a rebuttal rewrites the line to bucket 0 (PRE_EXISTING /
PRE_EXISTING_MATCH, or LANDLORD_RESPONSIBILITY / PHOTO_MISMATCH);
DOES_NOT_REBUT leaves the stage-1 line untouched. The outcome is stored
on the line as counter_verdict and exposed by get_deduction_schedule.
If stage 2 cannot reach a verdict, the assessment fails as a retryable
JURY_FAILURE and the cached stage-1 line is reused on the next attempt,
so a photo-based deduction is never stored for a line whose verified
counter-photos have not been judged.

### Offline verification
- tests/test_v13_counterstage.py: 10/10 (both rebuttal mappings,
  DOES_NOT_REBUT passthrough, hash-mismatch and bad-magic and oversize
  pairs short-circuit to UNVERIFIED with zero prompt calls, stage-2
  failure keeps the cached line and the retry does not re-run stage 1,
  no-photo and bucket-0 lines skip stage 2, appeal path).
- tests/test_pure.py: 31/31 against the v1.3 source (no regressions).

### Deployed artifact
The readable source is 43,941 B, over Bradbury's ~39,000 B deployment
wall, so the deployed artifact is a semantics-preserving compact form
(37,170 B): python-minifier with import combining, literal hoisting,
local renaming and dead-code removal all OFF; the two header lines are
byte-identical to the readable source; the two files' ASTs compare
equal, and both offline suites pass against the compact file as well.
- Production: 0xf396F412910D173CFEA65dC0081401343d330b6C
- Deploy tx: 0x7c8cbacbe6e65c70cafd46fdd378ee0f692faea79ef129fba4c0dd220560b2a4
  (MAJORITY_AGREE, FINISHED_WITH_RETURN)
- Source sha256: a1bb02591b4241df7301c255aeda63eb5a9ab73570de298d31e9149038fca0ad
  (== DepositCourt.py in this repo)

### Live proof (fast-clock twin, delta-only)
Twin 0x220629736311851090bb81E233E0F81b3F929163 = the compact source
with only the challenge and appeal windows at 600 s (sha256
5e502ee1b5279c0da6eb57be3f28e19399b1b850411df0a0c0d10de0c255e650).
Everything except the new stage stands on v1.1's completed live proof.
- Case R (tenant counter move-in photo = the stained wall): stage 1
  TENANT_DAMAGE, stage 2 REBUTS_PRE_EXISTING; stored line PRE_EXISTING,
  bucket 0, PRE_EXISTING_MATCH, counter_verdict REBUTS_PRE_EXISTING;
  deduction 0 wei; entitlements tenant 0.05 GEN / landlord 0 / fee 0;
  tenant withdrew the full deposit. Assessment tx
  0x2e23b12ab9cd432c2d2d384d8e1fc168c62c8fdeef25d881d7a08ecc6c7dc0d4
  (5 attempts).
- Case N (tenant counter-photos = clean move-in / stained move-out):
  counter_verdict DOES_NOT_REBUT; line stands TENANT_DAMAGE, bucket
  100, CLAUSE_BREACH; deduction 0.03 GEN; entitlements tenant 0.02 GEN
  / landlord 0.0299 GEN / protocol fee 0.0001 GEN; all three withdrew.
  Assessment tx
  0xb96c0a8cdd953bf0f89ef61e4deac7051785efe3a5688404cb3b922a7e7079fa
  (24 attempts across three driver runs — leader crashes and validator
  disagreements on the vision path, the same host-side pattern recorded
  for v1.1; no attempt changed state before the verdict landed).
- Fund conservation held at every checkpoint; after both settlements
  the twin's balance fell by exactly the released entitlements.
- Drivers: tests/live-v13-proof.mjs, tests/live-v13-proof-resume.mjs,
  tests/live-v13-proof-resume2.mjs; results tests/v13-proof-results.json;
  receipts tests/receipts-v13proof/. Two driver runs were interrupted
  by runtime restarts; after each, chain state was read and verified
  before resuming, and no step was re-sent against state that already
  held its result.
