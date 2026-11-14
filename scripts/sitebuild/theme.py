"""The index colour of a dataset's site: what tells one Sentier dataset site from another.

Every Sentier dataset site has the same frame: the logo, the paper, the type. One colour of
its own marks which dataset a reader is on: a band over the masthead, the current item of the
navigation, headings, links, buttons, the focus ring, and the one dark surface of the site.

site/config.json sets it under "index": one colour, or the colour with the three that go
with it.

    "index": "#3e5c76"
    "index": {"color": "#3e5c76", "dark": "#2b4257", "tint": "#dfe7ee", "soft": "#93adc2"}

Without it the stylesheet's own values hold (the brand's green) and nothing is written on a
page. With it the build works out what is not given, checks every pair of colours that will
carry text, and refuses a colour that fails: whether a colour can be read is a number, so it
is computed here and not judged by eye.

    color   text, links, headings, buttons     on the paper and on a card: 4.5 to 1 or more;
                                               white on it: 4.5 to 1 or more
    dark    the dark surface, strong text      the stage's text on it: 7 to 1 or more;
                                               on the tint: 4.5 to 1 or more
    tint    a quiet fill behind dark text
    soft    marks and underlines, never text   on the dark surface: 3 to 1 or more

The hue of the colour is not where the two signals of the site are (amber for waiting,
red-brown for failed): a reader must not take the site's colour for a status.

Standard library only.
"""

import colorsys
import re

HEX = re.compile(r"#[0-9a-fA-F]{6}")
PAPER, SURFACE, WHITE, BLACK = "#f0eee1", "#fbfaf5", "#ffffff", "#000000"
ON = "#f0eee1"                       # the text of the dark surface
KEYS = ("color", "dark", "tint", "soft")
SIGNAL_HUES = (345.0, 60.0)          # from red-brown through amber, in degrees
GREY_BELOW = 0.12                    # a colour this weak has no hue to mistake
TEXT, STRONG, MARK = 4.5, 7.0, 3.0   # contrast ratios: text, the stage's text, a mark
ARROW = ("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 12 12'%3E%3Cpath "
         "d='M3.5 1.5h7v7M10 2 1.8 10.2' fill='none' stroke='%23{hex}' stroke-width='1.7' "
         "stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E")
CHEVRON = ("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 12 8'%3E%3Cpath "
           "d='M1.5 1.5 6 6l4.5-4.5' fill='none' stroke='%23{hex}' stroke-width='1.8' "
           "stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E")


def channels(colour):
    return tuple(int(colour[n:n + 2], 16) for n in (1, 3, 5))


def luminance(colour):
    """Relative luminance, as WCAG 2 defines it."""
    def linear(value):
        value /= 255
        return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4

    red, green, blue = (linear(v) for v in channels(colour))
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast(one, other):
    """The contrast ratio of two colours, 1 to 21."""
    lighter, darker = sorted((luminance(one), luminance(other)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def mix(colour, other, share):
    """`share` of `colour` with the rest of `other`."""
    return "#" + "".join(
        f"{round(a * share + b * (1 - share)):02x}" for a, b in zip(channels(colour), channels(other))
    )


def hue(colour):
    """(degrees, saturation) of a colour."""
    h, _, s = colorsys.rgb_to_hls(*(v / 255 for v in channels(colour)))
    return h * 360, s


def darker(colour):
    """The colour, darkened until the stage's text reads on it at 7 to 1."""
    for share in (0.76, 0.7, 0.64, 0.58, 0.52, 0.46, 0.4, 0.34):
        dark = mix(colour, BLACK, share)
        if contrast(ON, dark) >= STRONG:
            return dark
    return mix(colour, BLACK, 0.3)


def grey(dark, least, against):
    """A grey of the dark surface: its text colour with as much of the surface in it as still
    reads at `least` to 1 against `against`."""
    for share in (0.5, 0.56, 0.62, 0.68, 0.74, 0.8, 0.86, 0.92, 1.0):
        made = mix(ON, dark, share)
        if contrast(made, against) >= least:
            return made
    return ON


def read(config):
    """The colours of a site from its configuration, checked: None when it sets none.
    Raises ValueError, naming every pair that can't be read, for a colour that fails."""
    value = config.get("index")
    if value is None:
        return None
    if isinstance(value, str):
        value = {"color": value}
    if not isinstance(value, dict) or "color" not in value or set(value) - set(KEYS):
        raise ValueError('site/config.json: "index" is a colour, or {"color", "dark", "tint", "soft"}')
    for key, colour in value.items():
        if not isinstance(colour, str) or not HEX.fullmatch(colour):
            raise ValueError(f'site/config.json: index.{key} is a colour written as "#rrggbb"')
    value = {key: colour.lower() for key, colour in value.items()}
    colour = value["color"]
    dark = value.get("dark") or darker(colour)
    tint = value.get("tint") or mix(colour, WHITE, 0.17)
    soft = value.get("soft") or mix(colour, WHITE, 0.55)

    wrong = []

    def needs(text, ground, least, what):
        ratio = contrast(text, ground)
        if ratio < least:
            wrong.append(f"{what}: {text} on {ground} is {ratio:.2f} to 1, and {least:g} to 1 is needed")

    needs(colour, PAPER, TEXT, "text in the index colour on the paper")
    needs(colour, SURFACE, TEXT, "text in the index colour on a card")
    needs(WHITE, colour, TEXT, "white text on a button in the index colour")
    needs(ON, dark, STRONG, "the text of the dark surface")
    needs(dark, tint, TEXT, "dark text on the tint")
    needs(soft, dark, MARK, "a mark on the dark surface")
    degrees, strength = hue(colour)
    low, high = SIGNAL_HUES
    if strength >= GREY_BELOW and (degrees >= low or degrees <= high):
        wrong.append(
            f"the hue of {colour} is {degrees:.0f} degrees, where the signals for waiting and failed are "
            f"({low:g} to {high:g} degrees): a reader would take the site's colour for a status"
        )
    if wrong:
        raise ValueError("site/config.json: the index colour can't be used.\n  " + "\n  ".join(wrong))

    well = mix(dark, BLACK, 0.62)
    return {
        "index": colour, "index-dark": dark, "index-soft": soft, "index-tint": tint,
        "stage-soft": grey(dark, STRONG, dark),
        "stage-quiet": grey(dark, TEXT, dark),
        "stage-dim": grey(dark, TEXT, well),
        "stage-clock": grey(dark, MARK + 0.5, well),
        "stage-well": well,
        "arrow-ext": f'url("{ARROW.format(hex=colour[1:])}")',
        "chevron": f'url("{CHEVRON.format(hex=colour[1:])}")',
    }


def rule(theme):
    """The one rule a page of a site with an index colour carries, for the stylesheet's tokens."""
    return ":root{" + "".join(f"--{name}:{value};" for name, value in theme.items()) + "}"
