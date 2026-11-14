"""The page templates of the public site, one function per component.

    text.py           escaping, dates, counts, link labels
    prose.py          Markdown: prose pages, record text, tables, step lists, markers
    shell.py          the page frame: head, masthead, footer, redirect, page not found
    status.py         the status of a finding or contribution: tracker, meter, filter chips
    findings.py       a finding as a row, the findings list and its index, the finding page
    contributions.py  a contribution as a row, the list, the contribution page
    overview.py       the overview
    pages.py          feedback, releases, datasets, changes and feed, housekeeping, sitemap
    data.py           the machine-readable outputs

Every function takes the `Site` of scripts/build_site.py as its first argument and returns
HTML. `up` is the path from the page being written back to the site root ("" or "../").
"""
