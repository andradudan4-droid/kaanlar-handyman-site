"""Render the Flask pages to plain HTML for Cloudflare.

Run from the repo root after changing any page in app.py:
    python3 tools/build_static.py
"""
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import app as site  # noqa: E402

OUT = ROOT / "public"
PAGES = {"/": "index.html", "/services": "services.html", "/gallery": "gallery.html",
         "/contact": "contact.html", "/privacy-policy": "privacy-policy.html", "/terms": "terms.html"}


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    client = site.app.test_client()
    for path, name in PAGES.items():
        res = client.get(path)
        assert res.status_code == 200, (path, res.status_code)
        (OUT / name).write_text(res.get_data(as_text=True))
    for path in ("/sitemap.xml", "/robots.txt"):
        (OUT / path[1:]).write_text(client.get(path).get_data(as_text=True))

    # The pages the contact form shows after a POST (the worker serves these).
    variants = OUT / "_contact"
    variants.mkdir()
    with site.app.test_request_context("/contact"):
        (variants / "sent.html").write_text(site.page("Contact", site.contact_body(sent=True)))
        (variants / "missing.html").write_text(site.page("Contact", site.contact_body(error="Please fill in every field.")))
        (variants / "busy.html").write_text(site.page("Contact", site.contact_body(error="Too many requests — please wait a moment or call us directly.")))

    tracked = subprocess.run(["git", "ls-files", "static"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
    for rel in tracked:
        dest = OUT / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / rel, dest)
    for extra in ("_headers", "_redirects"):
        shutil.copy(ROOT / "cloudflare" / extra, OUT / extra)
    print("built", len(list(OUT.rglob("*"))), "files into public/")


if __name__ == "__main__":
    main()
