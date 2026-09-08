def _primary_kind(place):
    kinds = place.get("kinds") or ""
    return kinds.split(",")[0] if kinds else "unknown"


def rerank_and_narrow(places, limit=5, max_per_kind=2):
    """Narrow a broad candidate list down to `limit` results, favoring higher-importance
    places (OpenTripMap's 'rate' field) while keeping category diversity so results aren't
    all the same kind of place.
    """
    ranked = sorted(places, key=lambda p: (-p.get("rate", 0), p.get("distance_m", 0)))

    selected = []
    kind_counts = {}
    leftovers = []

    for place in ranked:
        kind = _primary_kind(place)
        if kind_counts.get(kind, 0) < max_per_kind:
            selected.append(place)
            kind_counts[kind] = kind_counts.get(kind, 0) + 1
        else:
            leftovers.append(place)
        if len(selected) >= limit:
            return selected[:limit]

    for place in leftovers:
        if len(selected) >= limit:
            break
        selected.append(place)

    return selected[:limit]
