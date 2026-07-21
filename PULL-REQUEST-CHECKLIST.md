# How to Check if a Pull Request is Completed

## Overview

A pull request (PR) has multiple stages. Here's how to check the status at each stage.

---

## 1️⃣ **Check PR Status — Overview**

### Location on GitHub
1. Go to your repository: `https://github.com/Siddhu007006/sentinal`
2. Click **Pull requests** tab (top menu)
3. Find your PR in the list

### Quick Status Indicators

| Icon/Badge | Meaning |
|---|---|
| 🟢 Green checkmark | All checks passed ✅ |
| 🔴 Red X | At least one check failed ❌ |
| 🟡 Yellow circle | Checks still running ⏳ |
| 📝 Draft | PR is in draft mode (not ready) |

---

## 2️⃣ **Check Individual Checks**

### View Individual Job Status

1. Click on your PR title to open it
2. Scroll down to **Checks** section (near bottom)
3. You'll see each job status:

```
Checks (4/4 passed) ✅
├─ lint ........................... ✅ PASSED (2m 30s)
├─ type-check .................... ✅ PASSED (3m 15s)
├─ test ........................... ✅ PASSED (4m 50s)
└─ build-verification ............ ✅ PASSED (1m 45s)
```

### Click on Individual Check

1. Click on any job name (e.g., "lint")
2. View detailed output:
   - Console logs
   - Pass/fail reason
   - Step-by-step execution

---

## 3️⃣ **Check CI Workflow Status**

### From PR Page

1. Open the PR
2. Look for the **"Checks"** section
3. Click **"Show all checks"** if hidden
4. You'll see:
   - Status badge
   - Job names
   - Duration
   - Pass/fail symbol

### From Actions Tab (More Detailed)

1. Go to **Actions** tab in your repository
2. Find the workflow run for your PR
3. Click on it to see:
   - All jobs and their status
   - Detailed logs for each job
   - Time taken for each step

---

## 4️⃣ **What "Completed" Means**

### ✅ **COMPLETED (All Good)**

A PR is **completed** when:

1. ✅ **All CI Checks Pass**
   - lint job: ✅ PASSED
   - type-check job: ✅ PASSED
   - test job: ✅ PASSED
   - build-verification job: ✅ PASSED

2. ✅ **All Required Approvals**
   - Code reviews approved (if required)
   - All conversations resolved

3. ✅ **Ready to Merge**
   - Green "Merge pull request" button available
   - No conflicts with base branch

### 🔴 **FAILED (Not Completed)**

A PR is **not completed** if:

1. ❌ **Any CI Check Failed**
   - At least one job shows ❌ FAILED
   - Red X badge on PR

2. ❌ **Pending Reviews**
   - Waiting for approvals
   - Reviewers haven't reviewed yet

3. ❌ **Merge Conflicts**
   - Can't merge due to conflicts
   - Yellow warning appears

---

## 5️⃣ **Status Checks Explained**

### For E3.T6 PR:

#### **Lint Job** (Ruff)
- **What it checks:** Code formatting and style
- **Passes when:** Ruff finds 0 issues
- **Expected time:** ~2-3 minutes

#### **Type-Check Job** (MyPy)
- **What it checks:** Type annotations and static typing
- **Passes when:** MyPy finds 0 errors
- **Expected time:** ~3-4 minutes

#### **Test Job** (Pytest)
- **What it checks:** Unit tests and integration tests
- **Passes when:** All tests pass and coverage > 95%
- **Expected time:** ~4-6 minutes (includes DB setup)

#### **Build-Verification Job**
- **What it checks:** Project structure, imports, dependencies
- **Passes when:** App factory works, no import errors
- **Expected time:** ~1-2 minutes

---

## 6️⃣ **Real-Time Monitoring**

### Option 1: GitHub Web Interface

1. Open PR page
2. Scroll to **Checks** section
3. **Refresh the page** to see live updates
4. Watch the progress:
   - ⏳ Running → ✅ Passed / ❌ Failed

### Option 2: GitHub CLI (Command Line)

Install GitHub CLI: https://cli.github.com/

```bash
# Check PR status
gh pr view feature/e3-t6-analyses-orm-model

# Check specific PR checks
gh pr view feature/e3-t6-analyses-orm-model --json=checks

# List all PRs and their status
gh pr list
```

### Option 3: Watch GitHub Actions

1. Go to **Actions** tab
2. Find the workflow run for your PR
3. Click to expand and watch live
4. Each step will show real-time output

---

## 7️⃣ **Complete Checklist**

### Before Merging - Verify:

- [ ] ✅ All 4 CI jobs passed (lint, type-check, test, build-verification)
- [ ] ✅ Code reviews approved
- [ ] ✅ No merge conflicts
- [ ] ✅ All conversations resolved
- [ ] ✅ Branch is up to date with main
- [ ] ✅ No failing status checks

### After Checks Pass:

1. Click **"Merge pull request"** button (green)
2. Confirm merge
3. Delete branch (optional)
4. PR will show ✅ **Merged** badge

---

## 8️⃣ **Example: E3.T6 PR Status**

### What You'll See When Complete:

```
Pull Request: feat(analysis): implement Analysis ORM model, migration, and test suite

Status: ✅ READY TO MERGE (All checks passed)

Checks (4/4 passed) ✅
├─ lint
│  └─ All files formatted correctly
│     ✅ ruff check passed (0 issues)
│     ✅ ruff format check passed
│
├─ type-check
│  └─ All type hints validated
│     ✅ mypy strict check passed (0 errors)
│
├─ test
│  └─ All tests passed
│     ✅ 103 unit tests passed
│     ✅ Code coverage: 100%
│     ✅ Database migration tested
│
└─ build-verification
   └─ Project structure verified
      ✅ App factory verified
      ✅ Settings verified
      ✅ Dependencies verified

Merge Status:
✅ No conflicts with base branch
✅ All required checks passed
✅ Ready to merge to main
```

---

## 9️⃣ **Troubleshooting**

### If Checks Are Failing:

1. **Click on the failed job**
   - View detailed error logs
   - Identify what went wrong

2. **Common Issues:**
   - **Lint failed:** Run `ruff check app` locally, fix issues
   - **Type-check failed:** Run `mypy app --strict` locally
   - **Tests failed:** Run `pytest tests/` locally, debug
   - **Build failed:** Check import errors, dependencies

3. **Fix Locally**
   - Make corrections
   - Commit and push
   - PR will automatically re-run checks

### If Checks Are Stuck:

1. Go to **Actions** tab
2. Find the stuck workflow
3. Click **"Re-run all jobs"** button
4. Wait for workflow to complete

---

## 🔟 **Quick Reference Links**

### For Your Repository:

- **PRs:** `https://github.com/Siddhu007006/sentinal/pulls`
- **Actions:** `https://github.com/Siddhu007006/sentinal/actions`
- **Specific PR:** `https://github.com/Siddhu007006/sentinal/pull/1` (replace 1 with PR number)

### Key Commands (GitHub CLI):

```bash
# List all pull requests
gh pr list

# View specific PR status
gh pr view <branch-name>

# View PR checks status
gh pr view <branch-name> --json=statusCheckRollup

# Check workflow status
gh run list --repo Siddhu007006/sentinal

# View specific run details
gh run view <run-id> --repo Siddhu007006/sentinal
```

---

## ✅ **Summary**

| What to Check | Where | Status |
|---|---|---|
| **All Checks Passed?** | PR page → Checks section | 🟢 Green = Complete |
| **Specific Job Status?** | Click on job name | See detailed logs |
| **Live Progress?** | Actions tab | Watch real-time |
| **Ready to Merge?** | Green "Merge PR" button | Click when all ✅ |
| **After Merge** | PR shows "Merged" badge | Complete! 🎉 |

---

## 🎯 **For Your E3.T6 PR:**

Once you push to GitHub:

1. Go to `https://github.com/Siddhu007006/sentinal/pulls`
2. Find `feat(analysis): implement Analysis ORM model...`
3. Click it to open
4. **Wait for checks to complete** (~10-15 minutes total)
5. When all 4 jobs show ✅ **PASSED**
6. Click **"Merge pull request"** button
7. Confirm merge
8. **PR is now COMPLETED** ✅

That's it! 🎉
