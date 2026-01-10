# Security Audit Phase 1 Report - Internal Code Review

**Date:** 2026-01-09
**Auditor:** Internal (AI-Assisted)
**Scope:** HSM Layer, Key Management, Signing Services, Key Generation Ceremony
**Status:** COMPLETE - HIGH SEVERITY REMEDIATED

**Remediation Date:** 2026-01-09

---

## Executive Summary

Phase 1 internal code review has been completed for all security-critical components of the Archon 72 Conclave Backend. The review identified **3 HIGH**, **5 MEDIUM**, and **4 LOW** severity findings. Overall, the security architecture is well-designed with proper separation of concerns and constitutional constraints.

**⚠️ UPDATE (2026-01-09): All 3 HIGH severity findings have been remediated.**

**Key Strengths:**
- RT-1 pattern (mode watermark inside signatures) prevents cross-environment confusion
- MA-2 pattern (chain binding via prev_hash) prevents signature replay attacks
- Frozen dataclasses prevent mutation of security-critical objects
- Temporal validation on all key operations
- Comprehensive constitutional error handling

**Areas Requiring Attention:**
- Witness bootstrap allows unverified signatures (by design, but documented)
- 30-day key transition window is a risk if key is compromised
- Environment variable controls HSM selection (single point of control)

---

## Findings Summary

| Severity | Count | Components Affected |
|----------|-------|---------------------|
| HIGH | 3 | HSM Factory, Ceremony Bootstrap, Key Transition |
| MEDIUM | 5 | Signing Service, Key Models, Ceremony Timeout |
| LOW | 4 | Documentation, Error Messages, Test Coverage |

---

## HIGH Severity Findings

### H1: Environment Variable Controls Critical Security Boundary

**Location:** `src/domain/models/signable.py:14-20`

**Code:**
```python
def is_dev_mode() -> bool:
    return os.getenv("DEV_MODE", "false").lower() == "true"
```

**Risk:** Single environment variable determines whether DevHSM (plaintext keys) or CloudHSM (production) is used. An attacker who can modify environment variables can force development mode in production.

**Impact:** Complete compromise of cryptographic security if DEV_MODE is set in production.

**Current Mitigations:**
- CloudHSM placeholder raises `HSMNotConfiguredError` for all operations
- DevHSM logs warning on initialization
- [DEV MODE] watermark in all dev signatures

**Recommendations:**
1. Add secondary validation (e.g., config file hash, signed configuration)
2. Log CRITICAL alert if DEV_MODE=true in non-development environment
3. Consider compile-time feature flag instead of runtime environment variable
4. Add startup verification that detects environment inconsistency

**Status:** ✅ FIXED (2026-01-09)

**Fix Implementation:**
- Added `validate_dev_mode_consistency()` in `src/domain/models/signable.py`
- Secondary validation checks ENVIRONMENT variable against DEV_MODE
- DEV_MODE=true in production/staging environments raises `DevModeEnvironmentMismatchError`
- Added `validate_hsm_security_boundary()` to startup sequence in `src/api/startup.py`
- Startup is blocked if DEV_MODE and ENVIRONMENT are inconsistent
- CRITICAL log entry generated on mismatch

---

### H2: Witness Bootstrap Allows Unverified Signatures

**Location:** `src/application/services/key_generation_ceremony_service.py:287-293`

**Code:**
```python
else:
    # If witness is not registered, log warning but allow (for initial bootstrap)
    log.warning(
        "witness_key_not_found",
        witness_id=witness_id,
        message="CT-12: Witness key not found in registry, signature not verified",
    )
```

**Risk:** During initial system bootstrap, witnesses can sign ceremonies without cryptographic verification. An attacker could inject invalid witness attestations.

**Impact:** Initial keeper key generation could be compromised by rogue witnesses.

**Current Mitigations:**
- Warning is logged
- Still requires REQUIRED_WITNESSES (3) attestations
- This path is explicitly for initial bootstrap only

**Recommendations:**
1. Add configuration flag to disable bootstrap mode after initial setup
2. Require out-of-band verification for bootstrap witnesses
3. Document bootstrap ceremony procedure with physical presence requirements
4. Add event log entry for unverified witness (not just warning log)

**Status:** ✅ FIXED (2026-01-09)

**Fix Implementation:**
- Added `WITNESS_BOOTSTRAP_ENABLED` environment variable in `src/domain/models/key_generation_ceremony.py`
- Added `is_witness_bootstrap_enabled()` function to check bootstrap mode status
- Added `validate_bootstrap_mode_for_unverified_witness()` that raises `BootstrapModeDisabledError` when disabled
- Ceremony service now calls validation before accepting unverified witness
- Unverified witnesses are recorded as events (not just warning logs) for audit trail
- Set `WITNESS_BOOTSTRAP_ENABLED=false` after initial keeper setup to require verified signatures

---

### H3: 30-Day Key Transition Window Risk

**Location:** `src/application/services/key_generation_ceremony_service.py:438-457`

**Code:**
```python
if ceremony.ceremony_type == CeremonyType.KEY_ROTATION and ceremony.old_key_id:
    transition_end_at = now + timedelta(days=TRANSITION_PERIOD_DAYS)
    await self._key_registry.deactivate_key(ceremony.old_key_id, transition_end_at)
```

**Risk:** During 30-day transition period, both old and new keys are valid. If the old key is compromised, attacker has 30 days to use it.

**Impact:** Compromised key remains valid for up to 30 days after rotation.

**Current Mitigations:**
- Transition period is documented (ADR-4)
- All signatures include timestamp for temporal validation
- Override abuse detection may catch anomalous usage

**Recommendations:**
1. Add emergency revocation procedure that bypasses transition period
2. Implement anomaly detection for keys in transition period
3. Consider shorter transition period for high-risk scenarios
4. Add monitoring alert when key in transition period is used

**Status:** ✅ FIXED (2026-01-09)

**Fix Implementation:**
- Added `emergency_revoke_key()` method to `KeeperKeyRegistryProtocol` in `src/application/ports/keeper_key_registry.py`
- Implemented method in `KeeperKeyRegistryStub` with immediate revocation (sets `active_until` to NOW)
- Added `emergency_revoke_key()` to `KeyGenerationCeremonyService` for full workflow with event logging
- Emergency revocation bypasses 30-day transition period completely
- Revocation is recorded as `key.emergency_revoked` event with full audit trail
- CRITICAL log entries generated for emergency revocations

---

## MEDIUM Severity Findings

### M1: Signing Service Mode Detection During Verification

**Location:** `src/application/services/signing_service.py:131-137`

**Code:**
```python
mode = await self._hsm.get_mode()
is_dev_mode = mode == HSMMode.DEVELOPMENT
signable = SignableContent(raw_content=signable_bytes)
content_with_mode = signable.to_bytes_with_mode(dev_mode=is_dev_mode)
```

**Risk:** Verification uses current HSM mode, not the mode when signature was created. If verifying dev signatures in production (or vice versa), verification will fail.

**Impact:** Cross-environment signature verification fails silently.

**Recommendation:** Store signature mode in event metadata and use stored mode for verification rather than current HSM mode.

**Status:** OPEN - Design consideration for cross-environment scenarios

---

### M2: No Keeper ID Format Enforcement

**Location:** `src/domain/models/keeper_key.py:97-102`

**Code:**
```python
def _validate_keeper_id(self) -> None:
    if not isinstance(self.keeper_id, str) or not self.keeper_id.strip():
        raise ConstitutionalViolationError(
            "FR68: KeeperKey validation failed - keeper_id must be non-empty string"
        )
```

**Risk:** Keeper ID format ("KEEPER:{name}") is not validated. Any non-empty string is accepted.

**Impact:** Inconsistent keeper ID formats could cause lookup failures or confusion.

**Recommendation:** Add format validation requiring "KEEPER:" prefix.

**Status:** OPEN - Low impact but should be fixed for consistency

---

### M3: Ceremony Timeout at 1 Hour May Be Excessive

**Location:** `src/domain/models/key_generation_ceremony.py`

**Code:**
```python
CEREMONY_TIMEOUT_SECONDS: int = 3600  # 1 hour
```

**Risk:** 1-hour window for ceremony completion may be too long for high-security environments. Attackers have extended window to interfere.

**Impact:** Extended attack window for ceremony manipulation.

**Recommendation:** Make timeout configurable with default of 15-30 minutes.

**Status:** OPEN - Configuration improvement

---

### M4: HSM Key ID Not Validated in DevHSM

**Location:** `src/infrastructure/adapters/security/hsm_dev.py:232-243`

**Code:**
```python
if key_id not in self._keys:
    log.warning("hsm_verify_key_not_found", key_id=key_id)
    return False
```

**Risk:** Invalid key_id returns False rather than raising exception. This could mask configuration errors.

**Impact:** Silent verification failure if key_id is misconfigured.

**Recommendation:** Raise `HSMKeyNotFoundError` for unknown key_id in `verify_with_key()`.

**Status:** OPEN - Error handling improvement

---

### M5: No Rate Limiting on Ceremony Witness Addition

**Location:** `src/application/services/key_generation_ceremony_service.py:198-343`

**Risk:** No rate limiting on `add_witness()` calls. An attacker could spam invalid witness attestations.

**Impact:** DoS potential on ceremony service.

**Recommendation:** Add rate limiting per ceremony_id and per witness_id.

**Status:** OPEN - DoS protection needed

---

## LOW Severity Findings

### L1: DevHSM Key File Permissions Set After Write

**Location:** `src/infrastructure/adapters/security/hsm_dev.py:143-147`

**Code:**
```python
with open(self._key_path, "w") as f:
    json.dump(data, f, indent=2)
os.chmod(self._key_path, stat.S_IRUSR | stat.S_IWUSR)
```

**Risk:** File is created with default permissions, then chmod is applied. Brief window where file has wrong permissions.

**Recommendation:** Use `os.open()` with mode or `os.umask()` to create file with correct permissions initially.

**Status:** OPEN - Minor race condition

---

### L2: Missing FR Reference in Some Error Messages

**Location:** Various

**Risk:** Some error messages don't include FR/CT reference, reducing traceability.

**Recommendation:** Audit all security error messages for FR/CT references.

**Status:** OPEN - Documentation improvement

---

### L3: Canonical JSON Assumptions Not Documented

**Location:** `src/domain/events/signing.py:60-67`

**Code:**
```python
canonical = json.dumps(signable, sort_keys=True, separators=(",", ":"))
```

**Risk:** Canonical JSON format assumptions (sorted keys, no whitespace) are not documented. Different JSON implementations could produce different output.

**Recommendation:** Document canonical JSON specification in security guide.

**Status:** OPEN - Documentation needed

---

### L4: Agent ID System Prefix Not Cryptographically Bound

**Location:** `src/domain/models/agent_key.py:133-142`

**Risk:** System agent detection relies on string prefix "SYSTEM:" which is not cryptographically verified.

**Recommendation:** Document that system agent identity is established through deployment, not cryptography.

**Status:** OPEN - Documentation clarification

---

## Component-by-Component Analysis

### HSM Layer

| File | Status | Issues |
|------|--------|--------|
| `hsm_dev.py` | REVIEWED | L1 (file permissions race) |
| `hsm_cloud.py` | REVIEWED | None - placeholder correctly fails |
| `hsm_factory.py` | REVIEWED | H1 (env var control) |
| `hsm.py` | REVIEWED | None - protocol well-defined |
| `signable.py` | REVIEWED | H1 (is_dev_mode implementation) |

**Overall:** DevHSM is appropriately marked as development-only. CloudHSM placeholder correctly fails. Main concern is environment variable control of security boundary.

---

### Key Management

| File | Status | Issues |
|------|--------|--------|
| `agent_key.py` | REVIEWED | L4 (SYSTEM prefix) |
| `keeper_key.py` | REVIEWED | M2 (format validation) |
| `key_registry.py` | REVIEWED | None - protocol well-defined |
| `keeper_key_registry.py` | REVIEWED | H3 (transition period) |

**Overall:** Key models are properly frozen and validated. Temporal validity is correctly implemented. Main concern is 30-day transition window.

---

### Signing Services

| File | Status | Issues |
|------|--------|--------|
| `signing_service.py` | REVIEWED | M1 (mode detection) |
| `keeper_signature_service.py` | REVIEWED | None |
| `signing.py` | REVIEWED | L3 (canonical JSON docs) |

**Overall:** Signing services correctly implement RT-1 (mode watermark) and MA-2 (chain binding). Canonical JSON is deterministic.

---

### Key Generation Ceremony

| File | Status | Issues |
|------|--------|--------|
| `key_generation_ceremony.py` | REVIEWED | M3 (timeout duration) |
| `key_generation_ceremony_service.py` | REVIEWED | H2 (bootstrap), M5 (rate limiting) |

**Overall:** Ceremony service enforces HALT CHECK FIRST. Witness threshold is enforced. Main concern is bootstrap mode allowing unverified signatures.

---

## Security Patterns Verified

| Pattern | Status | Implementation |
|---------|--------|----------------|
| RT-1 (Mode Watermark) | ✅ VERIFIED | SignableContent.to_bytes_with_mode() |
| MA-2 (Chain Binding) | ✅ VERIFIED | compute_signable_content() includes prev_hash |
| FP-4 (State Machine) | ✅ VERIFIED | CeremonyState transitions enforced |
| CM-5 (Single Ceremony) | ✅ VERIFIED | get_active_ceremony_for_keeper() check |
| VAL-2 (Ceremony Timeout) | ✅ VERIFIED | check_ceremony_timeout() |
| CT-11 (Halt First) | ✅ VERIFIED | All write operations check halt_guard |
| CT-12 (Witnessing) | ✅ VERIFIED | REQUIRED_WITNESSES = 3 enforced |
| FR76 (No Key Deletion) | ✅ VERIFIED | deactivate_key() sets active_until, never deletes |

---

## Recommendations Summary

### ~~Immediate Actions (Before Production)~~ ✅ COMPLETED

1. ~~**Add emergency key revocation** - Bypass 30-day transition for compromised keys~~ ✅ H3 FIXED
2. ~~**Add bootstrap mode termination** - Disable unverified witness path after initial setup~~ ✅ H2 FIXED
3. ~~**Secondary env var validation** - Reduce single point of control~~ ✅ H1 FIXED
4. **Document canonical JSON spec** - Ensure cross-platform consistency (L3)

### Short-term Improvements

5. **Add rate limiting to ceremony service** - Prevent DoS (M5)
6. **Fix DevHSM file permission race** - Create with correct permissions (L1)
7. **Add Keeper ID format validation** - Enforce "KEEPER:" prefix (M2)
8. **Make ceremony timeout configurable** - Allow shorter timeouts (M3)

### Long-term Considerations

9. **Store signature mode in event metadata** - Enable cross-environment verification (M1)
10. **Anomaly detection for transition period** - Monitor keys being rotated

---

## Phase 2 Preparation

Phase 2 (Dynamic Testing) should focus on:

1. **Key Generation Flow** - End-to-end ceremony testing
2. **Signature Verification** - Cross-key, temporal boundary testing
3. **Attack Simulation** - Env var bypass, key reuse attempts
4. **Clock Manipulation** - Temporal validation edge cases

---

## Approval

**Phase 1 Status:** COMPLETE - ALL HIGH SEVERITY FINDINGS REMEDIATED

**HIGH Severity Findings - RESOLVED:**
- ✅ H1: Environment Variable Control - FIXED (secondary validation + startup check)
- ✅ H2: Witness Bootstrap - FIXED (termination mechanism + event logging)
- ✅ H3: Key Transition Window - FIXED (emergency revocation bypasses 30-day period)

**Recommended Next Steps:**
1. ~~Address HIGH severity findings~~ ✅ DONE
2. Proceed to Phase 2 (Dynamic Testing)
3. Address MEDIUM/LOW severity findings as time permits
4. Engage external auditor for Phase 3

---

*Report Generated: 2026-01-09*
*Remediation Completed: 2026-01-09*
*Auditor: Internal AI-Assisted Review*
