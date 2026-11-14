"""The frame of every page: head, masthead, footer; and the pages that are only a frame."""

import json

from . import theme
from .text import day, esc, ext

NAV_SCRIPT = ("<script>(function(){var a=document.querySelector('.nav [aria-current]');"
              "if(a&&a.scrollIntoView)a.scrollIntoView({block:'nearest',inline:'center'});})();</script>")


def shell(site, title, body, current, up="", page=None, description=None, head=""):
    """One page. `current` is the navigation item to mark, `page` the address of this page
    from the site root (for the canonical link), `up` the way back to the root."""
    c = site.config
    home = page == "index.html"
    full = c["home_title"] if home else f'{title} · {c["title_suffix"]}'
    described = description or c["description"]
    nav = "".join(
        f'<a href="{up}{href}"' + (' aria-current="page"' if href == current else "") + f">{esc(label)}</a>"
        for href, label in c["nav"]
    )
    footer = "".join(f'<a href="{up}{href}">{esc(label)}</a>' for href, label in c["footer"])
    footer += ext(site.repo, "Repository") + ext(f"{site.repo}/issues/new/choose", "Open an issue")
    if c.get("sibling_url"):
        footer += ext(c["sibling_url"], f'Other datasets: {esc(c["sibling_name"])}')
    notice = (
        '<aside class="preview-notice" aria-label="Preview"><div class="wrap"><strong>Preview.</strong> '
        "This is a proposed version of the site, not the published one. "
        f'{ext(site.preview_url, "See the pull request")}</div></aside>'
        if site.preview_url else ""
    )
    if not notice and getattr(site, "elsewhere", False):
        # A copy that another repository builds (a fork) is not the site of this workspace.
        notice = (
            '<aside class="preview-notice" aria-label="Preview"><div class="wrap"><strong>Preview.</strong> '
            f"This copy of the site is built from <code>{esc(site.built_by)}</code>. It is not the published site. "
            f'{ext("https://github.com/" + site.built_by, "See where it is built")}</div></aside>'
        )
    built = f"Built on {day(site.built, long=True)}" + (f" from revision {esc(site.revision)}" if site.revision else "") + "."
    if site.issues_source:
        built += " Comment counts were read from GitHub at that time."
    p = esc(site.provider)
    canonical = f'<link rel="canonical" href="{esc(c["site_url"] + page)}"><meta property="og:url" content="{esc(c["site_url"] + page)}">' if page else ""
    # A site with an index colour of its own says so on every page: the stylesheet is the same
    # file on every dataset site, and this one rule sets its tokens.
    colours = getattr(site, "theme", None)
    marked = ' class="has-index"' if colours else ""
    tokens = f"<style>{theme.rule(colours)}</style>" if colours else ""
    tint = colours["index"] if colours else "#3c5343"
    return f'''<!doctype html>
<html lang="en"{marked}><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(full)}</title><meta name="description" content="{esc(described)}"><meta name="theme-color" content="{tint}">{canonical}<meta property="og:title" content="{esc(title if not home else full)}"><meta property="og:description" content="{esc(described)}"><meta property="og:type" content="website"><link rel="icon" href="{up}assets/favicon-32x32.png" type="image/png"><link rel="preload" href="{up}assets/nunito-latin.woff2" as="font" type="font/woff2" crossorigin><link rel="stylesheet" href="{up}style.css">{tokens}<link rel="alternate" type="application/atom+xml" title="Changes to the findings" href="{up}feed.xml">{head}</head><body>
<a class="skip" href="#main">Skip to content</a>
<header class="masthead"><div class="wrap masthead-in"><a class="logo" href="https://www.d-d-s.ch/"><img src="{up}assets/dds-logo.svg" alt="Départ de Sentier" width="120" height="56"></a><a class="site-name" href="{up}index.html"><strong>{esc(site.dataset)}</strong><span>Community workspace</span></a><nav class="nav" aria-label="Main navigation">{nav}</nav>{ext(site.repo, "GitHub", "repo ext")}</div></header>
{notice}<main id="main">{body}</main>
<footer class="footer"><div class="wrap footer-in"><p class="footer-about"><strong>A Sentier community workspace.</strong> This site is not run by {p}, and nothing on it implies {p}'s endorsement. {p} publishes the {esc(site.dataset)} inventory database under its own Terms of Use.</p><nav class="footer-links" aria-label="Footer">{footer}</nav><p class="footer-build">{built} <a href="https://github.com/Depart-de-Sentier/dds-logo">Logo</a> by Sylvain Prevost · <a href="https://www.d-d-s.ch/">Départ de Sentier</a></p></div></footer>
{NAV_SCRIPT}
</body></html>
'''


def contents(sections, beside=""):
    """"On this page", beside a prose page with three or more sections; and what else the
    page puts beside its text."""
    if len(sections) < 3 and not beside:
        return ""
    listed = (
        '<div class="toc-list"><p class="card-label">On this page</p><ul>'
        + "".join(f'<li><a href="#{esc(anchor)}">{name}</a></li>' for anchor, name in sections)
        + "</ul></div>"
    ) if len(sections) >= 3 else ""
    return f'<aside class="rail toc" aria-label="On this page">{listed}{beside}</aside>'


def prose_page(site, doc, body, sections, listing=False, up="", opening="", beside=""):
    """A Markdown page. A page that holds a list of records takes the full width; any other
    keeps the reading width and gets its contents beside it. `opening` is what stands above
    both, over the full width: the page's title and the block that opens it."""
    top = f'<div class="wrap page-opening"><div class="prose wide">{opening}</div></div>' if opening else ""
    after = " after-opening" if opening else ""
    if listing:
        inner = f'{top}<div class="wrap page{after}"><article class="prose wide">{body}</article></div>'
    else:
        inner = f'{top}<div class="wrap page with-rail{after}"><article class="prose">{body}</article>{contents(sections, beside)}</div>'
    return shell(site, doc["title"], inner, doc.get("nav", doc["page"]), up=up, page=doc["page"],
                 description=doc.get("description"))


def generated_page(site, title, body, page, current=None, up="", description=None, head=""):
    """A page the build writes without a Markdown source: full width, same frame."""
    inner = f'<div class="wrap page"><article class="prose wide">{body}</article></div>'
    return shell(site, title, inner, current or page, up=up, page=page, description=description, head=head)


def lookup(site, up="", field="lookup"):
    """The lookup field: a dataset code (where the datasets have one), a finding number or a
    word, answered by the findings list."""
    what = "a dataset code, a finding number or a word" if site.code_pattern else "a finding number or a word"
    return (
        f'<form class="lookup" action="{up}findings.html" method="get" role="search">'
        f'<label for="{field}">Look up {what}</label>'
        f'<div class="lookup-row"><input id="{field}" name="q" type="search" placeholder="For example {esc(site.lookup_example)}" '
        'autocomplete="off" spellcheck="false"><button class="button" type="submit">Look up</button></div></form>'
    )


def redirect(site, target, label, up=""):
    """An old address: it leads on at once, keeps a fragment, and says where it leads."""
    here = up + target
    return (
        '<!doctype html>\n<html lang="en"><head><meta charset="utf-8"><title>Moved: '
        f'{esc(label)}</title><meta name="robots" content="noindex"><link rel="canonical" href="{esc(site.config["site_url"] + target)}">'
        f'<meta http-equiv="refresh" content="0; url={esc(here)}">'
        f"<script>location.replace({json.dumps(here)} + location.hash);</script></head>"
        f'<body><p>This page has moved. <a href="{esc(here)}">Continue to {esc(label)}</a>.</p></body></html>\n'
    )


def not_found(site):
    """GitHub Pages serves this page for any missing address, at any depth: its links start
    at the root of the site."""
    up = site.root_path
    body = (
        '<div class="wrap page"><article class="prose"><h1>Page not found</h1>'
        "<p>This address has no page. It may have moved. Findings and contributions keep their numbers, "
        "so you can find them in the lists.</p>"
        + lookup(site, up)
        + f'<p class="actions"><a class="arrow" href="{up}findings.html">All findings</a>'
        f'<a class="arrow" href="{up}feedback.html">Feedback to {esc(site.provider)}</a>'
        f'<a class="arrow" href="{up}contributions.html">All contributions</a>'
        f'<a class="arrow" href="{up}index.html">Overview</a></p></article></div>'
    )
    return shell(site, "Page not found", body, None, up=up, description="This address has no page.")
