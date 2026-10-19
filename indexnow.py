#!/usr/bin/env python3
"""Tell Bing (and the other IndexNow search engines) which kogroofs.com pages changed.

Runs on GitHub (see .github/workflows/hail-data.yml):
  - after each upload of site files, for the pages that upload changed
  - after the nightly hail job, when the hail report changed

Usage: python3 indexnow.py FILE_LIST
FILE_LIST is a text file with one changed file path per line. Anything
that isn't a public .html page is skipped. The key file
90f39845d69bb572540c4aa6f193f579.txt must stay in the site's top folder.

Uses only the Python standard library.
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request

HOST = "kogroofs.com"
SITE = "https://" + HOST
KEY = "90f39845d69bb572540c4aa6f193f579"
ENDPOINT = "https://api.indexnow.org/indexnow"
ROOT = os.path.dirname(os.path.abspath(__file__))
SKIP = {"404.html"}
WAIT_SECONDS = 120  # give GitHub Pages time to publish before Bing looks


def page_urls(list_file):
    urls = []
    with open(list_file, encoding="utf-8") as f:
        for line in f:
            path = line.strip()
            if not path.endswith(".html") or "/" in path:
                continue
            if path in SKIP or path.startswith("google"):
                continue
            if not os.path.exists(os.path.join(ROOT, path)):
                continue
            url = SITE + "/" if path == "index.html" else f"{SITE}/{path}"
            if url not in urls:
                urls.append(url)
    return urls


def main():
    if len(sys.argv) != 2 or not os.path.exists(sys.argv[1]):
        print("No list of changed pages; nothing to send.")
        return 0
    urls = page_urls(sys.argv[1])
    if not urls:
        print("No changed pages to send.")
        return 0
    if not os.path.exists(os.path.join(ROOT, KEY + ".txt")):
        print(f"The key file {KEY}.txt is missing from the site; not sending.")
        return 0
    if os.environ.get("GITHUB_ACTIONS"):
        time.sleep(WAIT_SECONDS)
    body = json.dumps({"host": HOST, "key": KEY, "keyLocation": f"{SITE}/{KEY}.txt",
                       "urlList": urls}).encode("utf-8")
    req = urllib.request.Request(ENDPOINT, data=body, method="POST",
                                 headers={"Content-Type": "application/json; charset=utf-8"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            print(f"Sent {len(urls)} page(s) to IndexNow: HTTP {r.status}")
    except urllib.error.HTTPError as e:
        print(f"IndexNow answered HTTP {e.code} for {len(urls)} page(s)")
    except Exception as e:  # network trouble: try again next time
        print(f"Could not reach IndexNow ({e})")
    for u in urls:
        print("  " + u)
    return 0


if __name__ == "__main__":
    sys.exit(main())
