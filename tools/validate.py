def validate_coordinates(lat, lon):
    """Sanity-check a lat/lon pair before it's used in an API call. Returns an error message
    string if something looks wrong, or None if it looks fine.

    Catches a real failure mode observed in testing: the model occasionally copies the
    latitude value into the longitude argument (or vice versa) when comparing multiple
    candidate destinations in the same turn.
    """
    if not (-90 <= lat <= 90):
        return f"lat={lat} is out of range (-90 to 90) -- this isn't a valid latitude."
    if not (-180 <= lon <= 180):
        return f"lon={lon} is out of range (-180 to 180) -- this isn't a valid longitude."
    if lat == lon:
        return (
            f"lat and lon are both {lat} -- a real place's latitude and longitude are essentially "
            "never identical, so this looks like a copy/paste mistake. Re-call geocode_location for "
            "this place and use its exact lat/lon values."
        )
    return None
