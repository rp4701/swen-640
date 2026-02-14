from __future__ import annotations

from math import ceil
from typing import Any, Callable, List, Optional, Sequence, TypeVar
import random

T = TypeVar("T")


# ---- Uniform Sampling ----

def sample_uniform(items: Sequence[T], k: int, seed: Optional[int] = None) -> List[T]:
    """Draw k items uniformly at random without replacement."""
    if k >= len(items):
        return list(items)

    rng = random.Random(seed)
    return rng.sample(list(items), k)


# ---- Stratified Sampling ----

def sample_stratified(
    items: Sequence[T],
    key: Callable[[T], Any],
    *,
    n: Optional[int] = None,
    frac: Optional[float] = None,
    seed: Optional[int] = None,
) -> List[T]:
    """Stratified sampling by key(item)."""

    # Validate parameters
    if (n is None and frac is None) or (n is not None and frac is not None):
        raise ValueError("Exactly one of `n` or `frac` must be provided")

    if frac is not None and frac < 0:
        raise ValueError("frac must be >= 0")

    # Group items by stratum
    groups = {}
    for item in items:
        groups.setdefault(key(item), []).append(item)

    result: List[T] = []

    # Sample within each group
    for gkey, group_items in groups.items():

        # deterministic sub-seed per group
        sub_seed = None if seed is None else hash((gkey, seed))
        rng = random.Random(sub_seed)

        if n is not None:
            k = min(n, len(group_items))
        else:
            k = int(len(group_items) * frac)
            if frac > 0 and k == 0:
                k = 1
            k = min(k, len(group_items))

        result.extend(rng.sample(group_items, k))

    return result


# ---- Systematic Sampling ----

def sample_systematic(
    items: Sequence[T], step: int, seed: Optional[int] = None
) -> List[T]:
    """Systematic sampling: random start, then every step-th item."""

    if step <= 0:
        raise ValueError("step must be >= 1")

    if not items:
        return []

    rng = random.Random(seed)
    start = rng.randrange(step)

    result: List[T] = []
    idx = start

    while idx < len(items):
        result.append(items[idx])
        idx += step

    return result


# ---- Sample Size for Proportions ----

def sample_size_proportion(
    N: Optional[int], p: float = 0.5, margin: float = 0.05, z: float = 1.96
) -> int:
    """Compute required sample size to estimate a proportion."""

    if not (0 < p < 1):
        raise ValueError("p must be between 0 and 1")

    if margin <= 0:
        raise ValueError("margin must be > 0")

    # infinite population estimate
    n0 = (z**2 * p * (1 - p)) / (margin**2)

    if N is not None:
        if N <= 0:
            raise ValueError("N must be positive")
        n = n0 / (1 + (n0 - 1) / N)
        return min(ceil(n), N)

    return ceil(n0)


# ---- Sample Size for Means ----

def sample_size_mean(
    sigma: float, margin: float = 0.05, z: float = 1.96, N: Optional[int] = None
) -> int:
    """Compute required sample size to estimate a mean."""

    if sigma <= 0:
        raise ValueError("sigma must be > 0")

    if margin <= 0:
        raise ValueError("margin must be > 0")

    # infinite population estimate
    n0 = (z**2 * sigma**2) / (margin**2)

    if N is not None:
        if N <= 0:
            raise ValueError("N must be positive")
        n = n0 / (1 + (n0 - 1) / N)
        return min(ceil(n), N)

    return ceil(n0)
