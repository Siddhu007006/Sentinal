# E3.T6 Implementation Guide

**Purpose:** Establish artifact roles and maintain clear separation of concerns during task execution.

---

## Artifact Roles During Implementation

### Requirements.md
**Role:** Business ground truth (read-only during implementation)
- Defines what must be built
- Acceptance criteria for validation
- Never changes during implementation
- Reference: When in doubt about business rules

### Design.md
**Role:** Technical decision repository (read-only during implementation)
- Explains why architectural decisions were made
- Contains all design rationale and trade-off analysis
- Complete reference for design questions
- Reference: When implementing design patterns

### Tasks.md
**Role:** Execution plan (write as you progress)
- Tracks implementation progress
- Records actual implementation approach
- Captures deviations and discoveries
- Reference: Step-by-step coding guide

---

## What Goes Where During Implementation

### Tasks.md — Include During Execution ✅

```
- ✓ Task status updates (In Progress → Completed)
- ✓ Acceptance criteria validation (checklist ☐ → ☑)
- ✓ Implementation deviations ("Chose approach B instead of A because...")
- ✓ Technical discoveries ("Found that constraint Y affects index performance")
- ✓ Code file locations ("Created backend/app/models/analysis.py")
- ✓ Test results ("All unit tests pass: 42/42")
- ✓ Blockers and resolutions ("Circular import resolved with TYPE_CHECKING")
```

### Tasks.md — Avoid During Execution ❌

```
- ✗ Design rationale ("We use selectin because...")
- ✗ Architectural explanations ("The lazy loading strategy is...")
- ✗ Constraint justifications ("Why threat_score is [0.0-1.0]...")
- ✗ Index selectivity calculations ("This index covers 2-5% of rows...")
- ✗ Alternative analysis ("We rejected ENUM because...")
```

### Where Design Rationale Lives

**If implementation raises questions about design:**
1. Reference Design.md §N (specific section)
2. Implementation notes: "Confirmed selectin approach per Design §5.1"
3. Design rationale stays in Design.md

**If implementation discovers a rationale issue:**
1. Document in tasks.md: "Implementation revealed constraint on [X]"
2. Note doesn't change Design.md (that's approved)
3. Flag for post-implementation review or next iteration

---

## Implementation Task Template Usage

Each task in tasks.md has this structure:

```markdown
### Task TN: [Name]

**Objective:** [1-sentence goal]
**Inputs:** [Requirements/Design sections]
**Dependencies:** [Upstream tasks]

**Implementation Steps:**
[Detailed coding procedure]

**Verification Steps:**
[Testing procedure]

**Acceptance Criteria:**
- [ ] Checklist item 1
- [ ] Checklist item 2

**Definition of Done:**
[Readiness for next task]

**Traceability:**
[Links to R1-R10 and Design sections]
```

### During Implementation:

1. **Read** objective, inputs, dependencies
2. **Execute** implementation steps (code)
3. **Run** verification steps (tests)
4. **Check** acceptance criteria (validation)
5. **Update** in tasks.md:
   - Mark task status
   - Check off acceptance criteria
   - Add implementation notes: deviations, discoveries, file locations
   - Record test results
6. **Move to** next task when Definition of Done is met

---

## Example: Task T5 (Migration Generation)

### What Goes in Tasks.md During Execution

✅ **Good Implementation Note:**
```
**Task T5 Status:** COMPLETED ✓

**Implementation Notes:**
- Migration file created: backend/alembic/versions/20250121_1430_001a_add_analyses_table.py
- All 18 columns present in upgrade() ✓
- All 5 CHECK constraints present ✓
- All 8 indexes present ✓
- Syntax check passed: python -m py_compile
- Deviation: Indexes created in dependency order (PK first) as per Design §6

**Test Results:**
- pytest backend/tests/unit/test_analysis_model.py: 42/42 PASSED ✓
- Coverage: 95% (target met)

**Blockers:** None
```

❌ **Avoid in Tasks.md:**
```
The lazy loading strategy uses selectin instead of joined because 
Analyses is projected to reach 10M+ rows. At that scale, JOIN operations 
become expensive. SELECT IN queries are more efficient. This deviates 
from E3.T5 which used joined loading...
```

✅ **Instead, Reference Design:**
```
Confirmed selectin lazy loading approach per Design §5.1. 
Performance profile aligns with design for projected 10M+ row scale.
```

---

## During Implementation: How to Handle Questions

### "Why did we choose selectin over joined?"
- **Answer:** See Design.md §5.1
- **Task note:** "Confirmed selectin per Design §5.1"

### "Should I add an index on [column]?"
- **Answer:** See Design.md §6.2 (8 indexes specified)
- **Task note:** "Added all 8 indexes per Design §6.2"

### "The constraint validation is failing differently than expected"
- **Answer:** Document in tasks.md
- **Task note:** "Discovered constraint X behaves differently: [description]. Confirmed with Design §7."

### "I found a bug in the design"
- **Answer:** Document discovery in tasks.md, don't modify Design.md
- **Task note:** "Implementation revealed issue with [X]. Recommend review in next iteration."

---

## Handoff: From Tasks to Code Review

When implementation is complete:

**Task status in tasks.md:**
- All 9 tasks marked COMPLETED
- All acceptance criteria checked ☑
- All blockers resolved
- Deviations and discoveries documented

**Code ready for review:**
- ORM model + migration + tests
- Design.md unchanged (business logic reference)
- Requirements.md unchanged (acceptance criteria reference)
- Tasks.md complete with execution notes

**Code reviewer sees:**
- Design.md for "why this was designed this way"
- Requirements.md for acceptance criteria
- Implementation (code) for "how it was built"
- Tasks.md for "what was actually done and any deviations"

---

## Summary: Artifact Roles

| Artifact | Role | During Implementation |
|---|---|---|
| Requirements.md | Business truth | Read-only, reference |
| Design.md | Technical decisions | Read-only, reference |
| Tasks.md | Execution plan | Update status, record progress, note deviations |
| Code/Tests | Implementation | Write, test, commit |

**Keep them focused. Each has a job.**

