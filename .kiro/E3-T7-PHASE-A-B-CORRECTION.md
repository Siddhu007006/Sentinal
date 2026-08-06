# E3.T7 Specification Correction: Phase A/B Split

**Date:** 2026-08-02  
**Status:** ✅ COMPLETE  
**Impact:** Critical — Spec now aligns with actual ORM model availability

---

## Problem Statement

The initial E3.T7 specification referenced **6 repositories** across all entities:
1. User ✅
2. Upload ✅
3. DigitalAsset ✅
4. Analysis ✅
5. Report ❌ (ORM model does NOT exist)
6. RefreshToken ❌ (ORM model does NOT exist)

However, only **4 ORM models** actually exist in `backend/app/models/`:
- `user.py` — User model (exists)
- `upload.py` — Upload model (exists)
- `digital_asset.py` — DigitalAsset model (exists)
- `analysis.py` — Analysis model (exists)
- `report.py` — ❌ Does NOT exist
- `refresh_token.py` — ❌ Does NOT exist

**Root Cause:** Specification was created ahead of ORM implementation reality, creating an impossible requirement: implement repositories for entities whose ORM models don't exist yet.

---

## Verification Performed

✅ Confirmed 4 ORM models exist:
- User: `class User(BaseModel)` with `deleted_at` soft-delete field
- Upload: `class Upload(BaseModel)` 
- DigitalAsset: `class DigitalAsset(BaseModel)` with `deleted_at` soft-delete field
- Analysis: `class Analysis(BaseModel)`

✅ Confirmed soft-delete consistency:
- User has `deleted_at: Mapped[datetime | None]` field
- DigitalAsset has `deleted_at` inherited from BaseModel
- Both implement soft-delete filtering correctly

❌ Confirmed Report ORM model does NOT exist
❌ Confirmed RefreshToken ORM model does NOT exist

---

## Solution: Phase A/B Split

**Phase A (E3.T7) — Ready for immediate implementation:**
- 4 repositories: User, Upload, DigitalAsset, Analysis
- All ORM models exist
- All query requirements defined in requirements.md
- All dependencies satisfied

**Phase B (E3.T8–E3.T9) — Deferred until ORM models created:**
- 2 repositories: Report, RefreshToken
- ORM models will be created in E3.T8–E3.T9
- Repositories will follow identical design patterns
- Will be added using same architecture

---

## Changes Made to Specification Files

### 0. Folder Naming Convention Fix

**Problem:** Folder was named `epic-3-database-foundation-repository-t7` (singular), but existing spec folders follow plural pattern:
- T3: `epic-3-database-foundation-users-t3` (plural)
- T4: `epic-3-database-foundation-uploads-t4` (plural)
- T5: `epic-3-database-foundation-digital-assets-t5` (plural)
- T6: `epic-3-database-foundation-analyses-t6` (plural)
- T7: `epic-3-database-foundation-repository-t7` (❌ singular - breaks convention)

**Solution:** Renamed to `epic-3-database-foundation-repositories-t7` (plural, consistent with existing pattern)

**Files Updated:**
- Folder: `.kiro/specs/epic-3-database-foundation-repository-t7/` → `.kiro/specs/epic-3-database-foundation-repositories-t7/`
- All spec files updated with new Feature Name in Document Information headers
- Impact: Future T8/T9 folders will follow this canonical naming

---

### 1. requirements.md

#### Section 1.1 (Purpose)
- **Added:** "Report and RefreshToken repositories are deferred to E3.T8–E3.T9 when their ORM models are introduced."
- **Impact:** Clarifies scope boundary upfront

#### Section 1.2 (Scope)
- **Changed:** "In Scope: 6 repository interface definitions" → "In Scope (Phase A): 4 repository interface definitions"
- **Added:** "Future Scope (Phase B): Report repository and RefreshToken repository when ORM models created"
- **Impact:** Explicitly separates implementable work from deferred work

#### Section 3 (R1 and R2 Requirements)
- **Changed:** "for all 6 entities" → "for 4 entities with ORM models (User, Upload, DigitalAsset, Analysis)"
- **Impact:** Requirements now match actual ORM availability

#### Section 3 (R4 — Domain-Specific Queries)
- **Changed:** Removed R4.5 (ReportRepository) and R4.6 (RefreshTokenRepository) from Phase A
- **Added:** "Phase B (E3.T8–E3.T9, deferred)" section
- **Impact:** Only 4 concrete repositories required; 2 deferred

#### New Section 4 (Entity Dependency Matrix)
- **Added:** Table showing which repositories are Phase A (ready) vs Phase B (deferred)
- **Impact:** Explicit visibility into what's implementable now vs later

#### Section 5 (Acceptance Criteria Summary)
- **Changed:** "67 Acceptance Criteria (Phase A)" instead of "77 Acceptance Criteria (all)"
- **Added:** "14 Acceptance Criteria (Phase B) — Future" row
- **Impact:** Clear tracking of what's Phase A vs B

#### Section 6 (Definition of Done)
- **Added:** "Report and RefreshToken repositories explicitly deferred to Phase B (E3.T8–E3.T9)"
- **Impact:** Checklist confirms deferred scope

---

### 2. design.md

#### Section 1.2 (Scope)
- **Changed:** "In Scope" → "Phase A (E3.T7) — In Scope:" (for 4 entities)
- **Added:** "Phase B (E3.T8–E3.T9) — Out of Scope for E3.T7:" (for Report, RefreshToken with rationale)
- **Impact:** Clear phase boundaries

#### Section 3.2 (Specific Repository Interfaces)
- **Changed:** "Similar patterns for: UploadRepository, DigitalAssetRepository, ReportRepository, RefreshTokenRepository"
- **To:** "Similar patterns for (Phase A): UploadRepository, DigitalAssetRepository. Future Extension (Phase B — E3.T8–E3.T9, when ORM models created): ReportRepository, RefreshTokenRepository"
- **Impact:** Design document clearly marks deferred repositories

---

### 3. tasks.md

#### Section 2 (Task Dependency Graph)
- **Changed:** Single DAG from T1–T9 with 6 repositories
- **To:** DAG for "Phase A (E3.T7 Scope)" with 4 repositories, then explicit "Phase B DEFERRED to E3.T8–E3.T9: Report & RefreshToken repositories" section
- **Impact:** Visual clarity of what's Phase A vs B

#### Task T3 (Specific Repository Interfaces)
- **Changed:** "Create 6 files" → "Create 4 files (Phase A)"
- **Added:** "Future Phase B (E3.T8–E3.T9) section explaining when Report and RefreshToken will be added
- **Acceptance Criteria:** "4 repository interfaces created (Phase A)" + "Report and RefreshToken explicitly deferred"
- **Impact:** Clear scope for T3

#### Task T7 (Revised)
- **Original:** "Implement Remaining Repositories (Upload, DigitalAsset, Report, RefreshToken)"
- **New:** "Implement Remaining Phase A Repositories (Upload, DigitalAsset)"
- **Changed:** Removed Report and RefreshToken from T7 implementation
- **Added:** "Deferred to Phase B (E3.T8–E3.T9)" section with rationale
- **Acceptance Criteria:** "2 Phase A repository implementations" + "Report and RefreshToken explicitly deferred"
- **Impact:** T7 now implementable with existing ORM models

#### Task T8 (Dependency Injection)
- **Changed:** "Dependency functions created for all 6 repositories" → "all 4 Phase A repositories"
- **Added:** "Phase B repositories (Report, RefreshToken) deferred in dependency configuration"
- **Impact:** DI wiring scope clarified

#### Task T9 (Tests)
- **Changed:** "For each repository" → "For all 4 Phase A repositories"
- **Added:** "Phase B repositories (Report, RefreshToken) noted as deferred"
- **Impact:** Test scope aligns with Phase A

#### Section 5 (Completion Criteria)
- **Changed:** "E3.T7 Complete when" → "E3.T7 Complete when (Phase A)"
- **Added:** "4 Phase A repositories implemented" + "Phase B repositories deferred"
- **Added:** New section "Phase B (Deferred to E3.T8–E3.T9)" with explicit deferral statement
- **Added:** "Next Steps" clarifying E4 can proceed with Phase A, and Phase B will follow when ORM models created
- **Impact:** Clear sign-off on Phase A as complete, Phase B as scheduled

---

## Impact Summary

| Metric | Before | After | Status |
|---|---|---|---|
| Repositories in scope | 6 | 4 (Phase A) | ✅ Aligned with ORM reality |
| ORM dependency match | 67% (4/6 exist) | 100% (4/4 Phase A exist) | ✅ No blocker |
| Acceptance criteria | 77 (mixed viability) | 67 Phase A + 14 Phase B (clear phases) | ✅ Clear tracking |
| Task count | 9 (all for Phase A only) | 9 (Phase A complete) | ✅ No change |
| Implementation blockers | Yes (Report, RefreshToken ORM missing) | No for Phase A | ✅ Unblocked |
| Deferral clarity | Implicit/assumed | Explicit (Phase B marked throughout) | ✅ Transparent |

---

## Verification Checklist

**Specification Correctness:**
- [x] Folder renamed to follow plural convention: `epic-3-database-foundation-repositories-t7`
- [x] All spec files updated with new Feature Name
- [x] Naming now consistent with T3–T6 (will be consistent for future T8–T9)
- [x] Report and RefreshToken correctly identified as Phase B (ORM models don't exist)
- [x] Phase A is implementable without dependency on Phase B
- [x] Phase B is clearly marked as deferred (not forgotten, scheduled for E3.T8–E3.T9)

**User and DigitalAsset Soft-Delete Consistency:**
- [x] User model has `deleted_at: Mapped[datetime | None]` field
- [x] DigitalAsset model has `deleted_at` inherited from BaseModel
- [x] Both have correct soft-delete field definitions
- [x] Design documents mention soft-delete filtering for both

**Design Patterns Preserved:**
- [x] All Phase A repositories follow identical architecture
- [x] Phase B will use same patterns when created
- [x] No architectural debt introduced

**Documentation Consistency:**
- [x] requirements.md clearly marks Phase A/B
- [x] design.md clearly marks Phase A/B
- [x] tasks.md clearly marks Phase A/B
- [x] All acceptance criteria updated
- [x] All section references updated

---

## Files Updated

1. `.kiro/specs/epic-3-database-foundation-repositories-t7/requirements.md` — 4 sections updated + Feature Name fixed
2. `.kiro/specs/epic-3-database-foundation-repositories-t7/design.md` — 2 sections updated + Feature Name fixed
3. `.kiro/specs/epic-3-database-foundation-repositories-t7/tasks.md` — 7 sections updated + Feature Name fixed
4. **Folder renamed:** `epic-3-database-foundation-repository-t7/` → `epic-3-database-foundation-repositories-t7/`

---

## Next Steps

**Immediate (E3.T7 Implementation):**
1. ✅ Specification corrected and ready
2. ⏳ Begin implementation with Phase A (4 repositories)
3. ⏳ Complete all 9 tasks for Phase A
4. ⏳ Ready for E4 (API endpoints)

**Future (E3.T8–E3.T9):**
1. When Report ORM model created → Create ReportRepository (same patterns)
2. When RefreshToken ORM model created → Create RefreshTokenRepository (same patterns)
3. Both repositories will follow E3.T7 design patterns exactly
4. Add Phase B repositories to dependency injection when ready

---

## Sign-Off

**Correction Status:** ✅ COMPLETE AND VERIFIED

The E3.T7 specification now accurately reflects the current state of the codebase and is ready for implementation with zero blockers.

**Specification Sections Updated:**
- Requirements: Phase A/B split with dependency matrix
- Design: Phase A/B split with deferred extension points
- Tasks: All 9 Phase A tasks correctly scoped and verified

**Implementability:**
- Phase A: ✅ Ready (all ORM models exist)
- Phase B: 📅 Scheduled (deferred until ORM models created in E3.T8–E3.T9)

