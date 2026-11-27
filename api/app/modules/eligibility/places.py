"""Recognizing US states and countries, so "OH" and "Ohio" compare equal.

Only names we can recognize with certainty are canonicalized. The engine
treats anything unrecognized as "unknown" (and asks), never as "not met".
"""

US_STATES: dict[str, str] = {
    "AL": "Alabama",
    "AK": "Alaska",
    "AZ": "Arizona",
    "AR": "Arkansas",
    "CA": "California",
    "CO": "Colorado",
    "CT": "Connecticut",
    "DE": "Delaware",
    "DC": "District of Columbia",
    "FL": "Florida",
    "GA": "Georgia",
    "HI": "Hawaii",
    "ID": "Idaho",
    "IL": "Illinois",
    "IN": "Indiana",
    "IA": "Iowa",
    "KS": "Kansas",
    "KY": "Kentucky",
    "LA": "Louisiana",
    "ME": "Maine",
    "MD": "Maryland",
    "MA": "Massachusetts",
    "MI": "Michigan",
    "MN": "Minnesota",
    "MS": "Mississippi",
    "MO": "Missouri",
    "MT": "Montana",
    "NE": "Nebraska",
    "NV": "Nevada",
    "NH": "New Hampshire",
    "NJ": "New Jersey",
    "NM": "New Mexico",
    "NY": "New York",
    "NC": "North Carolina",
    "ND": "North Dakota",
    "OH": "Ohio",
    "OK": "Oklahoma",
    "OR": "Oregon",
    "PA": "Pennsylvania",
    "RI": "Rhode Island",
    "SC": "South Carolina",
    "SD": "South Dakota",
    "TN": "Tennessee",
    "TX": "Texas",
    "UT": "Utah",
    "VT": "Vermont",
    "VA": "Virginia",
    "WA": "Washington",
    "WV": "West Virginia",
    "WI": "Wisconsin",
    "WY": "Wyoming",
    "PR": "Puerto Rico",
    "GU": "Guam",
    "VI": "U.S. Virgin Islands",
    "AS": "American Samoa",
    "MP": "Northern Mariana Islands",
}

_STATE_LOOKUP: dict[str, str] = {}
for _code, _name in US_STATES.items():
    _STATE_LOOKUP[_code.lower()] = _name
    _STATE_LOOKUP[_name.lower()] = _name
_STATE_LOOKUP.update(
    {
        "washington dc": "District of Columbia",
        "washington d.c.": "District of Columbia",
        "d.c.": "District of Columbia",
        "us virgin islands": "U.S. Virgin Islands",
    }
)

_COUNTRY_ALIASES: dict[str, str] = {
    "us": "united states",
    "u.s.": "united states",
    "usa": "united states",
    "u.s.a.": "united states",
    "united states of america": "united states",
    "america": "united states",
    "uk": "united kingdom",
    "u.k.": "united kingdom",
    "great britain": "united kingdom",
    "britain": "united kingdom",
}


def _clean(text: str) -> str:
    """ "  State of  New York " -> "new york"; "Ohio State" -> "ohio"."""
    lowered = " ".join(text.split()).lower()
    return lowered.removeprefix("state of ").removesuffix(" state")


def canonical_state(text: str) -> str | None:
    """ "oh", "Ohio", "State of Ohio" -> "Ohio"; unknown text -> None."""
    return _STATE_LOOKUP.get(_clean(text))


def canonical_country(text: str) -> str:
    """ "USA" -> "united states"; other names are lowercased as written."""
    cleaned = " ".join(text.split()).lower().removeprefix("the ")
    return _COUNTRY_ALIASES.get(cleaned, cleaned)
