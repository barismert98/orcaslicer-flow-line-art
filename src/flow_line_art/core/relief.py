"""Line relief: how many stacked passes of the line each part of the picture gets.

Darker parts get more passes, so the picture gains depth in raking light. A layer is
finished before the next starts: inside a spiral, stacking in place would drag the
nozzle's flat tip through the taller turn beside it.
"""
from __future__ import annotations

MIN_LAYERS = 2
MAX_LAYERS = 6  # a single-bead wall gets too fragile above this
MIN_RUN_MM = 8.0  # shorter raised runs cost a stop and print as a blob
MIN_GAP_MM = 8.0  # shorter dips are not worth a stop either
SECONDS_PER_STOP = 2.0  # retract, lift, cross and prime


def runs(mask: list) -> list:
    """The stretches of True in `mask`, as (start, end) with `end` exclusive."""
    found = []
    start = None
    for index, value in enumerate(mask):
        if value and start is None:
            start = index
        elif not value and start is not None:
            found.append((start, index))
            start = None
    if start is not None:
        found.append((start, len(mask)))
    return found


def _fill_short_gaps(mask: list, lengths: list) -> list:
    """Bridges interior gaps; a gap touching either end of the line costs no stop."""
    filled = list(mask)
    for start, end in runs([not value for value in mask]):
        if start > 0 and end < len(mask) and sum(lengths[start:end]) < MIN_GAP_MM:
            filled[start:end] = [True] * (end - start)
    return filled


def _drop_short_runs(mask: list, lengths: list) -> list:
    kept = list(mask)
    for start, end in runs(mask):
        if sum(lengths[start:end]) < MIN_RUN_MM:
            kept[start:end] = [False] * (end - start)
    return kept


def pass_counts(widths: list, lengths: list, width_min: float, width_max: float, layers: int) -> list:
    """Passes per segment, from the line width that already carries the picture's tone.

    Each raised level stands on the one below it, so no bead is ever laid over air.
    """
    span = width_max - width_min
    counts = [1] * len(widths)
    below = [True] * len(widths)
    for level in range(2, layers + 1):
        threshold = (level - 1) / layers
        wanted = _fill_short_gaps([(width - width_min) / span >= threshold for width in widths], lengths)
        below = _drop_short_runs([up and low for up, low in zip(wanted, below)], lengths)
        counts = [count + raised for count, raised in zip(counts, below)]
    return counts
