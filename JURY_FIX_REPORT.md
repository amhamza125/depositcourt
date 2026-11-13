# DepositCourt Jury Fix Report — 2026-11-13 (night run)

**Order:** Ameer, 2026-11-13 18:19 PKT — "Do whatever you want but contract
should be fix till morning." Deadline: morning Nov 14 (~08:00 PKT).
**Scope:** v1 jury arc stuck (cases 1 + 3 FROZEN, every assess failing);
a "fixed" twin deployed by the previous agent but never driven; production
v1.1 (0x3F46DbbA110Bf42EdE496f88e4a200392d9B2195) shares v1's jury code.

Contracts referenced:
- v1 production-era: `0x420447DD4a4d6561b6e579C61a18262C5d891254` (24h windows)
- v1.1 production: `0x3F46DbbA110Bf42EdE496f88e4a200392d9B2195` (24h windows)
- v1.1 fast-clock twin: `0x8f4A51E940e9dA2eb67364a91072fE0b40bDCc42` (WIN=600s)
- "fixed" twin (v1.2+PIL shrink): `0xe74F8CeB04F62Fd62207Cac2fB890a0aA68BbFED` (WIN=600s)
- ProbeD (bisect replica): `0x8B937FFc7e7C3590509749891C5DfD412d328E10`

---

## 1. Root cause (from receipts, not guesses)

Every failed assess on every contract shows the same receipt signature:
the eq block output is `nd_outs … exit_code 1` — the leader's nondet
execution **dies host-side** (GenVM v0.3.0-rc10) before producing output.
It is not a contract-level error: `att` stays 0, no state changes, escrow
untouched, and the contract's own try/except never sees it (the crash
bypasses Python entirely — the same signature recorded in
`probes/PROBE_RESULTS.md` on Nov 12).

Bisect on ProbeD (a verbatim replica of the fixed twin's jury() for the
staged case — same prompt, same images, same schema), 2026-11-13 evening:

| Mode | Shape | Result |
|---|---|---|
| `text` | full jury prompt, NO images | FINISHED_WITH_RETURN — leader produced a verdict JSON (NO_MAJORITY on validator variance) |
| `small` | fetch + PIL shrink + tiny prompt + images (≈ ProbeC2) | NOT_VOTED/IDLE (network idle; ProbeC2's identical run passed 1 of 2 on Nov 13) |
| `full` | fetch + PIL shrink + full prompt + images (= fixed twin) | **FINISHED_WITH_ERROR** — leader crash reproduced in the replica |
| `raw` | fetch + full prompt + RAW images, no PIL | **FINISHED_WITH_RETURN** — leader verdict `{"bucket_pct":100,"category":"TENANT_DAMAGE","claim_id":"claim_1","msg_support":"NONE","photo_pair_id":"pair_1","reason_code":"CLAUSE_BREACH"}` (NO_MAJORITY) |

Established facts behind the table:
- The mechanism is sound: hash-verified image bytes in `images=[...]`
  reach the vision model (ProbeA/B, Nov 12–13), and correct verdicts have
  reached MAJORITY_AGREE on this exact contract shape — ProbeB runs 2–3
  (byte-identical verdicts), ProbeC2 `probe_steps`, and the v1.1 twin's
  case 1 claim_1 (tx `0x35228904…`, TENANT_DAMAGE 100 / CLAUSE_BREACH).
- The failure is a **reliability property of the runner's vision nondet
  path**, not a code bug: across 74 assess attempts on the v1.1 twin,
  leaders returned in only 16 (22%); exactly 1 reached MAJORITY_AGREE.
  Text-only strict_eq juries on the same runner (GrantFlow, ExpenseCheck)
  settle routinely; vision calls crash/timeout at a high rate, worse with
  high-entropy PNG photo pairs than with 400×300 JPEG pairs (ProbeA
  bisect: the 800×600 PNG pair crashed deterministically; the JPEG pair
  is the only photo configuration that ever reached consensus twice —
  and the one verdict landed on the twin was on the JPEG-evidenced case).
- Success arrives in windows (ProbeB runs 2–3 back-to-back; long dry
  spells between). The contract design already anticipates this:
  permissionless `assess_claim`, an attempts counter, and time-based
  exits (§6.6) are load-bearing, not decorative.

## 2. The inherited "fix" — what it changes, and the verdict on it

`DepositCourt.fixed.py` vs `DepositCourt.v1.py.bak` (full diff taken
2026-11-13). Two families of changes:

**(a) The v1.1 audit fixes — principled, keep.** Dust floor removed in
`_rejv` (every rejected wei credited); `LANDLORD_RESPONSIBILITY` added to
the bucket-0 categories in `_vline`; `ALREADY_ASSESSED` guard in
`assess_claim` (a recorded line locks; jury failures stay retryable);
`submit_invoices` restricted to FUNDED; landlord slot `rev` reset on
INCONCLUSIVE re-open in `_incex`; `confirm_withdrawal` only marks a role
claimed when its pot is 0; pre-fee nets in the appeal losing-party check;
pause gate on `resolve_appeal`. (All already present in production v1.1.)

**(b) The jury change — `_shrink`: NOT principled as a fix; it hurts.**
Before `exec_prompt`, both hash-verified images are re-encoded in-contract
via PIL (decode → RGB → resize 400×300 → save PNG); on any exception the
original bytes pass through. Hash-binding and fail-closed behaviour are
preserved (the hash check runs on the original bytes before shrinking, and
the fallback never invents data) — so it is not a safety violation. But as
a *reliability* fix it is contradicted by the evidence gathered tonight:

- PIL itself is only half-available in the sandbox: the JPEG re-encode
  variant failed deterministically (`{"error":"PIL_FAILED"}` agreed by
  validators, ProbeC run-pil1); the PNG-resave variant works (ProbeC2).
- In the full jury shape, the shrink variant crashed the leader in the
  ProbeD replica (`full` mode) and in **all 6 assess attempts** driven on
  the fixed twin tonight (1 NOT_VOTED, 5 FINISHED_WITH_ERROR), versus a
  22% leader-return rate for the raw form on the v1.1 twin and a
  FINISHED_WITH_RETURN for ProbeD `raw` mode with the identical prompt
  and images. The in-contract decode/resize/encode of two photos adds
  CPU/memory work inside the same nondet execution that is already dying
  host-side; the data says it makes the crash more likely, not less.
- It also degrades the evidence the jury sees (400×300 re-encode of
  photos whose hashes were committed at full size) for no proven gain.

**Correction applied:** `DepositCourt.v1.2.py` (prepared tonight,
sha256 `3fe06cd3d4fac2f3b4b5ddb79a2a5f86eb3f56eca3a31b9e9680efc965d29729`,
38,837 bytes) = fixed.py **with `_shrink` removed** — images pass to the
jury as the hash-verified original bytes, exactly as in v1/v1.1 — keeping
the audit fixes and the jury-prompt clarifications from fixed.py
(bucket_pct wording, the verified-invoice note, honest tenant-photo
note). Offline pure suite: **31/31 PASS** against this source.

The real reliability lever is on the **evidence side**, not in-contract:
submit photos as 400×300 JPEG (the only configuration with repeated
consensus in probes). That is client/dApp guidance; the contract accepts
any hash-bound bytes.

## 3. Proof runs tonight

### 3a. Fixed twin (0xe74F8CeB…) case 0 — driven as instructed
- freeze_evidence(0): tx `0x9734ead07c45112693ed9b68a5ebca87f670c51c754a694a554a17c817604069`
  — FINISHED_WITH_RETURN / MAJORITY_AGREE, case FROZEN, snapshot set.
- assess_claim(0,"claim_1") ×3: `0x79d17b57…` NOT_VOTED/IDLE;
  `0x7d9a3893…` FINISHED_WITH_ERROR/MAJORITY_AGREE;
  `0x087ba2dd…` FINISHED_WITH_ERROR/NO_MAJORITY.
- assess_claim(0,"claim_2") ×2: `0xeb8cdd2e…` FINISHED_WITH_ERROR/MAJORITY_AGREE;
  `0x0f195b58…` FINISHED_WITH_ERROR/NO_MAJORITY.
- (plus one further claim_1 attempt `0x981ce68c…` FINISHED_WITH_ERROR/NO_MAJORITY)
- **No verdict landed on the fixed twin.** Combined with the ProbeD
  bisect, this is the evidence that the shrink variant is the wrong
  direction; driving it further was stopped in favour of the raw form.

### 3b. v1.1 twin (0x8f4A51E9…) — production-identical jury code
- Pre-existing: case 1 claim_1 verdict on chain (tx `0x352289046176bbd442b43bcaddb9a39312f1ca731174d7a48d3dc6cc001e874e`):
  TENANT_DAMAGE, bucket 100, CLAUSE_BREACH, photo_pair_id pair_1.
- Tonight: a second bounded retry loop (`tests/twin-retry-loop.mjs`,
  34 attempts, wallet A) ran from 19:41 PKT. In the one-hour priority
  window it completed 12 attempts — 11 leader crashes, 1 leader return
  (attempt 10, case 0 claim_2, FINISHED_WITH_RETURN / MAJORITY_TIMEOUT —
  verdict produced but not recorded). Case 1 still needs claim_2; the
  loop was left running to its bound after this report's proof landed
  (log: `tests/twin-retry-loop2.log`). If it completes case 1,
  `finalize` → `release` → `claim` phases are in
  `tests/live-twin-arc2.mjs`.

### 3c. ✅ PROOF — agreed jury verdict recorded on chain (one-hour order met)
At Ameer's 20:08 PKT priority order (verdict on chain by ~21:10 PKT), a
parallel loop drove ProbeD — the verbatim replica of the fixed jury —
from wallet B in `raw` mode (hash-verified original bytes, the v1.2
form). Attempt 9 landed inside the hour:

- **Tx `0x225363b2e0bbfa7f11dedab38d03e84fc77e61a6baeec0f2b9b84e7a2cfa7ce6`**
  (2026-11-13 15:38 UTC / 20:38 PKT), FINALIZED, FINISHED_WITH_RETURN,
  **MAJORITY_AGREE**.
- Agreed verdict, read back from the receipt eq block AND from contract
  storage (`get_last_result`):
  `{"bucket_pct":100,"category":"TENANT_DAMAGE","claim_id":"claim_1","msg_support":"NONE","photo_pair_id":"pair_1","reason_code":"CLAUSE_BREACH"}`
  — substantively correct for the scenario and byte-identical to the
  verdict the v1.1 twin recorded earlier today and to ProbeB's agreed
  verdicts of Nov 12.
- Loop record: attempts 2 and 3 also produced leader verdicts
  (NO_MAJORITY — one differed only in bucket, 50 vs 100, the strict_eq
  variance tax); attempts 1, 4–8 crashed leader-side. 9 attempts,
  ~25 minutes, one agreement — consistent with the day's rates.
- Precision note: ProbeD is a probe contract whose jury() is a verbatim
  copy of the production jury (same prompt text, same fetch/hash form,
  same verdict schema, same strict_eq), built to bisect the crash. The
  verdict above is a real validator-majority jury verdict on chain for
  the production jury logic in its fixed (v1.2) form. The same verdict
  line also stands recorded in a DepositCourt contract itself (the
  v1.1 twin, tx in §3b).

## 4. v1 frozen cases 1 + 3 (production 0x420447DD…)

Left FROZEN, deliberately. The 9-attempt retry loop earlier today
(`tests/jury-retry-results.json`) plus the original arc attempts all hit
the same host-side crash; nothing about tonight's findings gives v1's
PNG-evidenced cases a better per-attempt chance than the twins, and their
24h appeal windows mean a landed verdict tonight still could not complete
the arc before the Saturday deadline. Escrows are intact (0.05 GEN each;
contract balance == locked == 0.1 GEN at last read) and the cases remain
assessable by anyone, permissionlessly, whenever the runner has a good
window; the time-based exits protect the tenants' deposits regardless.
No funds were moved and no state was changed on v1 tonight.

## 5. Production recommendation

- **Do NOT redeploy production tonight.** Production v1.1's jury code is
  byte-identical in mechanism to the v1.1 twin's (raw hash-verified
  images, strict_eq, per-claim calls), and the fixed jury form (v1.2 =
  v1.1 mechanism + prompt clarifications) now has a validator-majority
  verdict on chain (§3c). The only "fix" that differed mechanically
  (PIL shrink) is disproven by tonight's data, so there is nothing to
  redeploy *for*.
- `DepositCourt.v1.2.py` (shrink removed, prompt clarifications kept,
  31/31 pure tests) is prepared and recorded above if Ameer wants the
  cosmetic jury-prompt improvements later; it should get its own twin
  proof before any production swap, per standing practice.
- **dApp/client guidance (the actual fix users feel):** evidence photos
  should be prepared as 400×300 JPEGs before submission — the only
  format with repeated on-chain consensus — and the dApp should present
  assess as "keep trying; verdicts land in windows" with the attempts
  counter visible, since retries are the designed path (§6.6).
- Residual risk, stated plainly: verdict latency on Bradbury's vision
  path is outside the contract's control. Conservation and exits do not
  depend on the jury ever answering; no deposit can be stranded by jury
  silence.

## 6. Conservation

- Fixed twin: balance == lockw == 50,000,000,000,000,000 wei before and
  after tonight's run (re-read at report time; case 0 still FROZEN,
  cvs empty); bondw/tcw/tpw 0. No payouts attempted (no verdict → no
  release), so no balance-delta proof is owed.
- v1.1 twin: balance == lockw == 100,000,000,000,000,000 wei at report
  time; bondw/tcw/tpw 0; case 1 claim_1 verdict intact.
- ProbeD holds no funds (probe contract; verdicts only).
- v1: untouched tonight; balance == locked == 0.1 GEN (Nov 13 arc read).

## 7. Filing pack

Produced alongside this report: `FILING_PACK.md` (title + description +
evidence links, in Ameer's slot format) and a repo-ready `README.md`.
Repo state for the push: production source `DepositCourt.py` (v1.1,
sha256 `33760b54…`) + `README.md` + tests + `BUILD_RECORD.md` + this
report. Remaining human step: Ameer creates the empty `depositcourt`
GitHub repo (the app cannot create repos); the push is then mechanical.

## Appendix — ProbeD deployment note

ProbeD's first two deploys failed deterministically (FINISHED_WITH_ERROR,
all 5 validators agreeing) because its header comment block sat between
the `# { "Depends": ... }` line and the imports — the documented deploy
gotcha. Moving the comments below the imports fixed it
(`0x8B937FFc…`, FINISHED_WITH_RETURN). DepositCourt sources do not have
this defect (their title comment sits after the imports).
