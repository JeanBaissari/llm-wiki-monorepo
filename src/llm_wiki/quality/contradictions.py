#!/usr/bin/env python3
"""contradictions.py — Contradiction detection + evidence-grounded confidence.

``llm-wiki contradictions <wiki> detect|list|apply|unapply`` (LWM_034 / ADR-0030)
implements the epistemic companion to ``llm-wiki ask``:

* **Claim extractor** — typed rows ``(subject, predicate, object, polarity,
  page, span)`` from page prose, grounded via the LWM_025 entity layer
  (``build_entity_registry``): a claim is only emitted when its subject
  resolves to a real wiki entity, so ungrounded prose never creates noise.
  Deterministic base-install (stdlib + existing modules); ``--assist llm``
  optionally screens candidates with the ask-wave LLM surface and degrades
  gracefully (absent provider → clear hint, base path unchanged, invariant 8).
* **Contradiction detector** — pairs claims on shared ``(subject, predicate)``
  with opposing polarity (``is``/``is not``, ``has``/``does not have``),
  incompatible numeric values (via the minimal unit-normalization table:
  MB/MiB, GB/GiB, KB/KiB, TB/TiB, ms/s — case-insensitive, so ``3.2 MB`` vs
  ``3.2 MiB`` is NOT a false flag), or mutually exclusive categories.
  **Suggest-only by default** — ``detect`` writes NOTHING (invariant 5).
* **Confidence scorer** — a deterministic formula over source count/recency
  (``sources`` + ``updated``), cross-page agreement (claim corroboration) and
  citation support, mapped to ``high|medium|low`` + a numeric
  ``evidence_score``. Author-overridable: an explicit ``confidence`` with a
  non-``evidence`` ``confidence_source`` marker is preserved, never silently
  overwritten (resolution Q(a)). Pages without ``sources``/``updated`` score
  ``low`` — never ``high``.
* **apply / unapply** — ``apply`` writes the ``contradictions`` frontmatter
  field on the involved pages (and ``confidence``/``confidence_source``/
  ``evidence_score`` with ``--confidence``) and persists the detected-claim +
  contradiction records to the existing ``ClaimsManager`` JSONL sidecar
  (``.llm-wiki/claims/``, ``operation: contradictions-apply`` marker);
  ``unapply`` reverses both, restoring the wiki byte-identically (round-trip).
* **Lint pass** — ``lint_contradictions`` reports pages involved in detected
  conflicts through the existing "contradiction signals" lint output
  (pattern-compatible with ``skill/scripts/validate_fixtures.py`` seeds), and
  the lint service surfaces them under its "Pages with contradictions" block.

The CLI surface is ``contradictions detect|list|apply|unapply`` — distinct from
the existing ``claims health|diff|redteam`` CLI; ``src/llm_wiki/cli.py`` maps
``"contradictions"`` to this module later.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from llm_wiki.core.atomic import atomic_write
from llm_wiki.core.frontmatter import FRONTMATTER_RE, parse_frontmatter
from llm_wiki.core.layout import discover_layout
from llm_wiki.graph.suggest import build_entity_registry, load_pages

# ══════════════════════════════════════════════════════════════════════════
# Unit normalization (resolution Q(b)) — minimal base-install table.
# ══════════════════════════════════════════════════════════════════════════

# raw unit (lowercased) -> (canonical unit, multiplier to canonical base)
# Storage units: decimal (MB) and binary (MiB) prefixes normalize to the SAME
# canonical unit with multiplier 1.0 — "3.2 MB" vs "3.2 MiB" are equal, never
# a false contradiction. Time units convert ms -> s so "500 ms" vs "2 s"
# compare correctly. A full SI/currency/temperature system is out of scope
# (deferred).
_UNIT_TABLE: "dict[str, tuple[str, float]]" = {
    "": ("unitless", 1.0),
    "kb": ("KiB", 1.0), "kib": ("KiB", 1.0),
    "kbyte": ("KiB", 1.0), "kbytes": ("KiB", 1.0),
    "kilobyte": ("KiB", 1.0), "kilobytes": ("KiB", 1.0),
    "mb": ("MiB", 1.0), "mib": ("MiB", 1.0),
    "mbyte": ("MiB", 1.0), "mbytes": ("MiB", 1.0),
    "megabyte": ("MiB", 1.0), "megabytes": ("MiB", 1.0),
    "gb": ("GiB", 1.0), "gib": ("GiB", 1.0),
    "gbyte": ("GiB", 1.0), "gbytes": ("GiB", 1.0),
    "gigabyte": ("GiB", 1.0), "gigabytes": ("GiB", 1.0),
    "tb": ("TiB", 1.0), "tib": ("TiB", 1.0),
    "tbyte": ("TiB", 1.0), "tbytes": ("TiB", 1.0),
    "terabyte": ("TiB", 1.0), "terabytes": ("TiB", 1.0),
    "ms": ("s", 0.001), "msec": ("s", 0.001), "millisecond": ("s", 0.001),
    "milliseconds": ("s", 0.001),
    "s": ("s", 1.0), "sec": ("s", 1.0), "second": ("s", 1.0),
    "seconds": ("s", 1.0),
}

# Mutually exclusive category pairs (resolution: "mutually exclusive
# categories"). Deterministic and deliberately tiny; exact-object matches only.
_MUTUALLY_EXCLUSIVE: "dict[str, str]" = {
    "enabled": "disabled", "disabled": "enabled",
    "active": "inactive", "inactive": "active",
    "open": "closed", "closed": "open",
    "on": "off", "off": "on",
    "public": "private", "private": "public",
    "true": "false", "false": "true",
    "free": "proprietary", "proprietary": "free",
}

_LEADING_APPROX_RE = re.compile(
    r"^(?:approximately|about|around|roughly|exactly|over|under|less than|"
    r"more than|nearly|almost)\s+",
    re.IGNORECASE,
)
_NUMERIC_OBJECT_RE = re.compile(
    r"^\s*(?P<num>\d+(?:\.\d+)?)\s*(?P<unit>[A-Za-z]+)?[^\d]*$"
)
_NEGATION_RE = re.compile(
    r"\b(?:not|never|no|nothing|neither|without|no\s+longer)\b|n't\b|"
    r"\b(?:cannot|can't|doesn't|does\s+not|isn't|is\s+not|hasn't|has\s+not|"
    r"won't)\b",
    re.IGNORECASE,
)
_CLAIM_RE = re.compile(
    r"^(?P<subject>.+?)\s+"
    r"(?P<verb>is|was|are|were|has|have|had|measures|reaches|contains|stores|"
    r"supports|holds|peaks\s+at)\s+"
    r"(?P<object>.+?)\s*$",
    re.IGNORECASE | re.DOTALL,
)
_COPULA_VERBS = {"is", "was", "are", "were"}
_HAS_VERBS = {"has", "have", "had"}

_APPLY_OPERATION = "contradictions-apply"

_EPS = 1e-9


def _values_equal(a: float, b: float) -> bool:
    return abs(a - b) <= _EPS * max(1.0, abs(a), abs(b))


# ══════════════════════════════════════════════════════════════════════════
# Typed claim rows
# ══════════════════════════════════════════════════════════════════════════


@dataclass
class ClaimRow:
    """One typed claim extracted from a page sentence (LWM_034 AC#1).

    ``subject``/``predicate`` are grounded/normalized keys; ``object`` is the
    surface value with a ``value_kind`` classification so the detector can
    compare numeric values, text objects, and polarity independently.
    """

    subject: str
    predicate: str
    object: str
    polarity: str          # "pos" | "neg"
    page: str              # page stem
    span: str              # source sentence
    value_kind: str = "text"      # "numeric" | "text"
    numeric_value: "float | None" = None
    unit: str = "unitless"
    claim_id: str = ""
    object_key: str = ""

    def __post_init__(self) -> None:
        if not self.claim_id:
            key = f"{self.subject}|{self.predicate}|{self.object_key}|{self.polarity}|{self.page}"
            self.claim_id = "clm_" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]


def _normalize_unit(raw: str) -> "tuple[str, float] | None":
    """Map a raw unit token to ``(canonical_unit, multiplier)`` or ``None``."""
    u = (raw or "").strip().lower().replace(" ", "")
    return _UNIT_TABLE.get(u)


def _classify_value(obj: str) -> "tuple[str, float | None, str, str]":
    """Classify an object value.

    Returns ``(value_kind, numeric_value_in_base, canonical_unit, object_key)``.
    ``object_key`` is the normalized identity used for claim dedup and
    corroboration (numeric value + canonical unit, or the lowercased text).
    """
    s = obj.strip().rstrip(".,;!?").strip()
    s = _LEADING_APPROX_RE.sub("", s)
    m = _NUMERIC_OBJECT_RE.match(s)
    if m:
        num = float(m.group("num"))
        unit = m.group("unit") or ""
        norm = _normalize_unit(unit)
        if norm is not None:
            canon, mult = norm
            base = num * mult
            key = f"{base:.6f}|{canon}"
            return "numeric", round(base, 6), canon, key
    return "text", None, "text", s.lower()


def _ground_subject(np: str, registry: dict, page_title: str) -> "str | None":
    """Resolve a subject noun phrase to a registry key (LWM_025 grounding).

    Strips a leading determiner, then takes the longest registry surface the
    phrase starts with (word/`(`/`,` boundary). Falls back to the page's own
    title. ``None`` means the subject is not a known wiki entity — the claim
    is not emitted (entity-layer grounding keeps the base path noise-free).
    """
    s = np.strip().strip('"').strip("'").strip(".")
    s_lower = s.lower()
    s_norm = re.sub(r"^(?:the|a|an)\s+", "", s_lower)
    best: "str | None" = None
    for key in registry:
        if s_norm == key or s_norm.startswith(key + " ") or \
                s_norm.startswith(key + "(") or s_norm.startswith(key + ","):
            if best is None or len(key) > len(best):
                best = key
    if best:
        return best
    title = (page_title or "").lower()
    if title and (s_lower == title or s_lower.startswith(title + " ")):
        return title
    return None


# ══════════════════════════════════════════════════════════════════════════
# Claim extraction
# ══════════════════════════════════════════════════════════════════════════


def _prose_sentences(body: str) -> "list[str]":
    """Turn markdown body text into plain claim-candidate sentences.

    Strips fenced/inline code, headings, and bullet markers; rewrites
    ``[[Page|alias]]`` wikilinks to their display alias (or page name) so
    prose reads naturally; then splits on sentence boundaries.
    """
    text = re.sub(r"```.*?```", " ", body, flags=re.S)
    text = re.sub(r"`[^`]*`", " ", text)
    text = re.sub(r"(?m)^\s*#{1,6}\s+.*$", "", text)
    text = re.sub(r"(?m)^\s*[-*+]\s+", "", text)
    text = re.sub(r"(?m)^\s*\|.*$", "", text)
    text = re.sub(r"(?m)^\s*[-=]{3,}\s*$", "", text)

    def _link(match: "re.Match") -> str:
        target = match.group(1).split("|")[0].split("#")[0].split("/")[-1]
        return match.group(0).split("|")[-1].split("#")[0].split("]")[0] if "|" in match.group(0) else target

    from llm_wiki.core.wikilinks import WIKILINK_RE
    text = WIKILINK_RE.sub(_link, text)
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text) if s.strip()]
    return sentences


def extract_claims(pages: dict, registry: dict) -> "list[ClaimRow]":
    """Deterministic claim extraction over every page (AC#1).

    Returns rows sorted by ``(page, claim_id)`` so ``detect`` output is
    byte-stable on a fixed wiki. Only sentences whose subject grounds to a
    known wiki entity are emitted.
    """
    rows: "list[ClaimRow]" = []
    for stem in sorted(pages):
        _path, text, fm = pages[stem]
        title = (fm.get("title") if fm else None) or stem
        for sentence in _prose_sentences(text):
            m = _CLAIM_RE.match(sentence)
            if not m:
                continue
            raw_subject = m.group("subject").strip()
            subject = _ground_subject(raw_subject, registry, title)
            if subject is None:
                continue
            verb = m.group("verb").lower()
            if verb in _COPULA_VERBS:
                predicate = "is"
            elif verb in _HAS_VERBS:
                predicate = "has"
            else:
                predicate = verb.replace("peaks at", "peaks")
            obj = m.group("object").strip().rstrip(".,;!?").strip()
            # Polarity is decided on the OBJECT clause only — a "no"/"not"
            # inside the subject ("No Evidence Page is ...") is not a negation.
            negated = False
            lead = re.match(r"^(?:not|no|never)\s+", obj, re.IGNORECASE)
            if lead:
                negated = True
                obj = lead.group(0) and re.sub(r"^(?:not|no|never)\s+", "", obj, flags=re.I).strip()
            elif _NEGATION_RE.search(obj):
                negated = True
            polarity = "neg" if negated else "pos"
            kind, num, canon, obj_key = _classify_value(obj)
            rows.append(ClaimRow(
                subject=subject,
                predicate=predicate,
                object=obj,
                polarity=polarity,
                page=stem,
                span=sentence,
                value_kind=kind,
                numeric_value=num,
                unit=canon,
                object_key=obj_key,
            ))
    rows.sort(key=lambda c: (c.page, c.claim_id))
    return rows


# ══════════════════════════════════════════════════════════════════════════
# Contradiction detection
# ══════════════════════════════════════════════════════════════════════════


def _conflict_kind(a: ClaimRow, b: ClaimRow) -> "str | None":
    """Return the conflict kind between two claims sharing (subject, predicate).

    * ``polarity`` — opposing polarity on the SAME normalized object
      (``is X`` vs ``is not X``). ``is X`` vs ``is not Y`` is NOT a
      contradiction (a mission can be crewed and still not the first), so
      polarity conflicts require the objects to be equal.
    * ``value`` — incompatible numeric values (after unit normalization).
    * ``category`` — mutually exclusive text categories.
    Identical claims (equal normalized object, same polarity) are NOT a
    conflict (that is corroboration, not contradiction).
    """
    if a.claim_id == b.claim_id:
        return None
    if a.polarity != b.polarity and a.object_key == b.object_key:
        return "polarity"
    if a.polarity == b.polarity and a.value_kind == "numeric" \
            and b.value_kind == "numeric" and a.unit == b.unit:
        if a.numeric_value is not None and b.numeric_value is not None \
                and not _values_equal(a.numeric_value, b.numeric_value):
            return "value"
    if a.polarity == b.polarity and a.value_kind == "text" \
            and b.value_kind == "text":
        oa, ob = a.object.lower(), b.object.lower()
        if _MUTUALLY_EXCLUSIVE.get(oa) == ob or _MUTUALLY_EXCLUSIVE.get(ob) == oa:
            return "category"
    return None


def detect_contradictions(claims: "list[ClaimRow]") -> "list[dict]":
    """Pair claims across pages on shared ``(subject, predicate)`` (AC#2).

    Suggest-only: returns structured rows, writes NOTHING. Deterministic order
    (sorted by ``contradiction_id``).
    """
    groups: "dict[tuple[str, str], list[ClaimRow]]" = defaultdict(list)
    for c in claims:
        groups[(c.subject, c.predicate)].append(c)

    detections: "list[dict]" = []
    for key in sorted(groups):
        members = groups[key]
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                a, b = members[i], members[j]
                kind = _conflict_kind(a, b)
                if kind is None:
                    continue
                pair_key = "|".join(sorted((a.claim_id, b.claim_id)))
                ctr_id = "ctr_" + hashlib.sha256(pair_key.encode("utf-8")).hexdigest()[:12]
                detections.append({
                    "contradiction_id": ctr_id,
                    "kind": kind,
                    "subject": a.subject,
                    "predicate": a.predicate,
                    "pages": sorted({a.page, b.page}),
                    "claim_a": asdict(a),
                    "claim_b": asdict(b),
                    "reason": f"{a.page} states '{a.span}' while {b.page} states '{b.span}'",
                    "reason_short": f"{a.subject} {a.predicate}: {a.object} vs {b.object}",
                })
    detections.sort(key=lambda d: d["contradiction_id"])
    return detections


# ══════════════════════════════════════════════════════════════════════════
# Confidence scorer (resolution Q(a): deterministic, author-overridable)
# ══════════════════════════════════════════════════════════════════════════

CONFIDENCE_WEIGHTS = {
    "source": 0.30,   # number of distinct frontmatter `sources`
    "recency": 0.20,  # `updated` recency vs the freshest page in the wiki
    "citation": 0.25, # fraction of `sources` that resolve to real raw files
    "agreement": 0.25,# cross-page corroboration minus contradiction
}
HIGH_THRESHOLD = 0.70
MEDIUM_THRESHOLD = 0.40
NO_EVIDENCE_CAP = 0.39  # no sources/updated → low, never high (AC#4)


def _sources_list(sources) -> "list[str]":
    if sources is None:
        return []
    if isinstance(sources, list):
        return [str(s).strip() for s in sources if str(s).strip()]
    if isinstance(sources, str):
        return [s.strip() for s in re.split(r"[,\n]", sources) if s.strip()]
    return []


def _parse_date_simple(value) -> "datetime | None":
    v = str(value or "").strip()
    if not v:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            dt = datetime.strptime(v, fmt)
            return dt.replace(tzinfo=None)
        except ValueError:
            continue
    try:
        return datetime.strptime(v, "%Y-%m-%d")
    except ValueError:
        return None


def _max_updated(pages: dict) -> "datetime | None":
    best: "datetime | None" = None
    for _p, _t, fm in pages.values():
        dt = _parse_date_simple((fm or {}).get("updated"))
        if dt and (best is None or dt > best):
            best = dt
    return best


def _recency_signal(updated: "datetime | None", reference: "datetime | None") -> float:
    if updated is None or reference is None:
        return 0.0
    age = max((reference - updated).days, 0)
    return round(max(1.0 - age / 365.0, 0.0), 6)


def _source_exists(slug: str, raw_dir: "Path | None", root: Path) -> bool:
    slug = str(slug).strip().lstrip("./")
    if raw_dir and raw_dir.is_dir():
        try:
            for hit in raw_dir.rglob(f"{slug}*"):
                if hit.is_file():
                    return True
        except OSError:
            pass
    for cand in (root / slug, root / (slug + ".md"),
                 (root / "raw" / slug) if raw_dir is None else None,
                 (root / "raw" / (slug + ".md")) if raw_dir is None else None):
        if cand is None:
            continue
        if cand.is_file():
            return True
    return False


def _citation_support(sources: "list[str]", raw_dir: "Path | None", root: Path) -> float:
    unique = {s for s in sources if s}
    if not unique:
        return 0.0
    resolved = sum(1 for s in unique if _source_exists(s, raw_dir, root))
    return round(resolved / len(unique), 6)


def _corroborator_count(stem: str, claims_by_page: dict) -> int:
    mine = claims_by_page.get(stem, [])
    if not mine:
        return 0
    my_keys = {(c.subject, c.predicate, c.object_key, c.polarity) for c in mine}
    others = 0
    for other_stem, cs in claims_by_page.items():
        if other_stem == stem:
            continue
        if any((c.subject, c.predicate, c.object_key, c.polarity) in my_keys for c in cs):
            others += 1
    return others


def _evidence_score(
    stem: str,
    fm: dict,
    claims_by_page: dict,
    contradicted_pages: "set[str]",
    reference: "datetime | None",
    raw_dir: "Path | None",
    root: Path,
) -> dict:
    sources = _sources_list(fm.get("sources"))
    updated = _parse_date_simple(fm.get("updated"))
    no_evidence = (not sources) or (updated is None)

    source_signal = min(len(set(sources)), 5) / 5.0
    recency_signal = _recency_signal(updated, reference)
    citation_support = _citation_support(sources, raw_dir, root)
    corr = _corroborator_count(stem, claims_by_page)
    contradicted = stem in contradicted_pages
    agreement = 0.5 * min(corr, 3) / 3.0 + (0.5 if not contradicted else 0.0)

    score = round(
        CONFIDENCE_WEIGHTS["source"] * source_signal
        + CONFIDENCE_WEIGHTS["recency"] * recency_signal
        + CONFIDENCE_WEIGHTS["citation"] * citation_support
        + CONFIDENCE_WEIGHTS["agreement"] * agreement,
        4,
    )
    label = "high" if score >= HIGH_THRESHOLD else ("medium" if score >= MEDIUM_THRESHOLD else "low")
    if no_evidence:
        label = "low"
        score = min(score, NO_EVIDENCE_CAP)
    return {
        "label": label,
        "evidence_score": score,
        "no_evidence": no_evidence,
        "signal": {
            "sources": len(set(sources)),
            "recency": recency_signal,
            "citation": citation_support,
            "agreement": agreement,
        },
    }


def score_confidence(wiki_root: str, analysis=None) -> dict:
    """Deterministic confidence labels + evidence scores for every page.

    Returns ``{page_stem: {label, evidence_score, confidence_source,
    write_confidence, no_evidence}}``. ``confidence_source`` is ``"author"``
    when an explicit author-set ``confidence`` (non-``evidence`` marker) must
    be preserved — evidence never silently overwrites it (resolution Q(a));
    ``write_confidence`` is False in that case.
    """
    if analysis is None:
        analysis = _analyze(wiki_root)
    _layout, pages, claims, detections = analysis
    claims_by_page: "dict[str, list[ClaimRow]]" = defaultdict(list)
    for c in claims:
        claims_by_page[c.page].append(c)
    contradicted_pages = {p for d in detections for p in d["pages"]}
    reference = _max_updated(pages)
    raw_dir = Path(_layout.raw_dir) if _layout.raw_dir else None
    root = Path(_layout.root)

    out: dict = {}
    for stem in sorted(pages):
        _p, _t, fm = pages[stem]
        fm = fm or {}
        author_conf = fm.get("confidence")
        conf_source = fm.get("confidence_source")
        author_intent = bool(author_conf and str(conf_source).strip() != "evidence")
        res = _evidence_score(stem, fm, claims_by_page, contradicted_pages, reference, raw_dir, root)
        res["confidence_source"] = "author" if author_intent else "evidence"
        res["write_confidence"] = not author_intent
        out[stem] = res
    return out


# ══════════════════════════════════════════════════════════════════════════
# Frontmatter editing (reversible)
# ══════════════════════════════════════════════════════════════════════════


def _yaml_scalar(value) -> str:
    if isinstance(value, list):
        return "[" + ", ".join(json.dumps(str(v)) for v in value) + "]"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    s = str(value)
    if re.fullmatch(r"[A-Za-z0-9_.\-/ ]+", s) and ":" not in s and not s.startswith((" ", "-")):
        return s
    return json.dumps(s)


def _add_frontmatter_fields(text: str, fields: dict) -> str:
    """Set ``fields`` in the frontmatter block (replace-or-append per key).

    A pre-existing single-line field with the same key is replaced in place
    (deterministic order), so re-running ``apply`` never duplicates a line and
    ``unapply`` can reverse the exact lines written.
    """
    m = FRONTMATTER_RE.match(text)
    if not m:
        return text
    header = m.group(1)
    lines = header.split("\n")
    keys = list(fields)
    existing_idx: "dict[str, int]" = {}
    for i, line in enumerate(lines):
        k = line.split(":", 1)[0].strip()
        if k in keys and k not in existing_idx:
            existing_idx[k] = i
    for key in keys:
        line = f"{key}: {_yaml_scalar(fields[key])}"
        if key in existing_idx:
            lines[existing_idx[key]] = line
        else:
            lines.append(line)
    new_header = "\n".join(lines)
    return text[: m.start(1)] + new_header + text[m.end(1):]


def _remove_frontmatter_fields(text: str, keys) -> str:
    """Remove single-line frontmatter fields with the given keys (byte-exact)."""
    m = FRONTMATTER_RE.match(text)
    if not m:
        return text
    header = m.group(1)
    lines = [l for l in header.split("\n")
             if not (l and l.split(":", 1)[0].strip() in keys)]
    return text[: m.start(1)] + "\n".join(lines) + text[m.end(1):]


def _frontmatter_list(value) -> "list[str]":
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    s = str(value).strip()
    return [s] if s else []


def _ctr_entries(fm_value) -> "list[str]":
    return _frontmatter_list(fm_value)


def _set_contradictions_field(text: str, entries: "list[str]") -> str:
    """Merge ``entries`` into the page's ``contradictions`` frontmatter field.

    Dedupes on the leading ``ctr_...`` id so re-running ``apply`` is
    idempotent; author-authored entries (no ``ctr_`` prefix) are preserved.
    """
    fm = parse_frontmatter(text) or {}
    existing = _ctr_entries(fm.get("contradictions"))
    merged = []
    seen = set()
    for e in existing + list(entries):
        token = e.split(":", 1)[0].strip()
        if token in seen:
            continue
        seen.add(token)
        merged.append(e)
    return _add_frontmatter_fields(text, {"contradictions": merged})


# ══════════════════════════════════════════════════════════════════════════
# Wiki loading + analysis
# ══════════════════════════════════════════════════════════════════════════


def _load_pages_wiki(wiki_root: str):
    layout = discover_layout(wiki_root)
    wiki_dir = Path(layout.pages_dir)
    skip = frozenset(f"{s}.md" for s in layout.skip_stems)
    pages = load_pages(wiki_dir, skip)
    return layout, pages


def _analyze(wiki_root: str):
    """Single extraction+detection pass shared by detect/apply/lint/confidence."""
    layout, pages = _load_pages_wiki(wiki_root)
    registry = build_entity_registry(pages)
    claims = extract_claims(pages, registry)
    detections = detect_contradictions(claims)
    return layout, pages, claims, detections


# ══════════════════════════════════════════════════════════════════════════
# Persistence records (reuse ClaimsManager sidecar)
# ══════════════════════════════════════════════════════════════════════════


def _claim_record(c: ClaimRow, pages: dict) -> dict:
    fm = (pages[c.page][2] if c.page in pages else None) or {}
    upd = str(fm.get("updated") or "")
    return {
        "claim_id": c.claim_id,
        "statement": c.span,
        "confidence": str(fm.get("confidence") or "medium"),
        "status": "active",
        "sources": _sources_list(fm.get("sources")),
        "pages": [c.page],
        "claim_type": "fact",
        "schema_version": "v0.2.1",
        "created_at": upd,
        "updated_at": upd,
        "first_seen_operation_id": _APPLY_OPERATION,
        "last_seen_operation_id": _APPLY_OPERATION,
        "subject": c.subject,
        "predicate": c.predicate,
        "object": c.object,
        "polarity": c.polarity,
        "span": c.span,
        "operation": _APPLY_OPERATION,
    }


def _contradiction_record(d: dict) -> dict:
    return {
        "contradiction_id": d["contradiction_id"],
        "claim_ids": [d["claim_a"]["claim_id"], d["claim_b"]["claim_id"]],
        "status": "open",
        "severity": "medium",
        "evidence": list(d["pages"]),
        "resolution": "",
        "created_at": "",
        "kind": d["kind"],
        "pages": list(d["pages"]),
        "operation": _APPLY_OPERATION,
    }


# ══════════════════════════════════════════════════════════════════════════
# apply / unapply (invariant 5: suggest-only, reversible, git-diffable)
# ══════════════════════════════════════════════════════════════════════════


def apply_contradictions(wiki_root: str, with_confidence: bool = False,
                         analysis=None, detections=None) -> int:
    """Write the ``contradictions`` field (and confidence fields) + sidecar.

    ``--confidence`` additionally writes ``confidence``/``confidence_source``/
    ``evidence_score`` on every evidence-wins page (never an author-marked
    one). ``detections`` (post-screening) defaults to the deterministic set.
    Returns the number of page files modified.
    """
    if analysis is None:
        analysis = _analyze(wiki_root)
    _layout, pages, claims, auto_detections = analysis
    if detections is None:
        detections = auto_detections

    from llm_wiki.quality.claims.storage import ClaimsManager
    mgr = ClaimsManager(wiki_root)
    mgr.append_claims([_claim_record(c, pages) for c in claims])
    mgr.append_contradictions([_contradiction_record(d) for d in detections])

    by_page: "dict[str, list[dict]]" = defaultdict(list)
    for d in detections:
        for p in d["pages"]:
            by_page[p].append(d)

    modified = 0
    for stem in sorted(by_page):
        path, text, _fm = pages[stem]
        entries = [f"{d['contradiction_id']}: {d['reason_short']}" for d in sorted(by_page[stem], key=lambda d: d["contradiction_id"])]
        new_text = _set_contradictions_field(text, entries)
        if new_text != text:
            atomic_write(str(path), new_text)
            modified += 1

    if with_confidence:
        scores = score_confidence(wiki_root, analysis=analysis)
        for stem in sorted(pages):
            res = scores[stem]
            if not res["write_confidence"]:
                continue
            path, text, _fm = pages[stem]
            fields = {
                "confidence": res["label"],
                "confidence_source": "evidence",
                "evidence_score": res["evidence_score"],
            }
            new_text = _add_frontmatter_fields(text, fields)
            if new_text != text:
                atomic_write(str(path), new_text)
                modified += 1
    return modified


def unapply_contradictions(wiki_root: str) -> int:
    """Reverse ``apply``: remove applied frontmatter fields + sidecar records.

    Removes the ``contradictions`` entries whose ``ctr_`` id was written by an
    apply run, and (when ``confidence_source: evidence``) the
    ``confidence``/``confidence_source``/``evidence_score`` fields — restoring
    the wiki byte-identically. Every sidecar record carrying the apply
    ``operation`` marker is removed (claims + contradictions), then the empty
    sidecar directory is cleaned up; an unrelated pre-existing claims sidecar
    is untouched.
    """
    from llm_wiki.quality.claims.storage import ClaimsManager
    mgr = ClaimsManager(wiki_root)
    applied_ctrs = [c for c in mgr.get_all_contradictions()
                    if c.get("operation") == _APPLY_OPERATION]
    removed_ctr_ids = {c.get("contradiction_id") for c in applied_ctrs}
    removed_claim_ids = {c.get("claim_id")
                         for c in mgr.get_all_claims()
                         if c.get("operation") == _APPLY_OPERATION}
    involved_pages: "set[str]" = set()
    for c in applied_ctrs:
        involved_pages.update(c.get("pages") or [])

    layout, pages = _load_pages_wiki(wiki_root)
    modified = 0
    for stem in sorted(pages):
        path, text, fm = pages[stem]
        fm = fm or {}
        new_text = text

        if fm.get("confidence_source") == "evidence":
            new_text = _remove_frontmatter_fields(
                new_text, ("confidence", "confidence_source", "evidence_score")
            )

        if stem in involved_pages:
            entries = _ctr_entries(fm.get("contradictions"))
            keep = [e for e in entries if e.split(":", 1)[0].strip() not in removed_ctr_ids]
            if len(keep) != len(entries):
                if keep:
                    new_text = _add_frontmatter_fields(new_text, {"contradictions": keep})
                else:
                    new_text = _remove_frontmatter_fields(new_text, ("contradictions",))

        if new_text != text:
            atomic_write(str(path), new_text)
            modified += 1

    mgr.remove_contradictions(removed_ctr_ids)
    mgr.remove_claims(removed_claim_ids)
    mgr.cleanup_empty_sidecar()
    return modified


# ══════════════════════════════════════════════════════════════════════════
# Lint pass (extending the existing "contradiction signals" output)
# ══════════════════════════════════════════════════════════════════════════


def lint_contradictions(wiki_root: str) -> "list[str]":
    """Suggest-only detector for the lint pass: involved page relpaths.

    Returns the relative (forward-slash) page paths whose prose hosts a
    detected contradiction — the same shape the lint service's
    "Pages with contradictions" block emits, so the ``validate_fixtures``
    "contradiction signals" seed matching stays green. Never writes.
    """
    try:
        layout, pages, _claims, detections = _analyze(wiki_root)
    except Exception:
        return []
    root = Path(layout.root)
    involved = sorted({p for d in detections for p in d["pages"]})
    relpaths = []
    for stem in involved:
        if stem in pages:
            p = pages[stem][0]
            try:
                relpaths.append(str(p.relative_to(root)).replace("\\", "/"))
            except ValueError:
                continue
    return relpaths


# ══════════════════════════════════════════════════════════════════════════
# LLM-assisted screening (--assist llm, graceful degradation)
# ══════════════════════════════════════════════════════════════════════════


def _llm_screen(detections: "list[dict]", assist: "str | None",
                screen_fn=None) -> "list[dict]":
    """Optional LLM-assisted screening of candidate contradictions.

    Degrades gracefully (invariants 3/8): without ``--assist llm`` it is a
    no-op; with an unknown backend or an unavailable LLM provider it prints a
    clear hint to stderr and returns the deterministic detection list
    unchanged — never crashes, never changes the base path.
    """
    if not assist:
        return detections
    if assist != "llm":
        print(f"hint: unknown --assist backend '{assist}'; "
              "using deterministic lexical detection (base path unchanged).",
              file=sys.stderr)
        return detections
    if screen_fn is not None:
        try:
            out = screen_fn(detections)
            return out if out is not None else detections
        except Exception as e:
            print(f"hint: LLM-assisted screening failed ({type(e).__name__}: {e}); "
                  "using deterministic lexical detection (base path unchanged).",
                  file=sys.stderr)
            return detections
    try:
        from llm_wiki.providers.registry import detect_default_provider
        if detect_default_provider() in (None, "", "default"):
            raise RuntimeError("no LLM provider configured")
    except Exception as e:
        print(f"hint: LLM-assisted screening unavailable ({type(e).__name__}: {e}); "
              "using deterministic lexical detection (base path unchanged).",
              file=sys.stderr)
        return detections
    try:
        from pydantic import BaseModel, Field
        from llm_wiki.providers.registry import call_llm_structured

        class ScreenResponse(BaseModel):
            keep_ids: "list[str]" = Field(
                default_factory=list,
                description="Contradiction ids that are genuine contradictions.",
            )

        system = (
            "You screen candidate wiki contradictions. A candidate is genuine "
            "when the two pages really disagree on the same subject and "
            "predicate. Reply with the ids to KEEP, one per candidate you "
            "judge genuine."
        )
        user = "\n".join(
            f"{d['contradiction_id']}\t{d['reason']}" for d in detections
        )
        resp = call_llm_structured(system, user, ScreenResponse)
        if resp is None or not getattr(resp, "keep_ids", None):
            return detections
        keep = set(resp.keep_ids)
        return [d for d in detections if d["contradiction_id"] in keep]
    except Exception as e:
        print(f"hint: LLM-assisted screening failed ({type(e).__name__}: {e}); "
              "using deterministic lexical detection (base path unchanged).",
              file=sys.stderr)
        return detections


# ══════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════

SUBCOMMANDS = ("detect", "list", "apply", "unapply")


def _print_detections(claims, detections, as_json: bool) -> None:
    if as_json:
        print(json.dumps({
            "claims": [asdict(c) for c in claims],
            "contradictions": detections,
        }, indent=2, default=str))
        return
    print(f"# Claims ({len(claims)})")
    for c in claims:
        print(f"- {c.subject} | {c.predicate} | {c.object} | {c.polarity} | "
              f"{c.page} | {c.span}")
    print(f"\n# Contradictions ({len(detections)}) [suggest-only — "
          f"run `contradictions apply` to write]")
    for d in detections:
        print(f"- {d['contradiction_id']} ({d['kind']}) "
              f"pages={','.join(d['pages'])}")
        print(f"    {d['reason']}")


def _cmd_detect(wiki_root: str, assist: "str | None", as_json: bool) -> int:
    analysis = _analyze(wiki_root)
    _layout, _pages, claims, detections = analysis
    detections = _llm_screen(detections, assist)
    _print_detections(claims, detections, as_json)
    return 0


def _cmd_list(wiki_root: str, as_json: bool) -> int:
    from llm_wiki.quality.claims.storage import ClaimsManager, has_sidecar
    if not has_sidecar(wiki_root):
        print("No contradiction records found (nothing applied yet).")
        return 0
    mgr = ClaimsManager(wiki_root)
    applied = [c for c in mgr.get_all_contradictions()
               if c.get("operation") == _APPLY_OPERATION]
    if as_json:
        print(json.dumps(applied, indent=2, default=str))
        return 0
    if not applied:
        print("No applied contradiction records found.")
        return 0
    print(f"# Applied contradictions ({len(applied)})")
    for c in sorted(applied, key=lambda c: c.get("contradiction_id", "")):
        print(f"- {c.get('contradiction_id')} ({c.get('kind', '')}) "
              f"pages={','.join(c.get('pages', []))}")
    return 0


def _cmd_apply(wiki_root: str, with_confidence: bool, assist: "str | None",
               as_json: bool) -> int:
    analysis = _analyze(wiki_root)
    _layout, _pages, claims, detections = analysis
    detections = _llm_screen(detections, assist)
    modified = apply_contradictions(
        wiki_root, with_confidence=with_confidence,
        analysis=analysis, detections=detections,
    )
    result = {
        "applied": True,
        "pages_modified": modified,
        "claims_persisted": len(claims),
        "contradictions": len(detections),
    }
    if as_json:
        print(json.dumps(result, indent=2, default=str))
    else:
        print(f"Applied {len(detections)} contradiction(s) across "
              f"{modified} page file(s).")
        if with_confidence:
            print("Confidence/confidence_source/evidence_score written on "
                  "evidence-wins pages (author-marked pages preserved).")
    return 0


def _cmd_unapply(wiki_root: str, as_json: bool) -> int:
    modified = unapply_contradictions(wiki_root)
    result = {"applied": False, "pages_modified": modified}
    if as_json:
        print(json.dumps(result, indent=2, default=str))
    else:
        print(f"Unapplied contradiction annotations across {modified} page file(s).")
    return 0


def _parse_args(argv: "list[str]"):
    """Parse ``contradictions [detect|list|apply|unapply] <wiki> [flags]``.

    Accepts both ``<wiki> detect`` and ``detect <wiki>`` orderings.
    """
    subcommand: "str | None" = None
    wiki_root: "str | None" = None
    with_confidence = False
    as_json = False
    assist: "str | None" = None
    positionals: "list[str]" = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ("-h", "--help"):
            positionals.append(a)
        elif a == "--confidence":
            with_confidence = True
        elif a == "--json":
            as_json = True
        elif a == "--assist":
            if i + 1 < len(argv):
                assist = argv[i + 1]
                i += 1
            else:
                assist = "llm"
        elif a.startswith("--assist="):
            assist = a.split("=", 1)[1]
        else:
            positionals.append(a)
        i += 1

    if not positionals or "-h" in positionals or "--help" in positionals:
        return None, None, with_confidence, assist, as_json

    if positionals[0] in SUBCOMMANDS:
        subcommand = positionals[0]
        wiki_root = positionals[1] if len(positionals) > 1 else None
    elif len(positionals) >= 2 and positionals[1] in SUBCOMMANDS:
        wiki_root = positionals[0]
        subcommand = positionals[1]
    else:
        subcommand = positionals[0]
        wiki_root = positionals[1] if len(positionals) > 1 else None
    return subcommand, wiki_root, with_confidence, assist, as_json


def _print_help() -> None:
    print("""Usage: llm-wiki contradictions <wiki> detect|list|apply|unapply [flags]

Subcommands:
  detect    Extract typed claims + suggest contradictions (writes NOTHING)
  list      List contradiction records currently applied (sidecar)
  apply     Write the `contradictions` frontmatter field on involved pages
            (+ confidence fields with --confidence) and persist to the
            claims sidecar (reversible)
  unapply   Reverse apply: restore pages + sidecar byte-identically

Flags:
  --confidence    With apply: also write confidence / confidence_source /
                  evidence_score on evidence-wins pages (author-marked
                  pages are preserved)
  --assist llm    Optional LLM-assisted screening; degrades gracefully
                  (absent provider -> hint, deterministic base path)
  --json          Machine-readable output

LWM_034 / ADR-0030 — contradiction detection + evidence-grounded confidence.""")


def run(argv: "list[str]") -> int:
    subcommand, wiki_root, with_confidence, assist, as_json = _parse_args(argv)
    if subcommand is None:
        _print_help()
        return 0 if any(a in ("-h", "--help") for a in argv) else 2
    if not wiki_root:
        print("error: <wiki> path is required", file=sys.stderr)
        return 2
    if subcommand == "detect":
        return _cmd_detect(wiki_root, assist, as_json)
    if subcommand == "list":
        return _cmd_list(wiki_root, as_json)
    if subcommand == "apply":
        return _cmd_apply(wiki_root, with_confidence, assist, as_json)
    if subcommand == "unapply":
        return _cmd_unapply(wiki_root, as_json)
    _print_help()
    return 2


def main() -> int:
    """CLI entry point (mirrors cli.py's UTF-8 reconfigure convention)."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            break
    return run(sys.argv[1:])


if __name__ == "__main__":
    sys.exit(main())
