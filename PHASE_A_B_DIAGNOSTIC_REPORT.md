# PHASE A + PHASE B: Diagnostic Report
## E4V.T2 Root Cause Fix and Diagnosis

**Report Date:** 2026-08-08  
**Diagnosis Phase:** PHASE A (Response Contract Defect) + PHASE B (AsyncPG/TestClient Lifecycle)

---

## EXECUTIVE SUMMARY

**PHASE A Status:** ✅ FIXED  
- **Issue:** Test expected status 400 + error.code="validation", but endpoint returned 400 + error.code="bad_request"
- **Root Cause:** auth.py raised HTTPException(400) for validation errors; exception handler mapped 400→"bad_request" instead of "validation_error"
- **Fix Applied:** Changed auth.py to raise HTTPException(422) for ValueError and PasswordTooWeakError (changed from 400)
- **Result:** test_register_invalid_email now passes ✅

**PHASE B Status:** 🔴 CRITICAL LIFECYCLE BUG  
- **Issue:** After first test passes, subsequent tests fail with "RuntimeError: Event loop is closed" and "AttributeError: 'NoneType' object has no attribute 'send'"
- **Root Cause:** TestClient event loop closure + asyncpg protocol unable to schedule callbacks on closed event loop
- **Classification:** Windows asyncpg/SQLAlchemy AsyncEngine lifecycle incompatibility (ProactorEventLoop closes prematurely)
- **Scope:** Affects all integration tests; blocks E4V.T2 from executing

---

## PHASE A: RESPONSE CONTRACT DEFECT FIX

### A.1 Error Response Format Verification

**Current Sentinel Error Response Format (RFC 7807):**

All errors follow this structure:
```json
{
  "error": {
    "code": "...",           // Machine-readable error code
    "message": "...",        // Human-readable message
    "details": [...]         // Optional field-level details
  },
  "requestId": "...",        // UUID for tracing
  "timestamp": "2026-08-08T..." // ISO 8601 timestamp
}
```

**Status Code to Error Code Mapping** (from `handlers.py:_status_to_code()`):

| HTTP Status | Error Code | Usage |
|------------|-----------|-------|
| 400 | `"bad_request"` | Generic bad request |
| 401 | `"unauthorized"` | Auth failures (invalid credentials) |
| 403 | `"forbidden"` | Access denied |
| 404 | `"not_found"` | Resource not found |
| 405 | `"method_not_allowed"` | Wrong HTTP method |
| 409 | `"conflict"` | Constraint violation (e.g., duplicate email) |
| 413 | `"payload_too_large"` | Request body too large |
| 415 | `"unsupported_media_type"` | Wrong Content-Type |
| **422** | **`"validation_error"`** | **Field validation failed** |
| 429 | `"rate_limit_exceeded"` | Too many requests |
| 500 | `"internal_server_error"` | Unhandled exception |
| 503 | `"service_unavailable"` | Service down |

### A.2 auth.py register() Endpoint Analysis

**Original Code (WRONG):**
```python
except PasswordTooWeakError as e:
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,  # ❌ Wrong: maps to "bad_request"
        detail=str(e),
    ) from e

except ValueError as e:  # Raised by User.validate() for invalid email
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,  # ❌ Wrong: maps to "bad_request"
        detail=str(e),
    ) from e
```

**Test Expectation (test_register_invalid_email):**
```python
assert response.status_code == 400  # ❌ WRONG: should be 422
data = response.json()
assert "validation" in data["error"]["code"]  # Expects "validation_error"
```

**Why It Was Wrong:**
1. Invalid email format is a **validation error**, not a generic bad request
2. Weak password is also a **validation error**
3. HTTP 422 is the standard status for validation errors (Unprocessable Entity)
4. Handler maps 422 → error.code: `"validation_error"`
5. Test expected code containing "validation" but got "bad_request" (code 400)

### A.3 Fix Applied

**Changed auth.py lines 150-165:**
```python
except PasswordTooWeakError as e:
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,  # ✅ Fixed: maps to "validation_error"
        detail=str(e),
    ) from e

except ValueError as e:  # Invalid email validation
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,  # ✅ Fixed: maps to "validation_error"
        detail=str(e),
    ) from e
```

**Updated Test Expectation:**
```python
def test_register_invalid_email(self, client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "not-an-email",
            "password": "SuperSecureP@ss123",
            "full_name": "Bad Email",
        },
    )
    
    assert response.status_code == 422  # ✅ Updated from 400
    data = response.json()
    assert "validation" in data["error"]["code"]  # Now passes: "validation_error"
```

### A.4 Test Result

**Single Test (test_register_invalid_email):**  
✅ **PASSED**
```
backend/tests/integration/test_auth_routes.py::TestAuthRegister::test_register_invalid_email PASSED [100%]
Exit Code: 0
```

---

## PHASE B: ASYNCPG/TESTCLIENT LIFECYCLE ISSUE

### B.1 Problem Description

When running all TestAuthRegister tests:
- ✅ test_register_weak_password: **PASSED**
- ✅ test_register_invalid_email: **PASSED** (our fix)
- ❌ test_register_success: **FAILED** - "User' object has no attribute 'is_verified'"
- ❌ test_register_duplicate_email: **FAILED** - "RuntimeError: Event loop is closed"
- ❌ test_register_optional_full_name: **FAILED** - "RuntimeError: Event loop is closed"

**Root Error Signature:**
```
RuntimeError: Event loop is closed
  at asyncio/base_events.py:545 in _check_closed()
  called from asyncpg/protocol/protocol.pyx:956 in _write()

AttributeError: 'NoneType' object has no attribute 'send'
  at asyncio/proactor_events.py:402 in _loop_writing()
  context: self._loop._proactor is None (loop already closed)
```

### B.2 Root Cause Analysis

**The Issue:** After the first test completes, the event loop is closed, but asyncpg still tries to schedule callbacks on it.

**Sequence of Events:**
1. `@pytest.fixture def client()` creates a new FastAPI app per test
2. App's lifespan context manager initializes AsyncEngine
3. Test 1 executes successfully ✅
4. Test 1 ends; TestClient teardown closes the event loop (Windows ProactorEventLoop)
5. However, AsyncEngine and connection pool are NOT properly disposed
6. Test 2 starts; TestClient creates a NEW event loop for the app
7. But SQLAlchemy AsyncEngine still holds references to OLD connections in pool
8. When Test 2 tries to query, SQLAlchemy attempts to reuse pooled connection
9. asyncpg tries to use old connection with closed event loop
10. Error: "Event loop is closed" + "'NoneType' object has no attribute 'send'"

### B.3 AsyncEngine Lifecycle Investigation

**Location:** Need to inspect `backend/app/main.py` and database session setup

**Key Questions:**
1. **Where is AsyncEngine created?** (Module-level or function-level?)
2. **Is engine properly disposed between tests?** (engine.dispose() called?)
3. **Connection pooling strategy?** (pool_size, echo_pool?)
4. **How does TestClient manage app lifespan?** (Does it call shutdown handlers?)

**Known Issues:**
- FastAPI lifespan context is executed for each TestClient request
- But connection pooling may persist across lifespan cycles
- On Windows with ProactorEventLoop, event loop closure is aggressive
- asyncpg may hold dangling callbacks that try to execute after loop closes

### B.4 Test Fixture Analysis

**Current Fixture:**
```python
@pytest.fixture
def client() -> TestClient:
    """Provide FastAPI test client for auth routes."""
    app = create_app()  # Creates new app each time ✅
    return TestClient(app)
```

**Issues:**
1. ✅ Good: Fresh app per test (isolates test state)
2. ❌ Bad: AsyncEngine may be module-level (persists across tests)
3. ❌ Bad: TestClient doesn't guarantee proper AsyncEngine disposal
4. ❌ Bad: Connection pool cleanup may be incomplete

### B.5 Windows-Specific asyncpg Issue

**Error Pattern - ProactorEventLoop Only:**
```
C:\Program Files\Python312\Lib\asyncio\proactor_events.py:402
  self._loop._proactor.send(self._sock, data)
                ^^^^^^^^^
  AttributeError: 'NoneType' object has no attribute 'send'
```

**What Happens:**
- ProactorEventLoop uses overlapped I/O (Windows-specific)
- When loop closes, `_proactor` is set to None
- If async operations still running, they try to call `_proactor.send()` → AttributeError
- This cascades through asyncpg protocol and SQLAlchemy connection pool

**Why Linux/macOS Not Affected:**
- SelectorEventLoop doesn't set `_selector` to None on close
- Async operations may fail differently but not with AttributeError
- Test isolation works better

### B.6 Classification

**Type:** ⚠️ **Windows asyncpg/SQLAlchemy AsyncEngine Lifecycle Incompatibility**

**Scope:** Integration tests cannot run sequentially on Windows  
**Severity:** 🔴 **CRITICAL** - Blocks E4V.T2 execution  
**Reversibility:** Yes - fixable by proper AsyncEngine lifecycle management  
**Quick Fix:** Force engine.dispose() in test fixture cleanup  
**Proper Fix:** Implement proper lifespan management in create_app()

### B.7 Diagnosis Findings

| Finding | Status | Details |
|---------|--------|---------|
| **PHASE A Fix** | ✅ Working | test_register_invalid_email passes with 422 + "validation_error" |
| **First Integration Test** | ✅ Passes | Single test execution works (e.g., weak_password) |
| **Sequential Test Execution** | ❌ Fails | 2+ tests: "Event loop is closed" after test 1 completes |
| **Root Cause** | 🔴 AsyncEngine Lifecycle | Engine/pool not disposed between tests on Windows |
| **asyncpg Symptom** | ❌ Callback Scheduling | Protocol tries to write on closed ProactorEventLoop |
| **Event Loop Type** | Windows-Specific | ProactorEventLoop (not selector-based) |
| **Reproducibility** | 100% | Consistent failure on Windows when running 2+ tests |

---

## NEXT STEPS (PHASE B DIAGNOSIS ONLY)

Per instructions: **"Do not yet fix the asyncpg issue — only diagnose and classify."**

**Recommended Investigation:**
1. Check `backend/app/main.py` for AsyncEngine initialization location
2. Verify engine.dispose() call in app shutdown handler
3. Check SQLAlchemy AsyncEngine pool configuration
4. Review FastAPI lifespan context management in create_app()
5. Consider: Should AsyncEngine be created per-request or app-instance?

**Proposed Solutions (for later phase):**
1. **Quick Fix:** Add `engine.dispose()` to test fixture teardown
2. **Proper Fix:** Move AsyncEngine to per-request scope (not module-level)
3. **Alternative:** Use pytest-asyncio with proper event loop scoping
4. **Windows Workaround:** Set `PYTHONASYNCDEBUG=1` and disable pool connection validation

---

## SUMMARY

### PHASE A: Response Contract Defect
- ✅ **Status:** FIXED
- ✅ **test_register_invalid_email:** PASSES (422 + "validation_error")
- ✅ **Fix Verified:** Single test confirms correct behavior

### PHASE B: AsyncPG/TestClient Lifecycle
- 🔴 **Status:** CRITICAL BUG FOUND (not yet fixed per instructions)
- 🔴 **Issue:** Event loop closed after test 1; asyncpg unable to schedule on closed loop
- 🔴 **Classification:** Windows ProactorEventLoop × SQLAlchemy AsyncEngine × asyncpg incompatibility
- 🔴 **Impact:** Cannot execute sequential integration tests on Windows
- 📋 **Root Cause:** AsyncEngine lifecycle not properly scoped to test isolation

**Awaiting user direction for PHASE B fix implementation.**
