"""Verify index count against Design specification."""

from app.models.analysis import Analysis
from sqlalchemy import Table
from typing import cast


table = cast(Table, Analysis.__table__)


print("=" * 70)
print("INDEX VERIFICATION AGAINST DESIGN §6")
print("=" * 70)
indexes = list(table.indexes)
print(f"\n✓ Total indexes exposed by SQLAlchemy: {len(indexes)}")
print("✓ Design specifies: 8 indexes\n")

print("Indexes found in implementation:")
print("-" * 70)
for i, idx in enumerate(indexes, 1):
    is_unique = idx.unique
    is_partial = idx.dialect_options.get("postgresql_where") is not None
    flags = []
    if is_unique:
        flags.append("UNIQUE")
    if is_partial:
        flags.append("PARTIAL")
    flag_str = f" [{', '.join(flags)}]" if flags else ""
    print(f"{i}. {idx.name}{flag_str}")

print("\n" + "-" * 70)
print("Design §6.2 specification:")
print("-" * 70)
design_indexes = [
    ("ix_analyses_asset_status", False, False),
    ("ix_analyses_asset_latest", False, False),
    ("ix_analyses_pending", False, True),
    ("ix_analyses_user_history", False, False),
    ("ix_analyses_celery_task", False, True),
    ("ix_analyses_severity_completed", False, True),
    ("uq_analyses_asset_analyzer_completed", True, True),
]

for i, (name, is_unique, is_partial) in enumerate(design_indexes, 1):
    flags = []
    if is_unique:
        flags.append("UNIQUE")
    if is_partial:
        flags.append("PARTIAL")
    flag_str = f" [{', '.join(flags)}]" if flags else ""
    print(f"{i}. {name}{flag_str}")

print("\n" + "=" * 70)
print("COMPARISON")
print("=" * 70)

impl_names = {
    str(idx.name)
    for idx in indexes
    if idx.name is not None
}
design_names = {name for name, _, _ in design_indexes}

missing = design_names - impl_names
extra = impl_names - design_names

if missing:
    print(f"\n❌ MISSING INDEXES: {missing}")
    print("   CLASSIFICATION: Category 1 (Implementation Issue)")
    print("   ACTION: Add missing indexes before T5 migration generation")
elif extra:
    print(f"\n⚠️  EXTRA INDEXES: {extra}")
    print("   CLASSIFICATION: Category 2 (Specification Inconsistency)")
    print("   ACTION: Clarify Design §6 or remove extra indexes")
else:
    print(
        f"\n✅ PERFECT MATCH: All {len(impl_names)} indexes match Design specification"
    )
    print("   CLASSIFICATION: No issue detected")
    print("   STATUS: Ready for T5 migration generation")

print("\n" + "=" * 70)
print("DETAILED VERIFICATION")
print("=" * 70)

# Verify unique index has correct structure
unique_idx = [idx for idx in indexes if idx.unique]
print(f"\nUnique indexes found: {len(unique_idx)}")
if unique_idx:
    for idx in unique_idx:
        print(f"  - {idx.name}")
        cols = [c.name for c in idx.columns]
        print(f"    Columns: {cols}")
        where = idx.dialect_options.get("postgresql_where")
        print(f"    WHERE clause: {where}")

# Verify partial indexes
partial_idx = [idx for idx in indexes if idx.dialect_options.get("postgresql_where")]
print(f"\nPartial indexes found: {len(partial_idx)}")
if partial_idx:
    for idx in partial_idx:
        print(f"  - {idx.name}")
        where = idx.dialect_options.get("postgresql_where")
        print(f"    WHERE clause: {where}")

print("\n" + "=" * 70)
