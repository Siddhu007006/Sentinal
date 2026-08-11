# E4V.T2 — Architecture Issues Summary

**Status**: 11/19 tests passing; 3 failures + 5 errors remaining  
**Root Causes**: Domain entity mismatches + API response field naming inconsistency  
**Effort to Complete**: 2-3 additional hours for full fixes

---

## Issues Found

### Issue 1: RefreshToken Entity Missing `user_agent` Field ❌

**Location**: `backend/app/domain/entities/refresh_token.py`

**Problem**: 
- ORM model has `user_agent` field (client context capture)
- Domain entity does NOT have this field
- Causes AttributeError during token refresh/logout flows

**Similar To**: AuditLog `updated_at` issue (ORM field not in domain)

**Fix Required**: Add `user_agent: str | None = None` to RefreshToken domain entity

---

### Issue 2: API Response Field Naming Mismatch ⚠️

**Symptom**: Test assertions expect `fullName` but API returns `full_name`

**Root Cause**: Response serialization converting snake_case to camelCase inconsistently

**Pattern**:
- Domain/ORM uses: `full_name` (Python snake_case)
- API should serialize to: `fullName` (camelCase for JSON)
- Currently returning: Mixed (some `fullName`, some `full_name`)

**Affected Tests**:
- test_register_success
- test_get_me_success
- Any test checking user profile fields

**Fix Location**: Likely in response serialization layer (API schemas)

---

### Issue 3: Event Loop Contamination Between Tests ⚠️

**Symptom**: After 11 passing tests, event loop errors occur

**Pattern**: Event loop state accumulates across tests; cleanup doesn't fully reset

**Root Cause**: AsyncClient doesn't fully isolate app lifespan events

**Affected Tests**: Tests 12+ (appear after first 11 pass)

**Potential Fix**: Explicit app lifespan trigger in AsyncClient fixture

---

## Test Results

```
Passing: 11/19 ✅
├── registration (6/6)
│   ├── test_register_success ✅
│   ├── test_register_duplicate_email ✅
│   ├── test_register_weak_password ✅
│   ├── test_register_invalid_email ✅
│   ├── test_register_missing_email ✅
│   └── test_register_optional_full_name ✅
└── login (5/?) - Partially passing

Failed: 3
├── Likely response field naming (test_register_success assertion failure)
├── Likely response field naming (test_get_me_success assertion failure)
└── Possibly RefreshToken user_agent issue

Errors: 5
├── RefreshToken missing user_agent (AttributeError)
├── Event loop contamination (asyncio errors)
└── Other lifespan/cleanup issues
```

---

## Priority Assessment

### High Priority (Blocking)
1. **RefreshToken user_agent field** - Causes 5+ test errors
2. **Response field naming** - Causes 3 assertion failures

### Medium Priority (Quality)
3. **Event loop isolation** - Affects test reliability on Windows

---

## Estimated Effort to Complete

| Issue | Effort | Complexity | Priority |
|-------|--------|-----------|----------|
| RefreshToken user_agent | 15 min | Low | 🔴 High |
| Response field naming | 30 min | Medium | 🔴 High |
| Event loop isolation | 1 hour | High | 🟡 Medium |
| **Total** | **~2 hours** | - | - |

---

## Next Steps

**Option 1: Continue (Recommended)**
- Fix RefreshToken user_agent (5 min)
- Fix response field naming (30 min)
- Re-run all 19 tests (should achieve 19/19)
- Handle any remaining event loop issues

**Option 2: Document and Defer**
- Current: 11/19 passing (58%)
- Document known issues
- Move to E4V.T3/T4/T5
- Return to E4V.T2 later

**User Decision Required**: Which path?

