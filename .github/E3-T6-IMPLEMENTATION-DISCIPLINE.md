# E3.T6 Implementation Discipline

**Purpose:** Establish clear protocols for task execution, quality gates, and handling discoveries during implementation.

---

## Task Execution Protocol

### Sequential Task Flow (No Skipping)

```
START
  ↓
T1: AnalysisStatus Enum
  ├─ Execute implementation steps
  ├─ Run verification steps
  ├─ Validate acceptance criteria (all ☑)
  └─ Only proceed if Definition of Done met
  ↓
T2: Analysis ORM Model
  ├─ Execute implementation steps
  ├─ Run verification steps
  ├─ Validate acceptance criteria (all ☑)
  └─ Only proceed if Definition of Done met
  ↓
[Continue T3 → T4 → T5 → T6 → T7 → T8 → T9]
  ↓
T9: Final Validation & Audit
  ├─ All tests pass (100%)
  ├─ Code coverage > 95%
  ├─ Linting: No errors
  ├─ Type checking: No errors
  ├─ Audit document created
  └─ Ready for code review
  ↓
COMPLETE
```

### No Shortcuts

| Temptation | Response |
|---|---|
| "Can I skip verification and go to T2?" | NO. Verify T1 first. Acceptance criteria are gates. |
| "Can I do T7 (tests) before T5 (migration)?" | NO. Follow dependency chain. Tests depend on migration. |
| "Can I start T6 (migration review) before T5?" | NO. Migration must be generated first. |
| "Can I refactor T3 code before moving to T4?" | YES, but only code issues. Architectural issues → stop. |

---

## Quality Gates (Non-Negotiable)

### T1 → T2 Gate

Before starting T2, verify T1 completely:
- [ ] AnalysisStatus enum defined with all 5 members
- [ ] All member values lowercase strings (pending, running, completed, failed, cancelled)
- [ ] Docstring explains lifecycle
- [ ] No import errors
- [ ] No linting errors
- [ ] No type errors

**If any gate fails:** Fix T1 before proceeding. Do not work on T2.

### T5 → T6 Gate (Migration Review)

**Before manual review, verify migration is generated:**
- [ ] Migration file created: `backend/alembic/versions/YYYYMMDD_HHMM_*.py`
- [ ] File syntax valid: `python -m py_compile <file>`
- [ ] upgrade() function contains all operations
- [ ] downgrade() function reverses all operations

**If migration fails to generate or has syntax errors:** Fix T5 before proceeding to T6.

### T6 Gate: 24-Point Checkpoint Review

**T6 is a quality gate, not a formality.** Every checkpoint must pass:

| Checkpoint | Pass/Concern |
|---|---|
| 1. Migration ID unique | Must pass |
| 2. Docstring present | Must pass |
| 3. Revision metadata | Must pass |
| ... (all 24 checkpoints) | Must pass |
| 24. Indexes present | Must pass |

**If any checkpoint fails or has concerns:** Document concern, fix migration (T5), regenerate, re-review. Do not proceed to T7 until all checkpoints pass.

### T8 → T9 Gate (All Tests Pass)

Before final validation, verify all tests:
- [ ] Unit tests: 100% pass rate
- [ ] Integration tests: 100% pass rate
- [ ] Migration tests: 100% pass rate
- [ ] Constraint tests: 100% pass rate
- [ ] Performance tests: 100% pass rate
- [ ] Code coverage: > 95%
- [ ] Linting (ruff): No errors
- [ ] Type checking (mypy): No errors

**If any test fails:** Fix code or tests (T7 or T8), re-run. Do not proceed to T9 until all pass.

### T9 Final Gate (Audit Complete)

Before marking E3.T6 complete:
- [ ] All 9 tasks executed
- [ ] All acceptance criteria verified (all ☑)
- [ ] All tests passing (100%)
- [ ] Code coverage: > 95%
- [ ] No linting errors
- [ ] No type errors
- [ ] Audit document generated and signed off
- [ ] Traceability matrix complete (R1–R10 → implementation)

**If audit fails:** Address issues, re-run tests, update audit. Do not mark complete until all gates pass.

---

## Classification Protocol for Discoveries

During implementation, you may discover issues. **Classify them immediately:**

### Category 1: Implementation Issue

**What it is:** Bug in your code, test, or immediate task.

**Examples:**
- Import error in T2 ORM model
- Column type mismatch
- Test assertion failing
- Linting warning

**Response:** Fix in code immediately. Do not block task completion.

**Documentation:** Record in tasks.md as implementation note: "Fixed [issue]: [solution]"

---

### Category 2: Specification Typo or Inconsistency

**What it is:** Minor error in requirements.md, design.md, or tasks.md. Does not affect architecture.

**Examples:**
- Column name spelled wrong in design (e.g., "analyzser_key" vs "analyzer_key")
- Index name typo in design
- Acceptance criterion wording unclear
- Traceability matrix has broken reference

**Response:** 
1. Record in tasks.md: "Found typo in Design §3: [description]"
2. Complete current task (do not stop work)
3. After current task completes: Fix specification, note fix in tasks.md
4. Continue with next task

**Do NOT:** Try to fix specifications during implementation. Note and defer.

---

### Category 3: Architectural Flaw

**What it is:** Significant issue with design that affects implementation correctness or quality.

**Examples:**
- Lazy loading strategy is causing N+1 query problem
- Constraint validation prevents legitimate use cases
- Index selectivity calculation is wrong
- Relationship cardinality doesn't match domain model
- Partial unique index condition is incorrect

**Response:** 
1. **STOP immediately.** Do not continue current task.
2. Document in tasks.md: "Architectural issue discovered: [description]"
3. Reference the design section affected (e.g., Design §5)
4. Propose remediation
5. Explicitly **revise Design.md** with user before continuing
6. Update tasks.md with decision: "Design §N revised per [reason]"
7. Resume implementation with updated design

**Why STOP:** Architectural issues compound downstream. Fixing late is more expensive than fixing now.

---

## Decision Tree

When you discover something unexpected:

```
Is it a problem with YOUR code?
├─ YES → Implementation Issue (Category 1)
│  └─ Fix immediately, note in tasks.md, continue
│
└─ NO. Is it a minor error in the specifications?
   ├─ YES → Specification Typo (Category 2)
   │  └─ Note in tasks.md, fix after current task, continue
   │
   └─ NO. Is it a fundamental architecture issue?
      ├─ YES → Architectural Flaw (Category 3)
      │  └─ STOP. Document. Revise Design. Get approval. Resume.
      │
      └─ UNCLEAR?
         └─ ASSUME Category 3. STOP. Document. Discuss.
```

---

## Example Scenarios

### Scenario 1: Import Error in T2

**Discovery:** `ImportError: cannot import name 'AnalysisStatus'` in T2

**Classification:** Implementation Issue (Category 1)

**Response:**
```
1. Check import path in T2
2. Verify T1 created file correctly
3. Fix import in T2
4. Re-run test
5. Record in tasks.md: "Fixed import path: changed 'from app.model' to 'from app.models'"
6. Continue T2
```

---

### Scenario 2: Column Name Typo in Design

**Discovery:** During T2, you notice Design §3 has typo: "analyser_key" (Design has 's', should be 'z')

**Classification:** Specification Typo (Category 2)

**Response:**
```
1. Note in tasks.md: "Found typo in Design §3: 'analyser_key' should be 'analyzer_key'"
2. Continue T2 with correct name (analyzer_key)
3. After T2 completes: Correct Design §3 and Design §6.2
4. Record fix in tasks.md: "Corrected Design §3 typo"
5. Continue to T3
```

---

### Scenario 3: Lazy Loading Causes N+1 Problem

**Discovery:** During T8 integration tests, you find lazy="selectin" causes N+1 queries in worker polling pattern

**Classification:** Architectural Flaw (Category 3)

**Response:**
```
1. STOP. Do not continue T8.
2. Document in tasks.md: "Architectural issue in T8: lazy='selectin' causes N+1 in worker polls (Design §5)"
3. Create analysis: "Pattern: SELECT analyses, then for each, SELECT digital_asset separately"
4. Propose fix: "Revise to lazy='joined' for worker polling, use explicit selectin() in dashboard"
5. REQUEST DESIGN REVISION
6. Update Design §5 (with approval)
7. Update T3 implementation if needed
8. Re-run T8 tests
9. Resume and complete T8
```

---

## Discipline Rules

### During Implementation

1. ✅ **Fix implementation bugs immediately** (don't block progress)
2. ✅ **Note specification typos** (defer correction to end of task)
3. ❌ **Don't continuously "improve" the design** (stay focused on task)
4. ❌ **Don't skip verification gates** (gates exist for a reason)
5. ✅ **STOP for architectural flaws** (fix before continuing)

### Before Proceeding to Next Task

- [ ] Current task acceptance criteria all ☑
- [ ] Definition of Done met
- [ ] No Category 3 (Architectural) issues outstanding
- [ ] All tests passing for current task
- [ ] No new linting errors introduced

### Before Final Completion (T9)

- [ ] All 9 tasks executed sequentially
- [ ] All acceptance criteria verified
- [ ] All tests passing (100%)
- [ ] Code coverage > 95%
- [ ] No linting or type errors
- [ ] Audit document complete
- [ ] Traceability matrix verified
- [ ] Category 2 (typo) issues fixed
- [ ] No outstanding Category 3 (architectural) issues

---

## Tasks.md Update Protocol

### For Each Task, Record:

**Task Status:**
```
### Task TN: [Name]
**Status:** [Not Started | In Progress | Completed]
**Started:** YYYY-MM-DD
**Completed:** YYYY-MM-DD
```

**Acceptance Criteria:**
```
- [x] Criterion 1 (completed)
- [x] Criterion 2 (completed)
- [ ] Criterion 3 (not started)
```

**Implementation Notes:**
```
**Implementation Notes:**
- Followed implementation steps 1–5 as documented
- File created: backend/app/models/analysis.py
- All tests pass: 42/42 unit tests
- Coverage: 95% (target met)
- No deviations from design
```

**Discoveries:**
```
**Discoveries:**
- Issue: [Category 1 fix OR Category 2 typo note OR Category 3 architecture stop]
- Fix: [Description]
- Status: [Fixed | Noted for later | Requires design revision]
```

---

## Code Review Readiness

At T9, code is ready for review only when:

- ✅ **All 9 tasks completed** (sequential, no skips)
- ✅ **All acceptance criteria verified** (100%)
- ✅ **All quality gates passed** (tests, linting, types)
- ✅ **Audit document complete** (signed off)
- ✅ **No outstanding discoveries** (Category 3 resolved, Category 2 corrected)

---

## Summary: Implementation Discipline

| Principle | Application |
|---|---|
| **Sequential execution** | Follow T1 → T2 → ... → T9. No skipping. |
| **Quality gates are real** | Don't proceed without passing current task gate. |
| **Manual review is serious** | T6 checkpoint review is a quality gate, not a formality. |
| **Fix code immediately** | Implementation issues block progress (Category 1). |
| **Note typos, defer correction** | Specification typos don't block (Category 2). Fix later. |
| **Stop for architecture** | Architectural flaws require design revision (Category 3). |
| **Keep tasks.md current** | Update status, record discoveries, note fixes. |
| **Don't improve continuously** | Stay focused. Flag improvements, fix after task. |

**Goal:** Deliver a correct, well-tested Analysis ORM model and migration on schedule, with clear audit trail of decisions and discoveries.

