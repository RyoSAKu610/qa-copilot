from __future__ import annotations

from qa_copilot.models import Listing
from qa_copilot.policy import AccessMode, PolicyError, discoverable_source_ids, effective

from .sources import REGISTRY


def run_discover(
    source_ids: list[str] | None,
    limit: int,
    user_enabled: dict[str, bool] | None = None,
) -> tuple[list[Listing], list[str]]:
    wanted = source_ids or discoverable_source_ids(user_enabled)
    listings: list[Listing] = []
    errors: list[str] = []
    for sid in wanted:
        policy = effective(sid, user_enabled)
        if policy.access is AccessMode.DISABLED:
            errors.append(f"{sid}: disabled")
            continue
        if policy.access is not AccessMode.OFFICIAL_API:
            errors.append(f"{sid}: not an official API source (use `inbox add`)")
            continue
        fetcher = REGISTRY.get(sid)
        if fetcher is None:
            errors.append(f"{sid}: no fetcher implemented")
            continue
        try:
            listings.extend(fetcher(limit))
        except Exception as exc:  # noqa: BLE001 — keep other sources going
            errors.append(f"{sid}: {exc}")
    if not listings and errors:
        raise PolicyError("discover failed:\n" + "\n".join(errors))
    return listings, errors
