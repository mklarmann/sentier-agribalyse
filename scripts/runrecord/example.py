"""A made-up review with every class in it: three tiny builds, two causes, one comparison.

Every repository that shows a comparison runs its page and its checks on this example, so
that a reader of any of them meets the same six classes with the same meaning. Nothing in
it is anybody's data.

- `base` and `base again` are two builds of the same state. They differ in water use of
  one product by 5 %: that is the noise.
- `changed` is the base plus two causes. `fix-1` claims that two products go down in climate
  change by at most 30 %. `fix-2` claims that one product moves in water use.

What the comparison of `base` and `changed` must find, one value of each class:

    as claimed            Wheat, climate change: down 10 %, inside fix-1
    off claim             Rice, climate change: down 50 %, further than fix-1 says
    not claimed           Barley, climate change: up 20 %, and no claim covers it
    within noise          Oats, water use: up 2.5 %, less than the two base builds differ
    claimed, not moved    Maize, water use: fix-2 names it, and it did not move
    unchanged             everything else
"""

from . import before_after, review

CLIMATE, WATER = "x:climate", "x:water"
INDICATORS = [(CLIMATE, "Climate change", "Climate", "kg CO2 eq"), (WATER, "Water use", None, "m3")]
NAMES = {
    "p1": {"name": "Wheat", "place": "FR"},
    "p2": {"name": "Maize", "place": "FR"},
    "p3": {"name": "Barley", "place": "DE"},
    "p4": {"name": "Oats", "place": "DE"},
    "p5": {"name": "Rice", "place": "IT"},
    "p6": {"name": "Rye", "place": "DE"},
}
BASE = {
    CLIMATE: {"p1": 10.0, "p2": 5.0, "p3": 2.0, "p4": 1.0, "p5": 8.0, "p6": 3.0},
    WATER: {"p1": 1.0, "p2": 2.0, "p3": 3.0, "p4": 4.0, "p5": 5.0, "p6": 6.0},
}
BASE_AGAIN = {CLIMATE: dict(BASE[CLIMATE]), WATER: BASE[WATER] | {"p4": 4.2}}
CHANGED = {
    CLIMATE: BASE[CLIMATE] | {"p1": 9.0, "p5": 4.0, "p3": 2.4},
    WATER: BASE[WATER] | {"p4": 4.1},
}
#: The class each value must get; every value that is not named here is unchanged.
EXPECTED = {
    (CLIMATE, "p1"): before_after.AS_CLAIMED,
    (CLIMATE, "p5"): before_after.OFF_CLAIM,
    (CLIMATE, "p3"): before_after.NOT_CLAIMED,
    (WATER, "p4"): before_after.NOISE,
    (WATER, "p2"): before_after.NOT_MOVED,
}
PAGE = "base-to-changed.html"


def causes():
    return [
        before_after.cause(
            "fix-1",
            kind="correction",
            title="Two cereals take the corrected fertiliser amount.",
            claim=before_after.claim(
                "Wheat and rice go down in climate change, by 30 % at most. Nothing else moves.",
                [before_after.scope([CLIMATE], {"p1", "p5"}, "down", 0.3)],
            ),
        ),  # fmt: skip
        before_after.cause(
            "fix-2",
            kind="correction",
            title="Maize takes the irrigation of its region.",
            claim=before_after.claim(
                "Maize moves in water use.", [before_after.scope([WATER], {"p2"})]
            ),
        ),  # fmt: skip
    ]


def comparison(**more):
    """The comparison of `base` and `changed`, as a repository's reader would write it."""
    values = {key: {i: (BASE[key][i], CHANGED[key][i]) for i in BASE[key]} for key in BASE}
    noise = {key: before_after.noise_of(BASE[key], BASE_AGAIN[key]) for key in BASE}
    return before_after.compare(
        "The base and the two fixes",
        ("Base", "The state before, built once."),
        ("Base with both fixes", None),
        ("product", "products"),
        INDICATORS,
        values,
        names=NAMES,
        floors=0.0,
        noise={"between": ("base", "base again"), "by": noise, "note": None},
        causes=causes(),
        item_causes={"p1": ["fix-1"], "p5": ["fix-1"]},
        **more,
    )


def index(found=None):
    """The index of the review: three builds, two causes, and the one pair that was compared.
    No pair isolates one fix alone, which the page must say when one is chosen."""
    found = found or comparison()
    return review.index(
        "The two fixes, reviewed",
        [
            review.run("base", "Base", identity={"commit": "0000000", "built": "1 January 2026"}),
            review.run("base-again", "Base, built again", replica_of="base", reproducible=False),
            review.run("changed", "Base with both fixes", ["fix-1", "fix-2"]),
        ],
        [
            review.cause(c["id"], kind=c["kind"], title=c["title"], claim=c["claim"])
            for c in found["causes"]
        ],
        [review.pair("base", "changed", page=PAGE, classes=review.totals(found))],
        notes=["A made-up example: nobody's data."],
    )
