# Conclave Vote Update Spike

Date: 2026-01-23

## Context / Problem
A full Conclave run (64 motions) showed a skewed distribution and a suspiciously high number of abstentions from the 9 Kings. The transcript reveals King responses beginning with `Vote: FOR` or `Vote: NAY`, while the stored vote choice in checkpoints was often `abstain`. This is due to a prompt/parser mismatch:

- King system prompts instruct `Vote: FOR|NAY|ABSTAIN`
- Conclave vote parser previously only recognized `AYE|NAY|ABSTAIN`

This caused valid votes to be recorded as abstentions, materially affecting outcomes.

## Last Changes (Already Implemented)
1. **Vote parser accepts synonyms** in `src/application/services/conclave_service.py` (`_parse_vote`).
   - Recognizes `Vote: FOR`, `Vote: NAY`, `Vote: ABSTAIN` and variants.
   - Handles `I VOTE AYE/NAY`, `I ABSTAIN`, and common formatting noise (markdown bullets/quotes).
   - Defaults to `ABSTAIN` if no explicit vote is found.

2. **Unit tests added** in `tests/unit/application/services/test_conclave_service_vote_parsing.py`.
   - Covers King-style `Vote: FOR` and Conclave-style `I VOTE AYE` formats.
   - Ensures unknown text defaults to `ABSTAIN`.

These changes address the prompt/parser mismatch but still rely on heuristic parsing of free-form LLM output.

## New Requirement: Dual LLM Vote Verification
We need to add dual verification for each archon vote using two LLMs:

- **Witness validator**: Archon ID from `WITNESS_ARCHON_ID` (Furcas)
- **Secretary validator**: Archon ID from `SECRETARY_TEXT_ARCHON_ID`

The validation rules:
- Both validators must independently agree on the same vote (AYE/NAY/ABSTAIN).
- If they disagree, re-roll (re-validate) until consensus or a max attempt limit.
- If consensus cannot be reached, emit a witnessed event of non-consensus.
- Only validated votes should be recorded; invalid/uncertain votes should not be treated as valid signals.

## Planned Implementation
### 1. Configuration
- Extend `ConclaveConfig` to include:
  - `vote_validation_archon_ids: list[str]` (expected length 2)
  - `vote_validation_max_attempts: int` (default: 3)

### 2. Environment Variables
- Add `WITNESS_ARCHON_ID` to `.env.example` alongside other role-based overrides.
- Use existing `SECRETARY_TEXT_ARCHON_ID`.

### 3. Vote Validation Flow
In `ConclaveService._get_archon_vote`:
- Invoke the target archon as usual and capture raw vote response.
- If dual validators are configured:
  1. Send the raw response to both validators.
  2. Require strict JSON output:
     ```json
     {"choice": "AYE"}
     ```
  3. Parse JSON deterministically (no regex) and map to `VoteChoice`.
  4. If validators agree, accept that choice as the authoritative vote.
  5. If validators disagree, re-run validation up to `vote_validation_max_attempts`.

### 4. Non-Consensus Handling
- If consensus is not reached after retries:
  - Record a **witnessed event** (`vote_validation_non_consensus`) via `KnightWitnessProtocol`.
  - Return `ABSTAIN` with a reason such as `Vote validation failed` (conservative default).

### 5. Observability / Transcript
- Emit an explicit transcript entry when validation fails (procedural entry, not a vote).
- Log validator disagreement details for audit.

## Notes / Rationale
- Dual LLM validation reduces reliance on fragile string parsing.
- JSON-only validator responses avoid regex-based decisioning.
- A witnessed non-consensus event satisfies governance transparency.
- This design remains compatible with existing vote parsing and can be applied incrementally.

## Files to Change
- `src/application/services/conclave_service.py` (vote validation logic)
- `scripts/run_conclave.py` (load env, configure validators, wire KnightWitness)
- `.env.example` (add `WITNESS_ARCHON_ID`)
- Tests as needed
