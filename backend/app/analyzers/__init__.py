"""
Analyzers subsystem.

Pluggable intelligence units as described in 02-Domain-Model.md.
Each analyzer implements a common interface and is structurally
isolated from the pipeline that invokes it.

Analyzer-specific subdirectories (security_analyzer, ocr_analyzer,
metadata_analyzer, ai_document_analyzer, image_analyzer) are created
when their respective Epics are implemented.

See: 06-Repository-Structure.md §9.
"""
