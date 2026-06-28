"""Extract which ``[S#]`` source markers the model actually used.

The model writes markdown prose with inline ``[S#]`` citation markers. The frontend renders the
markdown and resolves the markers into chips (via ``marker_map``); the backend only needs to know
which markers resolved — to build the "Sources for this answer" list, and (for the Phase-2 trace)
the cited-vs-retrieved set. Hallucinated ids that aren't in ``marker_map`` are ignored.
"""

from __future__ import annotations

import re

from .citations import CitationRef

# A bracketed source-marker group the model emits, e.g. "[S1]", "[S1][S3]" (two matches),
# or "[S1, S3]" (one match, two ids).
_MARKER_GROUP_RE = re.compile(r"\[\s*(S\d+(?:\s*[,;]?\s*S\d+)*)\s*\]")
_SID_RE = re.compile(r"S(\d+)")


def extract_used_markers(
    prose: str, marker_map: dict[str, CitationRef]
) -> tuple[list[CitationRef], list[str]]:
    """Return ``(used_refs, used_marker_ids)`` for the resolvable ``[S#]`` markers in ``prose``.

    ``used_refs`` are the distinct cited ``CitationRef``s in first-appearance order, deduped by
    (source, timestamp) so multiple cited timestamps on one lecture survive for the evidence
    reference list. ``used_marker_ids`` are the surviving ``S#`` ids (deduped, first-appearance) —
    required by the Phase-2 ``cited_vs_retrieved`` trace, which ``CitationRef`` alone can't yield.
    """
    used: list[CitationRef] = []
    used_keys: set[str] = set()
    marker_ids: list[str] = []
    seen_markers: set[str] = set()

    for m in _MARKER_GROUP_RE.finditer(prose):
        for sid in _SID_RE.findall(m.group(1)):
            marker = f"S{sid}"
            ref = marker_map.get(marker)
            if ref is None:
                continue  # hallucinated id -> ignore
            if marker not in seen_markers:
                seen_markers.add(marker)
                marker_ids.append(marker)
            key = f"{ref.link_target or ref.display}@{ref.timestamp or ''}"
            if key not in used_keys:
                used_keys.add(key)
                used.append(ref)
    return used, marker_ids
