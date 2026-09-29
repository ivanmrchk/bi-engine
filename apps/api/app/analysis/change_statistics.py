"""Is a change bigger than chance alone would produce?

Each function returns a z-score: the change divided by its standard
error, the typical size of a purely random swing at that sample size.
Chance rarely produces a z-score beyond about 2 either way, so a change
that large is treated as real. None means there's too little data to say.
"""

import math

CLEAR_CHANGE_Z_SCORE = 2.0


def count_change_z_score(before: int, after: int) -> float | None:
    """For counts of independent events, like booked jobs.

    Such counts swing randomly by about their square root, which makes the
    standard error of the log ratio sqrt(1/before + 1/after).
    """
    if before == 0 or after == 0:
        return None
    return math.log(after / before) / math.sqrt(1 / before + 1 / after)


def share_change_z_score(successes_before: int, total_before: int, successes_after: int, total_after: int) -> float | None:
    """For a share of a total, like the share of booked jobs that became real work.

    A two-proportion test: if nothing had changed, both periods would share
    one underlying rate, estimated by pooling them.
    """
    if total_before == 0 or total_after == 0:
        return None
    pooled_share = (successes_before + successes_after) / (total_before + total_after)
    standard_error = math.sqrt(pooled_share * (1 - pooled_share) * (1 / total_before + 1 / total_after))
    if standard_error == 0:
        return None
    return (successes_after / total_after - successes_before / total_before) / standard_error


def mean_change_z_score(
    mean_before: float, variance_before: float, count_before: int,
    mean_after: float, variance_after: float, count_after: int,
) -> float | None:
    """For an average, like the average ticket (Welch's test).

    Each average wobbles by its spread divided by the square root of how
    many values went into it.
    """
    if count_before < 2 or count_after < 2:
        return None
    standard_error = math.sqrt(variance_before / count_before + variance_after / count_after)
    if standard_error == 0:
        return None
    return (mean_after - mean_before) / standard_error
