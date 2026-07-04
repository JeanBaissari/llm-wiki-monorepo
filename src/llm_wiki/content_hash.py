"""
Content hash utilities for optimistic locking.

Stores SHA256 of page content (excluding _content_hash field) in frontmatter.
On write: read current hash → compare with expected → conflict if mismatch.
"""
import hashlib
import re

HASH_FIELD = "_content_hash"


def compute_hash(content: str) -> str:
    """Compute SHA256 of page content, excluding the _content_hash field.

    The _content_hash line is removed before hashing so that injecting the
    hash does not change the hash (avoiding infinite churn).
    """
    # Remove _content_hash line from frontmatter before hashing
    cleaned = re.sub(
        rf"^{HASH_FIELD}:.*\n", "", content, flags=re.MULTILINE
    )
    return hashlib.sha256(cleaned.encode("utf-8")).hexdigest()


def read_hash(content: str) -> str:
    """Extract _content_hash from page frontmatter. Returns empty string if absent."""
    m = re.search(rf"^{HASH_FIELD}:\s*(\S+)", content, re.MULTILINE)
    return m.group(1) if m else ""


def inject_hash(content: str) -> str:
    """Inject or update _content_hash in page frontmatter.

    The hash is inserted as a frontmatter field, between the opening and
    closing '---' delimiters.  This keeps metadata inside the YAML block.

    If the field already exists, update it in place.
    If frontmatter is present, insert after the first '---' line.
    If no frontmatter exists, prepend frontmatter with just the hash field.
    """
    h = compute_hash(content)
    # Case 1: field already exists — update in place
    if re.search(rf"^{HASH_FIELD}:", content, re.MULTILINE):
        return re.sub(
            rf"^{HASH_FIELD}:.*",
            f"{HASH_FIELD}: {h}",
            content,
            flags=re.MULTILINE,
        )
    # Case 2: frontmatter present — inject before closing '---' line
    fm_matches = list(re.finditer(r"^---\s*$", content, re.MULTILINE))
    if len(fm_matches) >= 2:
        # Insert right before the closing --- (second one)
        pos = fm_matches[1].start()
        return content[:pos] + f"{HASH_FIELD}: {h}\n" + content[pos:]
    # Case 3: no frontmatter — prepend one
    return f"---\n{HASH_FIELD}: {h}\n---\n\n{content}"
