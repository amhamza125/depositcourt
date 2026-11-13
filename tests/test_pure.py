"""Offline pure tests for DepositCourt (stubbed GenVM). Run: python3 test_pure.py"""
import sys, json, calendar
sys.path.insert(0, "/home/hatch/workspace/depositcourt/tests")
import harness
from harness import fresh, call, expect_err, conserve, sha, A, B, C, DAY
import genlayer as gl

T0 = calendar.timegm((2026, 11, 12, 0, 0, 0))
DEP = 10 ** 17            # 0.1 GEN deposit
FEE = 10 ** 14
BOND = 10 ** 14
PASS = []
FAIL = []

def check(name, fn):
    try:
        fn()
        PASS.append(name)
        print("PASS", name)
    except Exception as e:
        FAIL.append((name, repr(e)))
        print("FAIL", name, "->", repr(e))

def new_case(c, dep=DEP, path="TENANCY_START", tstart=None, tend=None):
    tstart = T0 - 300 * DAY if tstart is None else tstart
    tend = T0 - 10 * DAY if tend is None else tend
    r = call(c, A, c.create_case, A, B, "Flat 1", str(dep), str(tstart), str(tend), "en", path)
    assert r.startswith("CASE #"), r
    return int(r.split("#")[1].split(" ")[0])

LEASE = "Lease text. Clause 7: tenant returns property in same condition, wear excepted."
CLAUSES = json.dumps([{"clause_id": "clause_7", "text": "Return in same condition, wear excepted."}])
IMG_IN = b"\x89PNG move-in bytes"
IMG_OUT = b"\x89PNG move-out bytes"
RCPT = b"invoice receipt bytes"

def photos_json(n=1):
    return json.dumps({"move_in": [{"url": "https://x.test/in.png", "sha256": sha(IMG_IN)}] * n,
                       "move_out": [{"url": "https://x.test/out.png", "sha256": sha(IMG_OUT)}] * n})

def funded_case(c, dep=DEP, **kw):
    cid = new_case(c, dep=dep, **kw)
    r = call(c, A, c.lock_deposit, cid, value=dep)
    assert "CASE_FUNDED" in r, r
    return cid

def evidence_case(c, dep=DEP, claims=None, **kw):
    cid = funded_case(c, dep=dep, **kw)
    call(c, A, c.submit_lease, cid, LEASE, CLAUSES)
    claims = claims or [{"item": "wall stains", "claimed_amount_wei": str(4 * 10 ** 16), "clause_id": "clause_7"}]
    call(c, A, c.submit_claim_schedule, cid, json.dumps(claims))
    harness.WEB["https://x.test/in.png"] = IMG_IN
    harness.WEB["https://x.test/out.png"] = IMG_OUT
    call(c, A, c.submit_photos, cid, photos_json(len(claims)))
    return cid

def frozen_case(c, dep=DEP, claims=None, **kw):
    cid = evidence_case(c, dep=dep, claims=claims, **kw)
    harness.set_time(harness.now_unix() + DAY + 1)          # challenge window over
    r = call(c, B, c.freeze_evidence, cid)
    assert "EVIDENCE_FROZEN" in r, r
    return cid

def verdict(cat, bucket, reason="CLAUSE_BREACH", support="SUPPORTED", pair="pair_1"):
    def fn(prompt, images):
        cid = "claim_1"
        for line in prompt.splitlines():
            if line.startswith("claim_id:"):
                cid = line.split(":", 1)[1].strip()
        return {"claim_id": cid, "category": cat, "bucket_pct": bucket,
                "reason_code": reason, "msg_support": support, "photo_pair_id": pair}
    return fn

def provisional_case(c, dep=DEP, bucket=50, cat="TENANT_DAMAGE", **kw):
    cid = frozen_case(c, dep=dep, **kw)
    harness.PROMPT_FN = verdict(cat, bucket)
    r = call(c, C, c.assess_claim, cid, "claim_1")
    assert "CLAIM_ASSESSED" in r, r
    r = call(c, C, c.finalize_assessment, cid)
    assert "PROVISIONAL_VERDICT" in r, r
    return cid

# ---------------------------------------------------------------- create/fund
def t_create_validation():
    harness.set_time(T0)
    c = fresh()
    gl.message.sender_address = A
    expect_err(c, A, c.create_case, "0x123", B, "P", str(DEP), "1", "2", "en", "TENANCY_START", code="BAD_ADDRESS")
    expect_err(c, A, c.create_case, A, A, "P", str(DEP), "1", "2", "en", "TENANCY_START", code="BAD_ADDRESS")
    expect_err(c, A, c.create_case, A, B, "P", str(10 ** 15 - 1), "1", "2", "en", "TENANCY_START", code="BAD_AMOUNT")
    expect_err(c, A, c.create_case, A, B, "P", str(2 ** 256), "1", "2", "en", "TENANCY_START", code="BAD_AMOUNT")
    expect_err(c, A, c.create_case, A, B, "P", str(DEP), str(T0 - 400 * DAY), str(T0 - 40 * DAY), "en", "TENANCY_START", code="STALE_TENANCY_END")
    expect_err(c, A, c.create_case, A, B, "P", str(DEP), "1", "2", "en", "WRONG", code="BAD_FUNDING_PATH")
    cid = new_case(c, dep=10 ** 15)   # minimum deposit boundary
    assert cid == 0
    conserve(c)

def t_fund_paths():
    harness.set_time(T0)
    c = fresh(); gl.message.sender_address = A
    cid = new_case(c)
    # wrong sender for lock_deposit
    r = call(c, B, c.lock_deposit, cid, value=DEP)
    assert r.startswith("ONLY_PARTY"), r
    assert c._pot(B, cid) == DEP     # credited claimable (>= floor), no state change
    conserve(c)
    # wrong amount
    cid2 = new_case(c)
    r = call(c, A, c.lock_deposit, cid2, value=DEP - 1)
    assert r.startswith("ESCROW_MISMATCH"), r
    assert c._pot(A, cid2) == DEP - 1
    d = json.loads(c.cases[str(cid2)]); assert d["st"] == "CREATED"
    conserve(c)
    # v1.1 (N-64 flipped): a sub-floor wrong-value send credits claimable exactly
    cid3 = new_case(c)
    r = call(c, A, c.lock_deposit, cid3, value=10 ** 15)   # below the removed 2e15 floor
    assert r.startswith("ESCROW_MISMATCH"), r
    assert c._pot(A, cid3) == 10 ** 15
    conserve(c)
    # proper fund via fund_dispute by tenant
    r = call(c, B, c.fund_dispute, cid3, value=DEP)
    assert "CASE_FUNDED" in r, r
    d = json.loads(c.cases[str(cid3)]); assert d["fu"] == B
    conserve(c)
    # double fund rejected + credited
    r = call(c, A, c.fund_dispute, cid3, value=DEP)
    assert r.startswith("BAD_STATUS"), r
    assert c._pot(A, cid3) == DEP + 10 ** 15
    conserve(c)

def t_cancel():
    harness.set_time(T0)
    c = fresh(); gl.message.sender_address = A
    cid = new_case(c)
    expect_err(c, B, c.cancel_case, cid, code="ONLY_CREATOR")
    r = call(c, A, c.cancel_case, cid); assert "CASE_CANCELLED" in r
    cid2 = funded_case(c)
    r = call(c, A, c.cancel_case, cid2)
    assert "claimable by funder" in r and c._pot(A, cid2) == DEP
    conserve(c)

# ---------------------------------------------------------------- evidence
def t_evidence_gates():
    harness.set_time(T0)
    c = fresh(); gl.message.sender_address = A
    cid = funded_case(c)
    claims = json.dumps([{"item": "x", "claimed_amount_wei": "1000", "clause_id": "clause_7"}])
    expect_err(c, A, c.submit_claim_schedule, cid, claims, code="LEASE_REQUIRED")
    expect_err(c, C, c.submit_lease, cid, LEASE, CLAUSES, code="ONLY_PARTY")
    call(c, A, c.submit_lease, cid, LEASE, CLAUSES)
    expect_err(c, B, c.submit_claim_schedule, cid, claims, code="ONLY_LANDLORD")
    call(c, A, c.submit_claim_schedule, cid, claims)
    # freeze too early
    expect_err(c, B, c.freeze_evidence, cid, code="CHALLENGE_OPEN")
    # 9 claims -> CLAIM_LIMIT; 0 claims -> INVALID_CLAIMS (on a second case)
    cid2 = funded_case(c)
    call(c, A, c.submit_lease, cid2, LEASE, CLAUSES)
    many = json.dumps([{"item": "x", "claimed_amount_wei": "1", "clause_id": "n"}] * 9)
    expect_err(c, A, c.submit_claim_schedule, cid2, many, code="CLAIM_LIMIT")
    expect_err(c, A, c.submit_claim_schedule, cid2, "[]", code="INVALID_CLAIMS")
    conserve(c)

def t_landlord_revision_cap_and_supersede():
    harness.set_time(T0)
    c = fresh(); gl.message.sender_address = A
    cid = evidence_case(c)
    # tenant messages BEFORE any landlord revision: live
    call(c, B, c.submit_messages, cid, "tenant original messages")
    d = json.loads(c.cases[str(cid)])
    assert c._tlive(d, "messages")
    # landlord revises lease once -> tenant messages superseded
    call(c, A, c.submit_lease, cid, LEASE + " v2", CLAUSES)
    d = json.loads(c.cases[str(cid)])
    assert not c._tlive(d, "messages")
    # second landlord revision in EVIDENCE -> locked
    expect_err(c, A, c.submit_lease, cid, LEASE + " v3", CLAUSES, code="EVIDENCE_LOCKED")
    # tenant re-files against the revision -> live again
    call(c, B, c.submit_messages, cid, "tenant updated messages")
    d = json.loads(c.cases[str(cid)])
    assert c._tlive(d, "messages")
    harness.set_time(T0 + DAY + 1)
    r = call(c, B, c.freeze_evidence, cid)
    assert "EVIDENCE_FROZEN" in r
    expect_err(c, A, c.submit_messages, cid, "late", code="ALREADY_FROZEN")
    conserve(c)

def t_photo_validation():
    harness.set_time(T0)
    c = fresh(); gl.message.sender_address = A
    cid = funded_case(c)
    call(c, A, c.submit_lease, cid, LEASE, CLAUSES)
    bad = json.dumps({"move_in": [{"url": "ftp://x", "sha256": sha(IMG_IN)}],
                      "move_out": [{"url": "https://x.test/out.png", "sha256": sha(IMG_OUT)}]})
    expect_err(c, A, c.submit_photos, cid, bad, code="BAD_SCHEME")
    bad2 = json.dumps({"move_in": [{"url": "https://x.test/in.png", "sha256": "zz"}],
                       "move_out": [{"url": "https://x.test/out.png", "sha256": sha(IMG_OUT)}]})
    expect_err(c, A, c.submit_photos, cid, bad2, code="INVALID_PHOTOS")
    bad3 = json.dumps({"move_in": [], "move_out": []})
    expect_err(c, A, c.submit_photos, cid, bad3, code="INVALID_PHOTOS")
    conserve(c)

# ---------------------------------------------------------------- jury/finalize
def t_split_math_and_release():
    harness.set_time(T0)
    c = fresh(); gl.message.sender_address = A
    cid = provisional_case(c)   # claim 4e16 at bucket 50 -> ded 2e16
    d = json.loads(c.cases[str(cid)])
    assert d["vd"]["landlord_wei"] == str(2 * 10 ** 16), d["vd"]
    # release inside appeal window -> blocked
    expect_err(c, C, c.release_split, cid, code="APPEAL_WINDOW_OPEN")
    harness.set_time(T0 + 2 * DAY + 2)
    r = call(c, C, c.release_split, cid)
    assert "CASE_SETTLED" in r, r
    ded = 2 * 10 ** 16
    d = json.loads(c.cases[str(cid)])
    assert c._pot(B, cid) == DEP - ded
    assert c._pot(A, cid) == ded          # landlord share (ded-FEE) + owner fee (FEE), same wallet A
    assert d["ent"] == {"T": str(DEP - ded), "L": str(ded - FEE), "owner": str(FEE)}, d["ent"]
    conserve(c)
    rec = json.loads(c.lrecs[A])
    assert rec["ncd"] == 1 and rec["duw"] == str(ded)

def t_floor_division():
    harness.set_time(T0)
    c = fresh(); gl.message.sender_address = A
    claims = [{"item": "a", "claimed_amount_wei": str(10 ** 16 + 3), "clause_id": "clause_7"}]
    cid = provisional_case(c, claims=claims, bucket=25)
    d = json.loads(c.cases[str(cid)])
    expect = (10 ** 16 + 3) * 25 // 100
    assert d["vd"]["landlord_wei"] == str(expect), (d["vd"], expect)

def t_malformed_verdicts():
    harness.set_time(T0)
    c = fresh(); gl.message.sender_address = A
    cid = frozen_case(c)
    harness.PROMPT_FN = verdict("TENANT_DAMAGE", 33)   # bucket not in set
    r = call(c, C, c.assess_claim, cid, "claim_1")
    assert r.startswith("MALFORMED_VERDICT"), r
    d = json.loads(c.cases[str(cid)])
    assert d["att"] == 1 and d["cvs"] == {} and d["st"] == "FROZEN"
    expect_err(c, C, c.finalize_assessment, cid, code="ASSESSMENT_INCOMPLETE")
    # TENANT_DAMAGE with clause NONE -> malformed
    claims = [{"item": "x", "claimed_amount_wei": str(10 ** 16), "clause_id": "NONE"}]
    cid2 = frozen_case(c, claims=claims)
    harness.PROMPT_FN = verdict("TENANT_DAMAGE", 50)
    r = call(c, C, c.assess_claim, cid2, "claim_1")
    assert r.startswith("MALFORMED_VERDICT"), r
    # WEAR with bucket > 0 -> malformed
    harness.PROMPT_FN = verdict("WEAR_AND_TEAR", 50, reason="NORMAL_WEAR", pair="NONE")
    r = call(c, C, c.assess_claim, cid2, "claim_1")
    assert r.startswith("MALFORMED_VERDICT"), r
    # valid WEAR 0 works
    harness.PROMPT_FN = verdict("WEAR_AND_TEAR", 0, reason="NORMAL_WEAR", pair="NONE")
    r = call(c, C, c.assess_claim, cid2, "claim_1")
    assert "CLAIM_ASSESSED" in r, r
    conserve(c)

def t_excluded_artifact():
    harness.set_time(T0)
    c = fresh(); gl.message.sender_address = A
    cid = evidence_case(c)
    harness.WEB["https://x.test/out.png"] = b"different bytes"   # hash mismatch at jury time
    harness.set_time(T0 + DAY + 1)
    call(c, B, c.freeze_evidence, cid)
    harness.PROMPT_FN = verdict("TENANT_DAMAGE", 100)  # jury stub never runs: exclusion is deterministic
    r = call(c, C, c.assess_claim, cid, "claim_1")
    assert r.startswith("CLAIM_EXCLUDED") and "LANDLORD_PHOTO_HASH_MISMATCH" in r, r
    r = call(c, C, c.finalize_assessment, cid)
    assert "PROVISIONAL_VERDICT" in r
    d = json.loads(c.cases[str(cid)])
    assert d["vd"]["landlord_wei"] == "0"
    harness.set_time(T0 + 3 * DAY)
    call(c, C, c.release_split, cid)
    assert c._pot(B, cid) == DEP and c._pot(A, cid) == 0 and c._pot(c.owner, cid) == 0
    conserve(c)

def t_inconclusive_reopen_then_expire():
    harness.set_time(T0)
    c = fresh(); gl.message.sender_address = A
    cid = frozen_case(c)
    harness.PROMPT_FN = verdict("INCONCLUSIVE", 0, reason="UNPROVEN_CLAIM", pair="NONE")
    call(c, C, c.assess_claim, cid, "claim_1")
    r = call(c, C, c.finalize_assessment, cid)
    assert r.startswith("INCONCLUSIVE"), r
    d = json.loads(c.cases[str(cid)])
    assert d["st"] == "EVIDENCE" and d["icr"] == 1
    # re-freeze and inconclusive again -> EXPIRED, full tenant credit, no fee
    harness.set_time(T0 + 2 * DAY + 2)
    call(c, B, c.freeze_evidence, cid)
    harness.PROMPT_FN = verdict("INCONCLUSIVE", 0, reason="UNPROVEN_CLAIM", pair="NONE")
    call(c, C, c.assess_claim, cid, "claim_1")
    r = call(c, C, c.finalize_assessment, cid)
    assert "CASE_EXPIRED" in r, r
    assert c._pot(B, cid) == DEP and c._pot(c.owner, cid) == 0
    conserve(c)

def t_total_over_escrow():
    harness.set_time(T0)
    c = fresh(); gl.message.sender_address = A
    claims = [{"item": "a", "claimed_amount_wei": str(8 * 10 ** 16), "clause_id": "clause_7"},
              {"item": "b", "claimed_amount_wei": str(8 * 10 ** 16), "clause_id": "clause_7"}]
    cid = frozen_case(c, claims=claims)
    harness.PROMPT_FN = verdict("TENANT_DAMAGE", 100, pair="pair_1")
    call(c, C, c.assess_claim, cid, "claim_1")
    def v2(prompt, images):
        return {"claim_id": "claim_2", "category": "TENANT_DAMAGE", "bucket_pct": 100,
                "reason_code": "CLAUSE_BREACH", "msg_support": "NONE", "photo_pair_id": "pair_2"}
    harness.PROMPT_FN = v2
    call(c, C, c.assess_claim, cid, "claim_2")
    r = call(c, C, c.finalize_assessment, cid)
    assert r.startswith("MALFORMED_VERDICT"), r
    d = json.loads(c.cases[str(cid)])
    assert d["st"] == "FROZEN" and d["vd"] is None
    conserve(c)

# ---------------------------------------------------------------- appeal
def t_appeal_material_refund():
    harness.set_time(T0)
    c = fresh(); gl.message.sender_address = A
    cid = provisional_case(c)   # provisional ded 2e16; tenant net 8e16, landlord net 2e16-FEE; landlord is loser
    # tenant (winner) cannot appeal; v1.1: the rejected bond credits claimable exactly
    r = call(c, B, c.request_appeal, cid, value=BOND)
    assert r.startswith("NOT_LOSING_PARTY"), r
    assert c._pot(B, cid) == BOND
    # landlord appeals with exact bond
    r = call(c, A, c.request_appeal, cid, value=BOND)
    assert "APPEAL_FILED" in r, r
    # appeal jury: WEAR 0 -> total 0; tenant appellant-improvement for landlord = (0-FEE... ) new landlord net = -min(FEE,0)=0? fee=min(FEE,0)=0 -> net 0 vs prov net 2e16-FEE -> improvement negative -> bond to other
    harness.PROMPT_FN = verdict("WEAR_AND_TEAR", 0, reason="NORMAL_WEAR", pair="NONE")
    call(c, C, c.assess_claim, cid, "claim_1")
    r = call(c, C, c.resolve_appeal, cid)
    assert "APPEAL_RESOLVED" in r, r
    d = json.loads(c.cases[str(cid)])
    assert d["st"] == "SETTLED" and d["bst"] == "TO_OTHER", d
    assert c._pot(B, cid) == DEP + 2 * BOND   # full deposit + forfeited bond + the earlier rejected-bond credit
    assert c._pot(A, cid) == 0
    conserve(c)

def t_appeal_upheld_bond_to_other():
    harness.set_time(T0)
    c = fresh(); gl.message.sender_address = A
    cid = provisional_case(c)   # landlord loser appeals, jury confirms same verdict
    call(c, A, c.request_appeal, cid, value=BOND)
    harness.PROMPT_FN = verdict("TENANT_DAMAGE", 50)
    call(c, C, c.assess_claim, cid, "claim_1")
    r = call(c, C, c.resolve_appeal, cid)
    assert "APPEAL_RESOLVED" in r
    d = json.loads(c.cases[str(cid)])
    assert d["bst"] == "TO_OTHER"
    assert c._pot(B, cid) == DEP - 2 * 10 ** 16 + BOND
    assert c._pot(A, cid) == 2 * 10 ** 16   # landlord (ded-FEE) + owner fee (FEE), same wallet
    assert d["ent"]["owner"] == str(FEE)
    conserve(c)

def t_appeal_wrong_bond_and_window():
    harness.set_time(T0)
    c = fresh(); gl.message.sender_address = A
    cid = provisional_case(c)
    r = call(c, A, c.request_appeal, cid, value=BOND - 1)
    assert r.startswith("BOND_MISMATCH"), r
    assert c._pot(A, cid) == BOND - 1     # v1.1: credited exactly, no floor
    conserve(c)
    harness.set_time(T0 + 3 * DAY)
    r = call(c, A, c.request_appeal, cid, value=BOND)
    assert r.startswith("APPEAL_WINDOW_CLOSED"), r
    assert c._pot(A, cid) == (BOND - 1) + BOND
    conserve(c)

# ---------------------------------------------------------------- payouts
def t_pull_payout_cycle():
    harness.set_time(T0)
    c = fresh(); gl.message.sender_address = A
    cid = provisional_case(c)
    harness.set_time(T0 + 2 * DAY + 2)
    call(c, C, c.release_split, cid)
    bal_before = int(c.balance)
    n_tr = len(harness.TRANSFERS)
    r = call(c, B, c.claim_payout, cid)
    assert "WITHDRAWAL_PENDING" in r, r
    assert harness.TRANSFERS[-1] == (B, DEP - 2 * 10 ** 16)
    assert int(c.balance) == bal_before - (DEP - 2 * 10 ** 16)
    assert c._pot(B, cid) == 0
    expect_err(c, B, c.claim_payout, cid, code="PENDING_WITHDRAWAL")
    expect_err(c, A, c.confirm_withdrawal, cid, code="ONLY_RECIPIENT")
    r = call(c, B, c.confirm_withdrawal, cid)
    assert "WITHDRAWAL_CONFIRMED" in r
    expect_err(c, B, c.confirm_withdrawal, cid, code="NO_PENDING")
    # landlord claims once; A is both landlord and owner, so its single pot
    # covers both entitlements and the confirm closes the case.
    call(c, A, c.claim_payout, cid); call(c, A, c.confirm_withdrawal, cid)
    d = json.loads(c.cases[str(cid)])
    assert d["st"] == "CLOSED", d["st"]
    conserve(c)

def t_restore_pending():
    harness.set_time(T0)
    c = fresh(); gl.message.sender_address = A
    cid = provisional_case(c)
    harness.set_time(T0 + 2 * DAY + 2)
    call(c, C, c.release_split, cid)
    call(c, B, c.claim_payout, cid)
    expect_err(c, A, c.restore_pending, B, cid, code="TOO_EARLY")
    harness.set_time(T0 + 2 * DAY + 2 + 601)
    expect_err(c, B, c.restore_pending, B, cid, code="ONLY_OWNER")
    # restore's precondition: the EVM transfer never landed (owner verified
    # off-chain), so the value never actually left the contract balance.
    c.balance += DEP - 2 * 10 ** 16
    r = call(c, A, c.restore_pending, B, cid)
    assert "PENDING_RESTORED" in r
    assert c._pot(B, cid) == DEP - 2 * 10 ** 16
    conserve(c)

# ---------------------------------------------------------------- timeouts
def t_expire_paths():
    harness.set_time(T0)
    c = fresh(); gl.message.sender_address = A
    # unfunded
    cid = new_case(c)
    expect_err(c, C, c.expire_case, cid, code="NOT_EXPIRED")
    harness.set_time(T0 + 30 * DAY + 1)
    r = call(c, C, c.expire_case, cid); assert "unfunded" in r
    # funded silence (TENANCY_START: tend + 30d)
    harness.set_time(T0)
    cid2 = funded_case(c)
    harness.set_time(T0 - 10 * DAY + 30 * DAY + 1)   # tend=T0-10d -> due T0+20d
    r = call(c, C, c.expire_case, cid2)
    assert "to TENANT" in r and c._pot(B, cid2) == DEP
    # funded silence (DISPUTE_TIME: fat + 30d)
    harness.set_time(T0)
    cid3 = funded_case(c, path="DISPUTE_TIME")
    harness.set_time(T0 + 30 * DAY + 1)
    call(c, C, c.expire_case, cid3)
    assert c._pot(B, cid3) == DEP
    # abandoned evidence
    harness.set_time(T0)
    cid4 = evidence_case(c)
    harness.set_time(T0 + 14 * DAY + 1)
    call(c, C, c.expire_case, cid4)
    assert c._pot(B, cid4) == DEP
    # abandoned frozen
    harness.set_time(T0)
    cid5 = frozen_case(c)
    harness.set_time(T0 + DAY + 1 + 14 * DAY + 1)
    call(c, C, c.expire_case, cid5)
    assert c._pot(B, cid5) == DEP
    conserve(c)

def t_appeal_expiry():
    harness.set_time(T0)
    c = fresh(); gl.message.sender_address = A
    cid = provisional_case(c)
    call(c, A, c.request_appeal, cid, value=BOND)
    harness.set_time(T0 + DAY + 1 + 14 * DAY + 1)
    r = call(c, C, c.expire_case, cid)
    assert "APPEAL_EXPIRED" in r, r
    ded = 2 * 10 ** 16
    assert c._pot(B, cid) == DEP - ded
    assert c._pot(A, cid) == ded + BOND          # landlord share with NO fee + bond refund
    assert c._pot(c.owner, cid) == ded + BOND    # owner == A in this harness (same wallet) -> combined above
    conserve(c)

# ---------------------------------------------------------------- settlement/pause/owner
def t_settlement():
    harness.set_time(T0)
    c = fresh(); gl.message.sender_address = A
    cid = funded_case(c)
    expect_err(c, A, c.propose_settlement, cid, str(DEP - 1), "0", code="BAD_SPLIT")
    call(c, A, c.propose_settlement, cid, str(DEP - 10 ** 16), str(10 ** 16))
    expect_err(c, A, c.accept_settlement, cid, code="BAD_STATUS")   # own offer
    expect_err(c, C, c.accept_settlement, cid, code="ONLY_PARTY")
    r = call(c, B, c.accept_settlement, cid)
    assert "SETTLEMENT_ACCEPTED" in r
    assert c._pot(B, cid) == DEP - 10 ** 16 and c._pot(A, cid) == 10 ** 16
    assert c._pot(c.owner, cid) == 10 ** 16  # owner==A combined; fee is 0 (checked via ent)
    d = json.loads(c.cases[str(cid)])
    assert d["ent"] == {"T": str(DEP - 10 ** 16), "L": str(10 ** 16), "owner": "0"}
    conserve(c)

def t_pause_and_sweep_and_ownership():
    harness.set_time(T0)
    c = fresh(); gl.message.sender_address = A
    expect_err(c, B, c.set_paused, True, code="ONLY_OWNER")
    call(c, A, c.set_paused, True)
    expect_err(c, A, c.create_case, A, B, "P", str(DEP), "1", "2", "en", "TENANCY_START", code="PROTOCOL_PAUSED")
    call(c, A, c.set_paused, False)
    # v1.1: a wrong-amount send credits claimable (no floor) -> NOT sweepable excess
    cid = new_case(c)
    call(c, A, c.lock_deposit, cid, value=10 ** 15)
    assert c._pot(A, cid) == 10 ** 15
    expect_err(c, B, c.sweep_excess, code="ONLY_OWNER")
    expect_err(c, A, c.sweep_excess, code="NO_EXCESS")
    # genuine excess (a direct transfer to the contract address) still sweeps exactly
    c.balance += 10 ** 15
    bal = int(c.balance)
    r = call(c, A, c.sweep_excess)
    assert "EXCESS_SWEPT" in r and harness.TRANSFERS[-1] == (A, 10 ** 15)
    assert int(c.balance) == bal - 10 ** 15
    expect_err(c, A, c.sweep_excess, code="NO_EXCESS")
    # two-step ownership
    expect_err(c, A, c.accept_ownership, code="NO_PENDING_OWNER")
    call(c, A, c.transfer_ownership, B)
    expect_err(c, C, c.accept_ownership, code="NOT_PENDING_OWNER")
    call(c, B, c.accept_ownership)
    assert c.owner == B
    conserve(c)

def t_views():
    harness.set_time(T0)
    c = fresh(); gl.message.sender_address = A
    assert c.get_case(99) == "NOT_FOUND"
    cid = provisional_case(c)
    d = json.loads(call(c, C, c.get_case, cid))
    assert d["st"] == "PROVISIONAL_VERDICT"
    sched = json.loads(call(c, C, c.get_deduction_schedule, cid))
    assert sched["lines"][0]["ded_wei"] == str(2 * 10 ** 16)
    assert sched["lines"][0]["reason_text"].endswith("(clause clause_7)")
    ov = json.loads(call(c, C, c.get_protocol_overview))
    assert ov["lockw"] == str(DEP)
    ap = json.loads(call(c, C, c.get_appeal, cid))
    assert ap["bond_wei_required"] == str(BOND)
    conserve(c)

# ---------------------------------------------------------------- v1.1 fixes
def t_already_assessed_lock_and_retry():
    harness.set_time(T0)
    c = fresh(); gl.message.sender_address = A
    cid = frozen_case(c)
    # a jury failure records NO line -> the claim is NOT locked, retry works
    def boom(prompt, images):
        raise RuntimeError("jury down")
    harness.PROMPT_FN = boom
    r = call(c, C, c.assess_claim, cid, "claim_1")
    assert r.startswith("JURY_FAILURE"), r
    d = json.loads(c.cases[str(cid)])
    assert d["cvs"] == {} and d["att"] == 1
    harness.PROMPT_FN = verdict("TENANT_DAMAGE", 50)
    r = call(c, C, c.assess_claim, cid, "claim_1")
    assert "CLAIM_ASSESSED" in r, r
    # a recorded line locks: re-roll attempt rejected
    expect_err(c, C, c.assess_claim, cid, "claim_1", code="ALREADY_ASSESSED")
    # an excluded line is a recorded verdict too -> locked
    cid2 = evidence_case(c)
    harness.WEB["https://x.test/out.png"] = b"tampered bytes"
    harness.set_time(harness.now_unix() + DAY + 1)
    call(c, B, c.freeze_evidence, cid2)
    r = call(c, C, c.assess_claim, cid2, "claim_1")
    assert r.startswith("CLAIM_EXCLUDED"), r
    expect_err(c, C, c.assess_claim, cid2, "claim_1", code="ALREADY_ASSESSED")
    harness.WEB["https://x.test/out.png"] = IMG_OUT
    conserve(c)

def t_already_assessed_appeal_phase():
    harness.set_time(T0)
    c = fresh(); gl.message.sender_address = A
    cid = provisional_case(c)   # landlord is the provisional loser
    call(c, A, c.request_appeal, cid, value=BOND)
    harness.PROMPT_FN = verdict("TENANT_DAMAGE", 25)
    r = call(c, C, c.assess_claim, cid, "claim_1")
    assert "CLAIM_ASSESSED" in r, r
    expect_err(c, C, c.assess_claim, cid, "claim_1", code="ALREADY_ASSESSED")
    conserve(c)

def t_landlord_resp_bucket_zero():
    harness.set_time(T0)
    c = fresh(); gl.message.sender_address = A
    cid = frozen_case(c)
    harness.PROMPT_FN = verdict("LANDLORD_RESPONSIBILITY", 50, reason="UNPROVEN_CLAIM", pair="NONE")
    r = call(c, C, c.assess_claim, cid, "claim_1")
    assert r.startswith("MALFORMED_VERDICT"), r
    d = json.loads(c.cases[str(cid)])
    assert d["cvs"] == {}
    harness.PROMPT_FN = verdict("LANDLORD_RESPONSIBILITY", 0, reason="UNPROVEN_CLAIM", pair="NONE")
    r = call(c, C, c.assess_claim, cid, "claim_1")
    assert "CLAIM_ASSESSED" in r, r
    conserve(c)

def t_invoices_funded_only():
    harness.set_time(T0)
    c = fresh(); gl.message.sender_address = A
    cid = funded_case(c)
    inv = json.dumps([{"item_ref": "claim_1", "claimed_amount_wei": "1000",
                       "receipt_url": "https://x.test/r.png", "receipt_sha256": sha(RCPT)}])
    expect_err(c, B, c.submit_invoices, cid, inv, code="ONLY_LANDLORD")
    r = call(c, A, c.submit_invoices, cid, inv)
    assert "INVOICES_SUBMITTED" in r, r
    # once the claim schedule opens EVIDENCE, the invoice slot is closed (ambush shut)
    call(c, A, c.submit_lease, cid, LEASE, CLAUSES)
    call(c, A, c.submit_claim_schedule, cid, json.dumps([{"item": "x", "claimed_amount_wei": "1000", "clause_id": "clause_7"}]))
    expect_err(c, A, c.submit_invoices, cid, inv, code="BAD_STATUS")
    conserve(c)

def t_inconclusive_reopen_refiling():
    harness.set_time(T0)
    c = fresh(); gl.message.sender_address = A
    cid = evidence_case(c)
    # landlord uses the single EVIDENCE revision (rev -> 1), cap enforced
    call(c, A, c.submit_lease, cid, LEASE + " v2", CLAUSES)
    d = json.loads(c.cases[str(cid)])
    assert d["ev"]["L"]["lease"]["rev"] == 1
    expect_err(c, A, c.submit_lease, cid, LEASE + " v3", CLAUSES, code="EVIDENCE_LOCKED")
    harness.set_time(T0 + DAY + 1)
    call(c, B, c.freeze_evidence, cid)
    harness.PROMPT_FN = verdict("INCONCLUSIVE", 0, reason="UNPROVEN_CLAIM", pair="NONE")
    call(c, C, c.assess_claim, cid, "claim_1")
    r = call(c, C, c.finalize_assessment, cid)
    assert r.startswith("INCONCLUSIVE"), r
    d = json.loads(c.cases[str(cid)])
    assert d["st"] == "EVIDENCE" and d["ev"]["L"]["lease"]["rev"] == 0   # v1.1: rev reset on re-open
    # re-filing works again after the re-open
    call(c, A, c.submit_lease, cid, LEASE + " v3", CLAUSES)
    d = json.loads(c.cases[str(cid)])
    assert d["ev"]["L"]["lease"]["rev"] == 1
    conserve(c)

def t_ecl_zero_pot_guard():
    harness.set_time(T0)
    c = fresh(); gl.message.sender_address = A
    cid = provisional_case(c)
    harness.set_time(T0 + 2 * DAY + 2)
    call(c, C, c.release_split, cid)
    call(c, B, c.claim_payout, cid)
    # while the tenant's withdrawal is pending, a rejected send lands a fresh
    # credit in the tenant's pot for the same case
    r = call(c, B, c.lock_deposit, cid, value=7 * 10 ** 15)
    assert r.startswith("BAD_STATUS") and c._pot(B, cid) == 7 * 10 ** 15
    call(c, B, c.confirm_withdrawal, cid)
    d = json.loads(c.cases[str(cid)])
    assert d["ecl"]["T"] is False and d["st"] == "SETTLED"   # pot not empty -> not counted claimed
    call(c, A, c.claim_payout, cid); call(c, A, c.confirm_withdrawal, cid)
    d = json.loads(c.cases[str(cid)])
    assert d["st"] == "SETTLED"   # still open: the tenant's extra credit is unclaimed
    call(c, B, c.claim_payout, cid); call(c, B, c.confirm_withdrawal, cid)
    d = json.loads(c.cases[str(cid)])
    assert d["st"] == "CLOSED", d["st"]
    conserve(c)

def t_dust_credit_exact():
    # N-64 flipped (v1.1 ruling): EVERY rejected payable amount credits
    # claimable exactly — 1 wei included; nothing falls to protocol excess.
    harness.set_time(T0)
    c = fresh(); gl.message.sender_address = A
    cid = new_case(c)
    r = call(c, A, c.lock_deposit, cid, value=1)
    assert r.startswith("ESCROW_MISMATCH"), r
    assert c._pot(A, cid) == 1
    r = call(c, C, c.fund_dispute, cid, value=12345)
    assert r.startswith("ONLY_PARTY"), r
    assert c._pot(C, cid) == 12345
    conserve(c)
    cid2 = provisional_case(c)
    before = c._pot(A, cid2)
    r = call(c, A, c.request_appeal, cid2, value=1)
    assert r.startswith("BOND_MISMATCH"), r
    assert c._pot(A, cid2) == before + 1
    conserve(c)

def t_appeal_prefee_edge():
    # v1.1: the losing-party check compares PRE-FEE schedule shares.
    # dep 2e15, deduction 1.02e15 -> tenant share 0.98e15 < landlord 1.02e15:
    # the TENANT is the loser. Post-fee nets (landlord 0.92e15) would flip it.
    harness.set_time(T0)
    c = fresh(); gl.message.sender_address = A
    claims = [{"item": "x", "claimed_amount_wei": "2040000000000000", "clause_id": "clause_7"}]
    cid = provisional_case(c, dep=2 * 10 ** 15, claims=claims, bucket=50)
    d = json.loads(c.cases[str(cid)])
    assert d["vd"]["landlord_wei"] == "1020000000000000", d["vd"]
    r = call(c, A, c.request_appeal, cid, value=BOND)
    assert r.startswith("NOT_LOSING_PARTY"), r   # landlord is NOT the loser pre-fee
    r = call(c, B, c.request_appeal, cid, value=BOND)
    assert "APPEAL_FILED" in r, r                  # tenant IS the loser pre-fee
    conserve(c)

def t_resolve_appeal_pause_gate():
    harness.set_time(T0)
    c = fresh(); gl.message.sender_address = A
    cid = provisional_case(c)
    call(c, A, c.request_appeal, cid, value=BOND)
    call(c, A, c.set_paused, True)
    expect_err(c, C, c.resolve_appeal, cid, code="PROTOCOL_PAUSED")
    call(c, A, c.set_paused, False)
    expect_err(c, C, c.resolve_appeal, cid, code="ASSESSMENT_INCOMPLETE")
    conserve(c)

ALL = [v for k, v in sorted(list(globals().items())) if k.startswith("t_")]
for fn in ALL:
    check(fn.__name__, fn)
print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
for n, e in FAIL:
    print("FAILED:", n, e)
sys.exit(1 if FAIL else 0)
