# DepositCourt — Portal filing pack

Ready for Ameer's submission step. Repo step first: create the empty
GitHub repo `depositcourt` (the app cannot create repos), then Atlas
pushes `DepositCourt.py` + `README.md` + tests, then submit with the
fields below.

## Title

```
DepositCourt — rental deposits decided by an AI jury, paid on chain
```

## Description

```
DepositCourt is an Intelligent Contract on GenLayer Bradbury that settles
rental deposit disputes. The tenant's deposit is locked in the contract.
At the end of the tenancy the landlord files deduction claims, and an AI
jury decides each claim from the lease, the parties' messages, and the
move-in and move-out photo pairs. Every photo and document is bound by
SHA-256 when it is filed, and the contract verifies the hash of the bytes
the jury actually sees. The landlord gets one evidence revision, the
tenant gets a fresh challenge window after it, and the losing side can
appeal once for a blind second assessment. The verdict splits the deposit
by fixed buckets, and each party withdraws their own share — payouts are
proven by exact balance changes, not by receipts saying success.

What is live and verifiable: the full settlement lifecycle ran on chain
with wei-exact payouts (0.05 GEN case, tenant 0.04 / landlord 0.01, case
closed, contract back to zero for it). 19 out of 19 attack attempts were
blocked live. The AI jury has recorded verdicts on chain for the
wall-stain claim — TENANT_DAMAGE at bucket 100 under clause 7 — on a
fast-clock twin of the production contract and on a verbatim replica of
the production jury, with byte-identical verdict lines. Fund conservation
held at every checkpoint: the contract balance always equals locked +
bonds + claimable + pending, and time-based exits mean no deposit can be
stranded, even if a party disappears or a jury round has to be retried.
```

## Evidence links

- Contract (production v1.1, Bradbury):
  https://scan.bradbury.genlayer.com/address/0x3F46DbbA110Bf42EdE496f88e4a200392d9B2195
- Source in this repo: `DepositCourt.py`
  (sha256 `33760b54fccef0bd264db872e31b1857d6367af9b921a0d046a1c7db9460888a`,
  identical to the deployed source)
- dApp: https://depositcourt-ameer-hamza-s-projects2.vercel.app
- Jury verdict, fast-clock twin of the production contract (validator
  majority, TENANT_DAMAGE 100 / CLAUSE_BREACH):
  tx `0x352289046176bbd442b43bcaddb9a39312f1ca731174d7a48d3dc6cc001e874e`
- Jury verdict, verbatim replica of the production jury (validator
  majority, byte-identical line), 2026-11-13:
  tx `0x225363b2e0bbfa7f11dedab38d03e84fc77e61a6baeec0f2b9b84e7a2cfa7ce6`
- Build and test record: `BUILD_RECORD.md`, jury diagnosis and proof:
  `JURY_FIX_REPORT.md`, offline suite: `tests/test_pure.py`, live
  receipts: `tests/receipts*`
