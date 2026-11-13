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
DepositCourt is an Intelligent Contract on GenLayer Bradbury for rental deposit disputes. The tenant's deposit is locked in the contract. At tenancy end the landlord files deduction claims, and an AI jury decides each claim from the lease, both parties' messages, and move-in/move-out photo pairs. All evidence is SHA-256 bound when filed; the contract verifies the hash of the bytes the jury sees. The landlord gets one evidence revision, the tenant a challenge window after it, and the loser can appeal once for a blind second assessment. Verdicts split the deposit by fixed buckets; each party withdraws their own share.

Live and verifiable: a full settlement ran on chain with wei-exact payouts (0.05 GEN case: tenant 0.04, landlord 0.01, closed). 19 of 19 attacks were blocked live. The jury recorded verdicts on chain (wall-stain claim: TENANT_DAMAGE, bucket 100, clause 7), byte-identical across two independent jury runs. Conservation held at every checkpoint; no deposit can be stranded.
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
