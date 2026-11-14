"""A small client for the GitHub REST API, for scripts/intake.py and scripts/sync.py.

Standard library only. It sends and receives JSON and nothing else: no value is ever put into
a shell command. The token comes from the environment and is sent only to the API address.

    GitHub(repository, token, api, transport)   a client for one repository ("owner/name")
    .get(path) .post(path, body) .put(...) .patch(...) .delete(...)   one request; returns the JSON
    .pages(path)                                 every item of a listed resource, a hundred a page
    .location(path)                              where a path redirects to; the redirect is not followed
    .comment_once(issue, marker, text)           a comment that is posted once, however often it is asked for
    .remaining                                   requests left in the rate limit window, if known
    ApiError, NotFound, RateLimited              what a request can raise

`transport` is how a request leaves the process: (method, url, headers, body) -> (status,
headers, body). The tests pass recorded responses; nothing in the tests reaches the network.
"""

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.github.com"
# The workflows may read GITHUB_API_URL from the runner; a token is only ever sent over https,
# or to this machine, where the dry runs of the workflows listen.
ALLOWED_API = re.compile(r"https://[A-Za-z0-9.-]+(/[A-Za-z0-9./-]*)?|http://(127\.0\.0\.1|localhost)(:[0-9]+)?")
REPOSITORY = re.compile(r"[A-Za-z0-9._-]+/[A-Za-z0-9._-]+")


class ApiError(Exception):
    """A request the API refused. The message names the request and never holds the token."""

    def __init__(self, method, path, status, message=""):
        self.method, self.path, self.status, self.detail = method, path, status, message
        super().__init__(f"{method} {path}: HTTP {status}" + (f" ({message})" if message else ""))


class NotFound(ApiError):
    pass


class RateLimited(ApiError):
    """The rate limit is used up. Whatever was written before stays written; a later run goes on."""


def plain(text, limit=200):
    """Text from outside, made safe to print in a job log or to put in a message.

    A runner reads commands from what a step prints ("::name::"), and Markdown turns "@name"
    into a notification. One line, a short alphabet, and neither of the two.
    """
    text = re.sub(r"[^A-Za-z0-9 .,;:()/#'\"_+=\[\]-]", " ", str(text))
    text = re.sub(r"\s+", " ", text).replace("::", ": :").strip()
    return text if len(text) <= limit else text[:limit] + "…"


def http(method, url, headers, body):
    """One request with urllib: (status, headers with lower-case names, body bytes)."""
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, {k.lower(): v for k, v in response.headers.items()}, response.read()
    except urllib.error.HTTPError as error:
        return error.code, {k.lower(): v for k, v in error.headers.items()}, error.read()


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def http_once(method, url, headers, body):
    """One request that follows no redirect: (status, headers, body), a 302 included."""
    opener = urllib.request.build_opener(_NoRedirect)
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with opener.open(request, timeout=30) as response:
            return response.status, {k.lower(): v for k, v in response.headers.items()}, response.read()
    except urllib.error.HTTPError as error:
        return error.code, {k.lower(): v for k, v in error.headers.items()}, error.read()


class GitHub:
    def __init__(self, repository, token=None, api=None, transport=None):
        api = (api or os.environ.get("GITHUB_API_URL") or API).rstrip("/")
        if not ALLOWED_API.fullmatch(api):
            raise ValueError("the API address must be https, or http on this machine")
        if not REPOSITORY.fullmatch(repository or ""):
            raise ValueError("the repository is named owner/name")
        self.api, self.repository, self.token = api, repository, token
        self.transport = transport or http
        self.once = transport or http_once
        self.remaining = None
        self.requests = 0

    def request(self, method, path, body=None):
        """One request to a path below the repository, such as "/issues/48/labels"."""
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "sentier-bafu-automation",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        url = f"{self.api}/repos/{self.repository}{path}"
        status, answer, raw = self.transport(method, url, headers, data)
        self.requests += 1
        if str(answer.get("x-ratelimit-remaining", "")).isdigit():
            self.remaining = int(answer["x-ratelimit-remaining"])
        try:
            parsed = json.loads(raw) if raw else None
        except ValueError:
            parsed = None
        if status < 300:
            return parsed
        message = plain(parsed.get("message", "")) if isinstance(parsed, dict) else ""
        if status in (403, 429) and (
            answer.get("x-ratelimit-remaining") == "0" or "retry-after" in answer or "rate limit" in message.lower()
        ):
            raise RateLimited(method, path, status, message)
        # 410 is what an issue answers after it was deleted.
        raise (NotFound if status in (404, 410) else ApiError)(method, path, status, message)

    def get(self, path):
        return self.request("GET", path)

    def location(self, path):
        """Where a path sends its reader on to (the file of an artifact), or None.

        GitHub answers such a path with the address of the file at its storage, good for a
        minute. The token goes to the API and never to that address: the redirect is not
        followed here, and whoever reads the address sends it no header of ours.
        """
        headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28",
                   "User-Agent": "sentier-bafu-automation"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        status, answer, _ = self.once("GET", f"{self.api}/repos/{self.repository}{path}", headers, None)
        self.requests += 1
        if status in (301, 302, 303, 307, 308) and str(answer.get("location", "")).startswith("https://"):
            return answer["location"]
        if status in (401, 403, 404, 410):
            return None
        raise ApiError("GET", path, status)

    def post(self, path, body):
        return self.request("POST", path, body)

    def put(self, path, body):
        return self.request("PUT", path, body)

    def patch(self, path, body):
        return self.request("PATCH", path, body)

    def delete(self, path):
        return self.request("DELETE", path)

    def comment_once(self, issue, marker, text):
        """Post a comment unless one with this marker is already there. True when posted.

        The marker is a hidden line at the top of the comment. It makes every run repeatable:
        the same event, or the same change of status, is never announced twice.
        """
        tag = f"<!-- {marker} -->"
        for comment in self.pages(f"/issues/{issue}/comments"):
            if tag in (comment.get("body") or ""):
                return False
        self.post(f"/issues/{issue}/comments", {"body": f"{tag}\n{text}"})
        return True

    def pages(self, path):
        """Every item of a list, a hundred a page, until a page comes back short."""
        page = 1
        while True:
            joiner = "&" if "?" in path else "?"
            batch = self.get(f"{path}{joiner}per_page=100&page={page}") or []
            yield from batch
            if len(batch) < 100:
                return
            page += 1


def quoted(name):
    """A label or branch name as part of a path."""
    return urllib.parse.quote(name, safe="")


def repository_slug(url):
    """owner/name from https://github.com/owner/name."""
    return url.rstrip("/").split("github.com/")[-1]
