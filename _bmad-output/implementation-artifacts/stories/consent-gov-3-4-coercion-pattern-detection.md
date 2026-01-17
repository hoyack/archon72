# Story consent-gov-3.4: Coercion Pattern Detection

Status: done

---

## Story

As a **governance system**,
I want **detection of coercive language patterns**,
So that **manipulative content is identified and handled appropriately**.

---

## Acceptance Criteria

1. **AC1:** Detection of urgency pressure ("act now", "limited time", "URGENT")
2. **AC2:** Detection of guilt induction ("you owe", "disappointing", "let down")
3. **AC3:** Detection of false scarcity ("only X left", "exclusive", "last chance")
4. **AC4:** Detection of engagement-optimization language
5. **AC5:** Pattern library versioned and auditable
6. **AC6:** Patterns categorized by severity (transform, reject, block)
7. **AC7:** Pattern matching is deterministic and fast
8. **AC8:** Pattern library loadable from configuration
9. **AC9:** Unit tests for each pattern category

---

## Tasks / Subtasks

- [x] **Task 1: Create PatternLibraryPort interface** (AC: 5, 8)
  - [x] Create `src/application/ports/governance/pattern_library_port.py`
  - [x] Define `get_current_version()` method
  - [x] Define `get_blocking_patterns()` method
  - [x] Define `get_rejection_patterns()` method
  - [x] Define `get_transformation_rules()` method

- [x] **Task 2: Create CoercionPattern domain model** (AC: 6)
  - [x] Create `src/domain/governance/filter/coercion_pattern.py`
  - [x] Define `PatternSeverity` enum (TRANSFORM, REJECT, BLOCK)
  - [x] Define `CoercionPattern` value object
  - [x] Include pattern ID, regex, severity, category

- [x] **Task 3: Implement urgency pressure patterns** (AC: 1)
  - [x] "URGENT", "ASAP", "immediately", "right now"
  - [x] "limited time", "expires", "deadline approaching"
  - [x] "act now", "don't delay", "hurry"
  - [x] Caps-lock emphasis detection
  - [x] Severity: mostly TRANSFORM or REJECT

- [x] **Task 4: Implement guilt induction patterns** (AC: 2)
  - [x] "you owe", "you promised", "you said"
  - [x] "disappointing", "let down", "expected more"
  - [x] "after everything", "how could you"
  - [x] Severity: mostly REJECT

- [x] **Task 5: Implement false scarcity patterns** (AC: 3)
  - [x] "only X left", "limited availability"
  - [x] "exclusive", "special offer"
  - [x] "last chance", "won't last"
  - [x] "before it's too late"
  - [x] Severity: mostly REJECT

- [x] **Task 6: Implement engagement-optimization patterns** (AC: 4)
  - [x] Excessive punctuation (!!!, ???)
  - [x] Click-bait language
  - [x] Emotional manipulation
  - [x] Gamification language ("streak", "points", "level up")
  - [x] Severity: TRANSFORM for mild, REJECT for heavy

- [x] **Task 7: Implement hard violation patterns** (AC: 6)
  - [x] Explicit threats
  - [x] Deception patterns
  - [x] Manipulation through false claims
  - [x] Coercion through power imbalance
  - [x] Severity: BLOCK

- [x] **Task 8: Implement pattern library versioning** (AC: 5)
  - [x] Version in semver format
  - [x] Hash of all patterns for verification
  - [x] Version history tracked
  - [x] Changes logged to ledger

- [x] **Task 9: Implement YAML pattern loader** (AC: 8)
  - [x] Create `config/governance/coercion_patterns.yaml`
  - [x] Load patterns at startup
  - [x] Validate pattern syntax
  - [ ] Hot-reload support (future)

- [x] **Task 10: Implement deterministic matching** (AC: 7)
  - [x] Patterns matched in priority order
  - [x] Same input always matches same patterns
  - [x] No probabilistic matching
  - [x] Performance: <50ms for pattern matching

- [x] **Task 11: Write comprehensive unit tests** (AC: 9)
  - [x] Test urgency patterns detected
  - [x] Test guilt patterns detected
  - [x] Test scarcity patterns detected
  - [x] Test engagement-optimization detected
  - [x] Test hard violations blocked
  - [x] Test pattern versioning
  - [x] Test deterministic matching

---

## Documentation Checklist

- [x] Architecture docs updated (pattern library)
- [x] Pattern categories documented
- [x] How to add new patterns documented
- [x] N/A - README (internal component)

---

## File List

### Created
- `src/domain/governance/filter/coercion_pattern.py` - Domain models: PatternSeverity, PatternCategory, CoercionPattern, PatternLibraryVersion
- `src/application/ports/governance/pattern_library_port.py` - Port interface for pattern library
- `src/infrastructure/adapters/governance/yaml_pattern_library_adapter.py` - YAML adapter for loading patterns
- `config/governance/coercion_patterns.yaml` - Pattern library configuration (56 patterns)
- `tests/unit/domain/governance/filter/test_coercion_pattern.py` - Domain model tests (42 tests)
- `tests/unit/infrastructure/adapters/governance/test_yaml_pattern_library_adapter.py` - Adapter tests (23 tests)
- `tests/unit/infrastructure/adapters/governance/test_coercion_pattern_detection.py` - Comprehensive pattern tests (52 tests)

### Modified
- `src/domain/governance/filter/__init__.py` - Added exports for new types
- `src/application/ports/governance/__init__.py` - Added PatternLibraryPort export

---

## Dev Notes

### Key Architectural Decisions

**Pattern Severity Levels:**
```
TRANSFORM (mild):
  - Can be automatically softened
  - E.g., "URGENT" → removed, caps → lowercase
  - Content still sent after transformation

REJECT (moderate):
  - Cannot be automatically fixed
  - Earl must rewrite
  - E.g., guilt induction, false scarcity
  - Content NOT sent until rewritten

BLOCK (severe):
  - Hard violation
  - Cannot be sent under any circumstances
  - E.g., explicit threats, deception
  - Logged as potential governance issue
```

**Anti-Engagement (NFR-UX-01):**
```
The governance system explicitly prohibits engagement-optimization:
  - No "streak" tracking
  - No "points" or gamification
  - No FOMO (fear of missing out) language
  - No dark patterns

The Coercion Filter enforces this by detecting and removing
engagement-optimization language.
```

### Pattern Categories

```yaml
# Pattern categories with examples

urgency_pressure:
  description: "Creates artificial time pressure"
  examples:
    - "URGENT"
    - "Act now"
    - "Limited time"
    - "Expires soon"
    - "Don't delay"
  default_severity: TRANSFORM

guilt_induction:
  description: "Induces guilt or shame"
  examples:
    - "You owe us"
    - "Disappointing"
    - "Let everyone down"
    - "After everything we've done"
  default_severity: REJECT

false_scarcity:
  description: "Creates artificial scarcity"
  examples:
    - "Only X left"
    - "Limited availability"
    - "Exclusive opportunity"
    - "Last chance"
  default_severity: REJECT

engagement_optimization:
  description: "Optimizes for engagement over value"
  examples:
    - "!!!" (excessive punctuation)
    - "You won't believe"
    - "Streak" / "Points" / "Level"
    - "Don't miss out"
  default_severity: TRANSFORM

hard_violations:
  description: "Cannot be transformed or allowed"
  examples:
    - Explicit threats
    - False claims
    - Deceptive statements
    - Harassment
  default_severity: BLOCK
```

### Domain Models

```python
class PatternSeverity(Enum):
    """How severely to treat pattern matches."""
    TRANSFORM = "transform"  # Auto-fix, content can be sent
    REJECT = "reject"        # Requires rewrite
    BLOCK = "block"          # Hard violation


class PatternCategory(Enum):
    """Categories of coercive patterns."""
    URGENCY_PRESSURE = "urgency_pressure"
    GUILT_INDUCTION = "guilt_induction"
    FALSE_SCARCITY = "false_scarcity"
    ENGAGEMENT_OPTIMIZATION = "engagement_optimization"
    HARD_VIOLATION = "hard_violation"


@dataclass(frozen=True)
class CoercionPattern:
    """A pattern for detecting coercive language."""
    id: str
    category: PatternCategory
    severity: PatternSeverity
    pattern: str  # Regex pattern
    description: str
    replacement: str | None = None  # For TRANSFORM severity

    def matches(self, content: str) -> bool:
        """Check if pattern matches content."""
        return bool(re.search(self.pattern, content, re.IGNORECASE))

    def extract_match(self, content: str) -> str | None:
        """Extract the matched text."""
        match = re.search(self.pattern, content, re.IGNORECASE)
        return match.group(0) if match else None

    def apply(self, content: str) -> str:
        """Apply transformation (for TRANSFORM severity)."""
        if self.severity != PatternSeverity.TRANSFORM:
            raise ValueError("Can only apply TRANSFORM patterns")
        return re.sub(self.pattern, self.replacement or "", content, flags=re.IGNORECASE)


@dataclass(frozen=True)
class PatternLibraryVersion:
    """Version information for pattern library."""
    version: str  # semver
    patterns_hash: str  # blake3 hash of all patterns
    loaded_at: datetime
    pattern_count: int
```

### YAML Pattern Configuration

```yaml
# config/governance/coercion_patterns.yaml
version: "1.0.0"

patterns:
  # Urgency Pressure - TRANSFORM
  - id: "urgency_caps_urgent"
    category: "urgency_pressure"
    severity: "transform"
    pattern: "\\bURGENT\\b"
    description: "Caps-lock URGENT creates artificial pressure"
    replacement: ""

  - id: "urgency_act_now"
    category: "urgency_pressure"
    severity: "transform"
    pattern: "\\bact\\s+now\\b"
    description: "Act now creates time pressure"
    replacement: "when convenient"

  - id: "urgency_limited_time"
    category: "urgency_pressure"
    severity: "reject"
    pattern: "\\blimited\\s+time\\b"
    description: "Limited time creates artificial deadline"
    rejection_reason: "urgency_pressure"

  # Guilt Induction - REJECT
  - id: "guilt_you_owe"
    category: "guilt_induction"
    severity: "reject"
    pattern: "\\byou\\s+owe\\b"
    description: "Creates obligation through guilt"
    rejection_reason: "guilt_induction"

  - id: "guilt_disappointing"
    category: "guilt_induction"
    severity: "reject"
    pattern: "\\bdisappoint(ing|ed|ment)?\\b"
    description: "Induces guilt through disappointment"
    rejection_reason: "guilt_induction"

  # False Scarcity - REJECT
  - id: "scarcity_only_x_left"
    category: "false_scarcity"
    severity: "reject"
    pattern: "\\bonly\\s+\\d+\\s+(left|remaining)\\b"
    description: "Creates artificial scarcity"
    rejection_reason: "false_scarcity"

  - id: "scarcity_last_chance"
    category: "false_scarcity"
    severity: "reject"
    pattern: "\\blast\\s+chance\\b"
    description: "Creates FOMO"
    rejection_reason: "false_scarcity"

  # Engagement Optimization - TRANSFORM/REJECT
  - id: "engagement_excessive_punctuation"
    category: "engagement_optimization"
    severity: "transform"
    pattern: "[!?]{3,}"
    description: "Excessive punctuation is engagement bait"
    replacement: "."

  - id: "engagement_streak"
    category: "engagement_optimization"
    severity: "reject"
    pattern: "\\bstreak\\b"
    description: "Streak language is gamification"
    rejection_reason: "engagement_optimization"

  # Hard Violations - BLOCK
  - id: "violation_explicit_threat"
    category: "hard_violation"
    severity: "block"
    pattern: "\\b(hurt|harm|punish|destroy)\\s+(you|your)\\b"
    description: "Explicit threat of harm"
    violation_type: "explicit_threat"

  - id: "violation_or_else"
    category: "hard_violation"
    severity: "block"
    pattern: "\\bor\\s+else\\b"
    description: "Implicit threat"
    violation_type: "coercion"
```

### Pattern Library Adapter

```python
class YamlPatternLibraryAdapter:
    """Loads patterns from YAML configuration."""

    def __init__(self, config_path: Path):
        self._config_path = config_path
        self._patterns: list[CoercionPattern] = []
        self._version: PatternLibraryVersion | None = None

    async def load(self) -> None:
        """Load patterns from YAML file."""
        with open(self._config_path) as f:
            config = yaml.safe_load(f)

        self._patterns = [
            CoercionPattern(
                id=p["id"],
                category=PatternCategory(p["category"]),
                severity=PatternSeverity(p["severity"]),
                pattern=p["pattern"],
                description=p["description"],
                replacement=p.get("replacement"),
            )
            for p in config["patterns"]
        ]

        # Calculate version hash
        patterns_hash = self._calculate_hash()
        self._version = PatternLibraryVersion(
            version=config["version"],
            patterns_hash=patterns_hash,
            loaded_at=datetime.now(),
            pattern_count=len(self._patterns),
        )

    async def get_current_version(self) -> PatternLibraryVersion:
        return self._version

    async def get_blocking_patterns(self) -> list[CoercionPattern]:
        return [p for p in self._patterns if p.severity == PatternSeverity.BLOCK]

    async def get_rejection_patterns(self) -> list[CoercionPattern]:
        return [p for p in self._patterns if p.severity == PatternSeverity.REJECT]

    async def get_transformation_rules(self) -> list[CoercionPattern]:
        return [p for p in self._patterns if p.severity == PatternSeverity.TRANSFORM]
```

### Test Patterns

```python
class TestCoercionPatternDetection:
    """Unit tests for coercion pattern detection."""

    def test_urgency_patterns_detected(self, pattern_library):
        """Urgency pressure patterns are detected."""
        content = "URGENT! Act now before time runs out!"

        patterns = pattern_library.get_transformation_rules()
        matches = [p for p in patterns if p.matches(content)]

        assert len(matches) >= 2  # URGENT and "act now"

    def test_guilt_patterns_detected(self, pattern_library):
        """Guilt induction patterns are detected."""
        content = "You owe it to the team. Don't be disappointing."

        patterns = pattern_library.get_rejection_patterns()
        matches = [p for p in patterns if p.matches(content)]

        assert len(matches) >= 2

    def test_scarcity_patterns_detected(self, pattern_library):
        """False scarcity patterns are detected."""
        content = "Only 3 left! This is your last chance!"

        patterns = pattern_library.get_rejection_patterns()
        matches = [p for p in patterns if p.matches(content)]

        assert len(matches) >= 2

    def test_engagement_optimization_detected(self, pattern_library):
        """Engagement-optimization patterns are detected."""
        content = "Don't break your streak!!! You won't believe this!!!"

        all_patterns = (
            pattern_library.get_transformation_rules() +
            pattern_library.get_rejection_patterns()
        )
        matches = [p for p in all_patterns if p.matches(content)]

        assert len(matches) >= 2

    def test_hard_violations_blocked(self, pattern_library):
        """Hard violations result in BLOCK severity."""
        content = "Do this or else I will hurt you."

        patterns = pattern_library.get_blocking_patterns()
        matches = [p for p in patterns if p.matches(content)]

        assert len(matches) >= 1
        assert all(p.severity == PatternSeverity.BLOCK for p in matches)

    def test_pattern_versioning(self, pattern_library):
        """Pattern library tracks version."""
        version = pattern_library.get_current_version()

        assert version.version is not None
        assert version.patterns_hash is not None
        assert version.pattern_count > 0

    def test_deterministic_matching(self, pattern_library):
        """Same content always matches same patterns."""
        content = "URGENT task for you!"

        matches1 = [
            p for p in pattern_library.get_transformation_rules()
            if p.matches(content)
        ]
        matches2 = [
            p for p in pattern_library.get_transformation_rules()
            if p.matches(content)
        ]

        assert matches1 == matches2

    def test_neutral_content_passes(self, pattern_library):
        """Neutral content matches no patterns."""
        content = "Please review this task when you have time."

        all_patterns = (
            pattern_library.get_blocking_patterns() +
            pattern_library.get_rejection_patterns() +
            pattern_library.get_transformation_rules()
        )
        matches = [p for p in all_patterns if p.matches(content)]

        assert len(matches) == 0
```

### Dependencies

- **Depends on:** consent-gov-3-1 (domain model)
- **Enables:** consent-gov-3-2 (filter service uses pattern library)

### References

- NFR-UX-01: Communications free of engagement-optimization
- Governance architecture: Coercion Filter mandatory path
- Anti-coercion constitutional principle
