# E3.T7 Specification Corrections: Phase A/B Split + Naming Convention

**Date:** 2026-08-02  
**Status:** ✅ COMPLETE  
**Impact:** Critical — Spec now aligns with ORM availability AND follows naming convention

---

## Corrections Applied

### 1. Naming Convention Fix

**Problem:** Folder named `epic-3-database-foundation-repository-t7` (singular)

**Existing convention (T3–T6):**
- T3: `epic-3-database-foundation-users-t3` (plural)
- T4: `epic-3-database-foundation-uploads-t4` (plural)
- T5: `epic-3-database-foundation-digital-assets-t5` (plural)
- T6: `epic-3-database-foundation-analyses-t6` (plural)

**Solution:** Renamed to `epic-3-database-foundation-repositories-t7` (plural)

**Files Updated:**
- Folder: `.kiro/specs/epic-3-database-foundation-repositories-t7/`
- All spec files: Feature Name field updated in Document Information headers

**Impact:** Future T8/T9 will follow this canonical plural naming pattern

---

### 2. Phase A/B Alignment Fix

**Problem:** Spec referenced 6 repositories, but only 4 ORM models exist

**ORM Model Status:**
- ✅ User, Upload, DigitalAsset, Analysis (exist)
- ❌ Report, RefreshToken (don't exist)

**Solution:** Phase A/B split with explicit deferral

**Scope Changes:**
- Phase A (E3.T7): 4 repositories (User, Upload, DigitalAsset, Analysis)
- Phase B (E3.T8–E3.T9): 2 repositories (Report, RefreshToken) — deferred until ORM models created

**Files Updated:**
- `requirements.md`: Added Entity Dependency Matrix, reduced AC from 77 to 67 (Phase A only)
- `design.md`: Updated scope to distinguish Phase A (in-scope) vs Phase B (deferred)
- `tasks.md`: Updated DAG, T3, T7, T8, T9 to reflect Phase A/B split

---

## Verification Checklist

**Naming Convention:**
- [x] Folder renamed to: `epic-3-database-foundation-repositories-t7`
- [x] Feature Name in all specs updated to: `epic-3-database-foundation-repositories-t7`
- [x] Consistent with T3–T6 plural pattern
- [x] Future T8/T9 will follow same naming convention

**Phase A/B Alignment:**
- [x] All Phase A repositories (User, Upload, DigitalAsset, Analysis) have ORM models
- [x] Report and RefreshToken correctly identified as Phase B (ORM models don't exist)
- [x] Phase A implementable without Phase B dependency
- [x] Phase B clearly marked as deferred

**Soft-Delete Consistency:**
- [x] User model has `deleted_at` field
- [x] DigitalAsset model has `deleted_at` field
- [x] Both correctly defined and documented

**Documentation:**
- [x] requirements.md: Phase A/B marked, AC summary updated
- [x] design.md: Scope clearly distinguishes Phase A vs Phase B
- [x] tasks.md: DAG, T3, T7, T8, T9 all reflect Phase A/B split
- [x] Feature Name updated in all three files

---

## File Locations

**Specification Folder:** `.kiro/specs/epic-3-database-foundation-repositories-t7/`

**Specification Files:**
- `requirements.md` — 67 Phase A acceptance criteria + Phase B deferred
- `design.md` — Phase A design patterns + Phase B extension points
- `tasks.md` — 9 Phase A tasks + Phase B roadmap

---

## Next Steps

**Ready for Implementation:**
1. ✅ Specification corrected and follows naming convention
2. ⏳ Begin E3.T7 Phase A implementation (4 repositories)
3. ⏳ Complete 9 Phase A tasks
4. ⏳ Proceed to E4 (API endpoints)

**Future Tasks:**
- When Report ORM model created (E3.T8): Create ReportRepository (same patterns)
- When RefreshToken ORM model created (E3.T8): Create RefreshTokenRepository (same patterns)
- Folder naming: `epic-3-database-foundation-*-t8` (plural pattern continues)

---

## Sign-Off

**All Corrections Complete:**
- ✅ Folder naming: `epic-3-database-foundation-repositories-t7` (plural, consistent)
- ✅ Phase A/B split: 4 Phase A repositories + 2 Phase B deferred
- ✅ ORM dependency: Phase A fully implementable with existing models
- ✅ Documentation: All three specs updated and internally consistent

**Status:** E3.T7 is production-ready for Phase A implementation

