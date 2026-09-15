"""Shared helpers for the StudyMate regression suites.

The upload flow now performs SHA-256 content de-duplication (a Step 14.5
hardening feature). Regression suites that upload the *same* sample PDF on every
run would therefore be rejected as duplicates on the second run. `unique_pdf`
appends a unique, harmless PDF comment so each run's content differs, while the
file remains a valid PDF (the original bytes are preserved as a prefix).
"""

import uuid


def unique_pdf(base_bytes: bytes) -> bytes:
    """Return the given PDF bytes with a unique trailing comment appended."""
    marker = ("\n%%studymate-test-" + uuid.uuid4().hex + "\n").encode("ascii")
    return bytes(base_bytes) + marker
