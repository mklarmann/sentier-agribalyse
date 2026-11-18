"""What a run kept of itself, for a page to show: its lines and its own account.

`transcript` runs a command and keeps every line it prints, with the time of each line.
`summary` is the file a run writes about itself: its steps, the figures of each, what blocks
its result. `scripts/last_run.py` reads both, and `scripts/sitebuild/lastrun.py` shows them.
`before_after` is the file a run may write beside them when it changed data: the results of
the same items before and after, compared. `scripts/sitebuild/beforeafter.py` shows it on a
page of its own.

Nothing here knows a dataset, a provider or a tool. Standard library only.
"""
