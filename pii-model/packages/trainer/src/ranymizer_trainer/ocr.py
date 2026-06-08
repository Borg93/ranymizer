# SPDX-FileCopyrightText: Copyright (c) 2026 Ranymizer
# SPDX-License-Identifier: Apache-2.0
"""Span-preserving OCR-noise augmenter for the Swedish PII recipe.

Real PaddleOCR output of scanned Swedish forms and tables is noisy: ``l`` becomes
``1``, ``ö`` loses its diacritic, columns gain stray ``|`` separators, and spaces
drift. We want synthetic *training* text to share that distribution — including OCR
errors *inside* the PII itself, so the tagger learns to find a personnummer even
when a digit got mangled.

THE CONTRACT (read before touching this file)
----------------------------------------------
``ocr_noise(text, entities, rng, *, rate)`` returns ``(noised_text, noised_entities)``
such that **every mention in ``noised_entities`` is a verbatim substring of
``noised_text``**.

This is achieved BY CONSTRUCTION, not by filtering out broken mentions:

1.  Locate each entity mention's character span(s) in the *original* ``text``
    (leftmost, non-overlapping; a mention may occur several times, and a mention
    may itself be a substring of a longer mention — longer mentions claim their
    spans first so the short one only matches elsewhere).
2.  Apply char-level noise to the WHOLE text once, building an index map from every
    original char index ``i`` to the ``(start, end)`` range that char now occupies
    in the output. Insertions / deletions / expansions all stay consistent with
    this map, so any original ``[s, e)`` span maps deterministically to a noised
    span ``[map[s].start, map[e - 1].end)``.
3.  Slice ``noised_text`` at each mapped span to recover the *noised* mention, then
    rebuild ``noised_entities[label]`` as the de-duplicated, order-preserving list
    of those slices. Because each value is literally a slice of ``noised_text``, the
    substring invariant holds even though the PII text itself is now corrupted.

The function is PURE and DETERMINISTIC: all randomness is drawn from the passed-in
``random.Random``. Same ``rng`` seed + same input => identical output. stdlib only;
no data_designer / faker / gliner2 imports, so it loads in any venv.
"""

from __future__ import annotations

import random

# --- char-level confusion tables -------------------------------------------
# Each maps a source character to the candidate glyphs PaddleOCR tends to emit.
# Values are tuples so a confusion may pick among several look-alikes.
_CONFUSIONS: dict[str, tuple[str, ...]] = {
    "l": ("1", "I"),
    "1": ("l", "I"),
    "I": ("1", "l"),
    "O": ("0",),
    "0": ("O",),
    "o": ("0",),
    "B": ("8",),
    "8": ("B",),
    "S": ("5",),
    "5": ("S",),
    "Z": ("2",),
    "2": ("Z",),
    "G": ("6",),
    "6": ("G",),
    ":": (".",),
}

# Diacritic loss is the dominant Swedish OCR error; keep it the likeliest op.
_DIACRITIC_LOSS: dict[str, str] = {
    "å": "a",
    "ä": "a",
    "ö": "o",
    "Å": "A",
    "Ä": "A",
    "Ö": "O",
}
# Rare reverse: a bare vowel mis-read as its diacritic form.
_DIACRITIC_GAIN: dict[str, tuple[str, ...]] = {
    "a": ("å", "ä"),
    "o": ("ö",),
    "A": ("Å", "Ä"),
    "O": ("Ö",),
}

# Digraph confusions, checked (and consuming two source chars) before single ops.
_RN_TO_M = ("rn", "m")
_M_TO_RN = ("m", "rn")


def _find_spans(text: str, mentions: list[str]) -> list[tuple[int, int]]:
    """Return leftmost, non-overlapping ``[start, end)`` spans for ``mentions``.

    Longer mentions are placed first so a short mention that is also a substring of
    a long one is forced to match at a *different* occurrence (or not at all). Each
    occurrence of a repeated mention claims its own span. Empty mentions are skipped.
    """
    taken: list[tuple[int, int]] = []  # claimed regions, kept sorted

    def _overlaps(s: int, e: int) -> bool:
        return any(s < te and ts < e for ts, te in taken)

    # Longest first, then by original list order to keep ties deterministic.
    ordered = sorted(
        ((m, idx) for idx, m in enumerate(mentions) if m),
        key=lambda mi: (-len(mi[0]), mi[1]),
    )
    for mention, _idx in ordered:
        start = 0
        while True:
            pos = text.find(mention, start)
            if pos < 0:
                break
            end = pos + len(mention)
            if not _overlaps(pos, end):
                taken.append((pos, end))
                taken.sort()
                break
            start = pos + 1
    return sorted(taken)


def _char_noise(ch: str, rng: random.Random) -> str:
    """Return the (possibly substituted) glyph(s) for a single char.

    Caller has already decided this char is being noised; pick *which* corruption
    deterministically from ``rng``. May return 0, 1, or 2 chars.
    """
    # Diacritic loss dominates Swedish OCR; weight it heavily when applicable.
    if ch in _DIACRITIC_LOSS and rng.random() < 0.85:
        return _DIACRITIC_LOSS[ch]
    if ch in _DIACRITIC_GAIN and rng.random() < 0.10:
        return rng.choice(_DIACRITIC_GAIN[ch])
    if ch in _CONFUSIONS:
        return rng.choice(_CONFUSIONS[ch])
    if ch in _DIACRITIC_LOSS:  # diacritic char that escaped the 85% branch
        return _DIACRITIC_LOSS[ch]
    # No applicable confusion for this char: leave it unchanged.
    return ch


def _noise_chars(
    text: str, rng: random.Random, rate: float
) -> tuple[str, list[tuple[int, int]]]:
    """Apply per-char OCR noise and return ``(out, index_map)``.

    ``index_map[i] == (start, end)`` is the range in ``out`` produced from
    ``text[i]``. A deleted char yields an empty range ``(start, start)``. Digraph
    ops (``rn``<->``m``) consume two source chars and map both to the new glyphs.
    """
    out: list[str] = []
    index_map: list[tuple[int, int]] = [(0, 0)] * len(text)
    cur = 0  # current length of ``out`` joined
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        nxt = text[i + 1] if i + 1 < n else ""

        # --- digraph confusions (consume two source chars) ----------------
        if ch == "r" and nxt == "n" and rng.random() < rate * 0.5:
            repl = _RN_TO_M[1]  # "m"
            out.append(repl)
            span = (cur, cur + len(repl))
            index_map[i] = span
            index_map[i + 1] = span  # both originals collapse onto "m"
            cur += len(repl)
            i += 2
            continue
        if ch == "m" and rng.random() < rate * 0.4:
            repl = _M_TO_RN[1]  # "rn"
            out.append(repl)
            index_map[i] = (cur, cur + len(repl))
            cur += len(repl)
            i += 1
            continue

        # --- per-char substitution ---------------------------------------
        # Diacritics get a boosted rate (their loss is extremely common in OCR).
        local_rate = rate * 3.0 if ch in _DIACRITIC_LOSS else rate
        repl = _char_noise(ch, rng) if rng.random() < local_rate else ch
        out.append(repl)
        index_map[i] = (cur, cur + len(repl))
        cur += len(repl)
        i += 1

    return "".join(out), index_map


def _map_span(
    index_map: list[tuple[int, int]], s: int, e: int, out_len: int
) -> tuple[int, int]:
    """Map an original ``[s, e)`` span to its noised ``[start, end)`` range."""
    if s >= len(index_map):
        return out_len, out_len
    start = index_map[s][0]
    # Walk back from e-1 to the last original char that produced output, so a
    # trailing deleted char does not shrink the span past real content.
    j = min(e, len(index_map)) - 1
    while j > s and index_map[j][1] == index_map[j][0]:
        j -= 1
    end = index_map[j][1]
    if end < start:
        end = start
    return start, end


def ocr_noise(
    text: str,
    entities: dict[str, list[str]],
    rng: random.Random,
    *,
    rate: float = 0.06,
) -> tuple[str, dict[str, list[str]]]:
    """Add PaddleOCR-style noise to ``text`` while preserving entity spans.

    Returns ``(noised_text, noised_entities)`` where every mention in
    ``noised_entities`` is a verbatim substring of ``noised_text`` — by construction
    (see the module docstring). Pure and deterministic given ``rng``.

    Args:
        text: original synthetic Swedish row.
        entities: ``{label: [mention, ...]}``; mentions must be substrings of
            ``text`` (any that are not are silently dropped — they cannot be mapped).
        rng: seeded ``random.Random`` driving every random choice.
        rate: per-char corruption probability (~0.06 keeps it human-readable).
    """
    # 1. Locate spans per label (leftmost, non-overlapping, longest-first).
    spans_by_label: dict[str, list[tuple[int, int]]] = {}
    for label, mentions in entities.items():
        if not isinstance(mentions, (list, tuple)):
            continue
        spans_by_label[label] = _find_spans(text, [str(m) for m in mentions if m])

    # 2. Char-level noise over the whole text + index map.
    char_noised, index_map = _noise_chars(text, rng, rate)

    # 3. Map every span into the char-noised text and remember its byte range so
    #    we can re-recover it after whitespace jitter shifts indices.
    out_len = len(char_noised)
    span_map: dict[str, list[tuple[int, int]]] = {
        label: [_map_span(index_map, s, e, out_len) for (s, e) in spans]
        for label, spans in spans_by_label.items()
    }

    # 4. Whitespace / structural jitter. This shifts indices, so we apply it to the
    #    char-noised text while tracking how each output index moves, then re-map.
    noised_text, ws_map = _apply_ws_with_map(char_noised, rng, rate)

    # 5. Recover noised mentions as slices of ``noised_text`` (invariant by slice).
    noised_entities: dict[str, list[str]] = {}
    for label, spans in span_map.items():
        seen: set[str] = set()
        recovered: list[str] = []
        for s, e in spans:
            ns = ws_map[s] if s < len(ws_map) else len(noised_text)
            ne = ws_map[e] if e < len(ws_map) else len(noised_text)
            slice_ = noised_text[ns:ne]
            if slice_ and slice_ not in seen:
                seen.add(slice_)
                recovered.append(slice_)
        noised_entities[label] = recovered

    return noised_text, noised_entities


def _apply_ws_with_map(
    text: str, rng: random.Random, rate: float
) -> tuple[str, list[int]]:
    """Whitespace jitter that also returns an index map old->new char positions.

    ``ws_map[i]`` is the position in the output of original char ``i`` (and
    ``ws_map[len(text)]`` is the output length, for end-exclusive span ends). Only
    spaces are added / removed / widened, stray ``|`` columns are injected into
    structured rows, and a long line may gain a wrap newline at a space — so every
    *non-space* character keeps its relative order and span ends always land
    correctly. PII mentions never begin or end on a space in this recipe, so their
    mapped slices stay intact.
    """
    ws_map: list[int] = [0] * (len(text) + 1)
    out: list[str] = []
    cur = 0
    # Per-char flag: is this char on a table/form line (``|`` or 2+ spaces)?
    structured = _structured_flags(text)
    # Per-char distance to the next newline, to gate the rare long-line wrap.
    line_len = _line_lengths(text)
    wrapped_line = -1  # index of the line we already wrapped (at most one wrap/line)
    cur_line = 0
    for i, ch in enumerate(text):
        ws_map[i] = cur
        if ch == "\n":
            out.append("\n")
            cur += 1
            cur_line += 1
            continue
        if ch == " ":
            roll = rng.random()
            if roll < rate:
                sub = rng.random()
                if sub < 0.25:
                    continue  # delete the space (word join)
                if sub < 0.50:
                    out.append("  ")  # double it
                    cur += 2
                    continue
                if structured[i] and sub < 0.78:
                    piece = " | " if rng.random() < 0.4 else "   "
                    out.append(piece)
                    cur += len(piece)
                    continue
                if line_len[cur_line] > 40 and wrapped_line != cur_line and sub < 0.95:
                    out.append("\n")  # rare line wrap at a space
                    cur += 1
                    wrapped_line = cur_line
                    continue
            out.append(" ")
            cur += 1
            continue
        out.append(ch)
        cur += 1
    ws_map[len(text)] = cur
    return "".join(out), ws_map


def _structured_flags(text: str) -> list[bool]:
    """Per-char flag: is this char on a table/form line (has ``|`` or 2+ spaces)?"""
    flags: list[bool] = []
    lines = text.split("\n")
    for n, line in enumerate(lines):
        is_struct = "|" in line or "  " in line
        flags.extend([is_struct] * len(line))
        if n < len(lines) - 1:
            flags.append(is_struct)  # flag for the '\n' joining to the next line
    return flags


def _line_lengths(text: str) -> list[int]:
    """Length of the line each char index belongs to, indexed by *line number*."""
    return [len(line) for line in text.split("\n")]
