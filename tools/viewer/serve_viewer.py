#!/usr/bin/env python3
"""
serve_viewer.py  -  Local server for Delulu Benchmark Viewer with Docker API.

Serves viewer.html and provides REST endpoints for Docker operations:
  GET  /api/health       -> Check if Docker is available
  POST /api/image-check  -> Check if an image is pulled locally
  POST /api/pull         -> Pull a Docker image
  POST /api/verify       -> Run verification command

Review endpoints:
  POST /api/load-csv     -> Load a CSV file from the output/ directory
  POST /api/save-review  -> Save review state to a JSON sidecar file
  POST /api/load-review  -> Load review state from a JSON sidecar file
  POST /api/export-csv   -> Export reviewed CSV with accept/edit columns

Usage:
    python serve_viewer.py
    python serve_viewer.py --port 9000
"""
from __future__ import annotations

import argparse
import csv
import http.server
import io
import json
import os
import re
import socketserver
import subprocess
import sys
import webbrowser
from urllib.parse import urlparse

STATIC_DIR = os.path.dirname(os.path.abspath(__file__))

# Image allowlist. Only image references whose first path component matches
# one of these prefixes can be pulled or executed by the viewer. Override
# with the DELULU_IMAGE_ALLOWLIST env var (comma-separated).
_DEFAULT_IMAGE_ALLOWLIST = (
    "delulubench/",                 # planned public Docker Hub org
    "mcr.microsoft.com/delulu/",    # planned public MCR namespace
)


def _image_allowlist() -> tuple[str, ...]:
    raw = os.environ.get("DELULU_IMAGE_ALLOWLIST")
    if raw:
        return tuple(p.strip() for p in raw.split(",") if p.strip())
    return _DEFAULT_IMAGE_ALLOWLIST


_IMAGE_REF_RE = re.compile(r"^[a-z0-9._\-/]+(:[a-zA-Z0-9._\-]+)?$")


def _is_image_allowed(image: str) -> bool:
    """Reject anything that is not a plain image reference matching the
    allowlist. Blocks image refs containing shell metacharacters, CLI
    flags, or untrusted registries."""
    if not image or not isinstance(image, str):
        return False
    if image.startswith("-"):
        return False  # would be parsed as a docker CLI flag
    if not _IMAGE_REF_RE.match(image):
        return False
    allow = _image_allowlist()
    return any(image.startswith(p) for p in allow)


class ViewerHandler(http.server.SimpleHTTPRequestHandler):
    """HTTP handler: serves static files + Docker API endpoints."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=STATIC_DIR, **kwargs)

    # ── Routing ──────────────────────────────────

    def do_GET(self):
        if not self._origin_ok():
            self.send_error(403, "Cross-origin request blocked")
            return
        path = self.path.split("?", 1)[0]
        if path == "/api/health":
            return self._api_health()
        if path == "/api/list-csvs":
            return self._api_list_csvs()
        return super().do_GET()

    def do_POST(self):
        if not self._origin_ok():
            self.send_error(403, "Cross-origin request blocked")
            return
        routes = {
            "/api/health": self._api_health,
            "/api/image-check": self._api_image_check,
            "/api/pull": self._api_pull,
            "/api/verify": self._api_verify,
            "/api/load-csv": self._api_load_csv,
            "/api/save-review": self._api_save_review,
            "/api/load-review": self._api_load_review,
            "/api/export-csv": self._api_export_csv,
        }
        handler = routes.get(self.path)
        if handler:
            return handler()
        self.send_error(404)

    def do_OPTIONS(self):
        if not self._origin_ok():
            self.send_error(403, "Cross-origin request blocked")
            return
        self.send_response(204)
        self._cors_headers()
        self.end_headers()

    # ── Helpers ──────────────────────────────────

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length))

    def _origin_ok(self) -> bool:
        """Reject cross-origin requests so a malicious page in another tab
        cannot CSRF the local Docker control endpoints.

        Same-origin browsers either omit the Origin header (true same-origin
        navigation) or send it equal to the viewer's own host. Any *other*
        Origin is rejected.
        """
        origin = self.headers.get("Origin")
        host = self.headers.get("Host", "")
        if origin is None:
            # Same-origin navigation / curl. Allow.
            return True
        try:
            origin_host = urlparse(origin).netloc
        except Exception:
            return False
        return origin_host == host

    def _json_response(self, data: dict, status: int = 200):
        body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def _cors_headers(self):
        # Echo only the request's Origin if same-origin; never use "*" so
        # cross-origin POSTs cannot drive the local Docker endpoints.
        origin = self.headers.get("Origin")
        host = self.headers.get("Host", "")
        if origin and urlparse(origin).netloc == host:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    @staticmethod
    def _docker(cmd: list[str], *, timeout: int = 300,
                stdin_data: str | None = None) -> tuple[int, str, str]:
        try:
            r = subprocess.run(
                cmd,
                input=stdin_data,
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding="utf-8",
                errors="replace",
            )
            return r.returncode, r.stdout or "", r.stderr or ""
        except subprocess.TimeoutExpired:
            return -1, "", f"Command timed out after {timeout}s"
        except FileNotFoundError:
            return -2, "", "docker executable not found"
        except Exception as e:
            return -1, "", str(e)

    def log_message(self, fmt, *args):
        # Only log API requests, skip static files
        if args and isinstance(args[0], str) and "/api/" in args[0]:
            return super().log_message(fmt, *args)

    # ── API Endpoints ────────────────────────────

    def _api_health(self):
        rc, _, _ = self._docker(["docker", "info"], timeout=10)
        self._json_response({"docker": rc == 0})

    def _api_image_check(self):
        body = self._read_json()
        image = body.get("image", "")
        if not image:
            return self._json_response({"error": "No image specified"}, 400)
        if not _is_image_allowed(image):
            return self._json_response(
                {"error": ("Image rejected: not in allowlist. "
                           "Set DELULU_IMAGE_ALLOWLIST to override."),
                 "image": image,
                 "allowlist": list(_image_allowlist())}, 400)
        rc, _, _ = self._docker(
            ["docker", "image", "inspect", image], timeout=10)
        self._json_response({"pulled": rc == 0, "image": image})

    def _api_pull(self):
        body = self._read_json()
        image = body.get("image", "")
        if not image:
            return self._json_response({"error": "No image specified"}, 400)
        if not _is_image_allowed(image):
            return self._json_response(
                {"error": ("Image rejected: not in allowlist. "
                           "Set DELULU_IMAGE_ALLOWLIST to override."),
                 "image": image,
                 "allowlist": list(_image_allowlist())}, 400)

        # Check if already local
        rc, _, _ = self._docker(
            ["docker", "image", "inspect", image], timeout=10)
        if rc == 0:
            return self._json_response(
                {"status": "already_pulled", "image": image})

        # Pull
        rc, stdout, stderr = self._docker(
            ["docker", "pull", "--", image], timeout=600)
        if rc == 0:
            self._json_response({"status": "pulled", "image": image})
        else:
            self._json_response({
                "status": "error",
                "image": image,
                "message": (stderr or stdout)[:1000],
            })

    def _api_verify(self):
        body = self._read_json()
        image = body.get("image", "")
        mode = body.get("mode", "")
        completion = body.get("completion")

        if not image:
            return self._json_response({"error": "No image specified"}, 400)
        if not _is_image_allowed(image):
            return self._json_response(
                {"error": ("Image rejected: not in allowlist. "
                           "Set DELULU_IMAGE_ALLOWLIST to override."),
                 "image": image,
                 "allowlist": list(_image_allowlist())}, 400)
        if not mode:
            return self._json_response({"error": "No mode specified"}, 400)
        if mode not in ("golden", "hallucinated", "patch"):
            return self._json_response(
                {"error": f"Invalid mode: {mode}"}, 400)

        if mode == "patch":
            if completion is None:
                return self._json_response(
                    {"error": "No completion provided for patch mode"}, 400)
            rc, stdout, stderr = self._docker(
                ["docker", "run", "--rm", "-i", "--", image,
                 "verify", "patch"],
                stdin_data=completion, timeout=180)
        else:
            rc, stdout, stderr = self._docker(
                ["docker", "run", "--rm", "--", image, "verify", mode],
                timeout=180)

        # Parse JSON output from entrypoint
        result = None
        if stdout.strip():
            try:
                result = json.loads(stdout)
            except json.JSONDecodeError:
                pass

        self._json_response({
            "exit_code": rc,
            "result": result,
            "stdout": stdout if result is None else None,
            "stderr": stderr.strip() or None,
        })

    # ── Review API Endpoints ─────────────────────

    def _api_list_csvs(self):
        """List CSV files in the output/ directory.

        Hides files produced by the review/export pipeline so the dropdown
        only shows canonical input CSVs. To see everything, pass
        ?all=1 in the request URL or set DELULU_VIEWER_SHOW_ALL=1.
        """
        output_dir = os.path.join(STATIC_DIR, "output")
        if not os.path.isdir(output_dir):
            return self._json_response({"files": []})

        show_all = (
            "all=1" in (self.path.split("?", 1)[1] if "?" in self.path else "")
            or os.environ.get("DELULU_VIEWER_SHOW_ALL") == "1"
        )

        # Hide review/export artifacts and helper backups so users see
        # only canonical CSVs they'd want to review.
        def _is_intermediate(name: str) -> bool:
            lower = name.lower()
            if lower.startswith("_"):
                return True
            if ".before_" in lower:
                return True
            stem = lower[:-4] if lower.endswith(".csv") else lower
            for suffix in ("_reviewed", "_updated", "_reviewed_updated",
                           "_export", "_exported"):
                if stem.endswith(suffix):
                    return True
            return False

        files = []
        for f in os.listdir(output_dir):
            if not f.endswith(".csv"):
                continue
            if not os.path.isfile(os.path.join(output_dir, f)):
                continue
            if not show_all and _is_intermediate(f):
                continue
            files.append(f)
        files.sort()
        self._json_response({"files": files})

    def _api_load_csv(self):
        """Load a CSV file from the output/ directory."""
        body = self._read_json()
        filename = body.get("filename", "")
        if not filename:
            return self._json_response({"error": "No filename specified"}, 400)

        # Sanitize filename - prevent path traversal
        basename = os.path.basename(filename)
        if basename != filename or ".." in filename:
            return self._json_response(
                {"error": "Invalid filename"}, 400)

        filepath = os.path.join(STATIC_DIR, "output", basename)
        if not os.path.isfile(filepath):
            return self._json_response(
                {"error": f"File not found: {basename}"}, 404)

        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            fieldnames = reader.fieldnames or []

        self._json_response({
            "filename": basename,
            "fieldnames": fieldnames,
            "rows": rows,
            "count": len(rows),
        })

    def _api_save_review(self):
        """Save review state as a JSON sidecar file."""
        body = self._read_json()
        filename = body.get("filename", "")
        review_data = body.get("review_data")

        if not filename or review_data is None:
            return self._json_response(
                {"error": "filename and review_data required"}, 400)

        basename = os.path.basename(filename)
        if basename != filename or ".." in filename:
            return self._json_response(
                {"error": "Invalid filename"}, 400)

        # Save as .review.json alongside the CSV
        review_path = os.path.join(
            STATIC_DIR, "output",
            basename.replace(".csv", ".review.json"))
        with open(review_path, "w", encoding="utf-8") as f:
            json.dump(review_data, f, ensure_ascii=False, indent=2)

        self._json_response({
            "status": "saved",
            "path": os.path.basename(review_path),
        })

    def _api_load_review(self):
        """Load review state from a JSON sidecar file."""
        body = self._read_json()
        filename = body.get("filename", "")
        if not filename:
            return self._json_response(
                {"error": "No filename specified"}, 400)

        basename = os.path.basename(filename)
        if basename != filename or ".." in filename:
            return self._json_response(
                {"error": "Invalid filename"}, 400)

        review_path = os.path.join(
            STATIC_DIR, "output",
            basename.replace(".csv", ".review.json"))

        if not os.path.isfile(review_path):
            return self._json_response({"review_data": None})

        with open(review_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self._json_response({"review_data": data})

    def _api_export_csv(self):
        """Export reviewed CSV with accepted/edited columns."""
        body = self._read_json()
        filename = body.get("filename", "")
        review_data = body.get("review_data")
        export_name = body.get("export_name", "")

        if not filename or review_data is None:
            return self._json_response(
                {"error": "filename and review_data required"}, 400)

        basename = os.path.basename(filename)
        if basename != filename or ".." in filename:
            return self._json_response(
                {"error": "Invalid filename"}, 400)

        # Load original CSV
        filepath = os.path.join(STATIC_DIR, "output", basename)
        if not os.path.isfile(filepath):
            return self._json_response(
                {"error": f"File not found: {basename}"}, 404)

        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            fieldnames = list(reader.fieldnames or [])

        # Add new columns
        extra_cols = ["accepted", "is_hallucination_updated"]
        for col in extra_cols:
            if col not in fieldnames:
                fieldnames.append(col)

        # Apply review decisions
        # review_data is a dict: {benchmark_id: {accepted, edited_hallucination, ...}}
        exported_rows = []
        for row in rows:
            bid = row.get("benchmark_id", "")
            review = review_data.get(bid, {})

            status = review.get("status", "pending")
            # Only include accepted rows if export_accepted_only
            row["accepted"] = "true" if status == "accepted" else "false"

            edited = review.get("edited_hallucination")
            if edited is not None and edited != row.get(
                    "hallucinated_completion", ""):
                row["hallucinated_completion"] = edited
                row["is_hallucination_updated"] = "true"
            else:
                row["is_hallucination_updated"] = "false"

            exported_rows.append(row)

        # Write to buffer
        buf = io.StringIO()
        writer = csv.DictWriter(
            buf, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(exported_rows)
        csv_content = buf.getvalue()

        # Save to file
        if not export_name:
            export_name = basename.replace(
                ".csv", "_reviewed.csv")
        export_basename = os.path.basename(export_name)
        export_path = os.path.join(
            STATIC_DIR, "output", export_basename)
        with open(export_path, "w", encoding="utf-8", newline="") as f:
            f.write(csv_content)

        self._json_response({
            "status": "exported",
            "filename": export_basename,
            "total_rows": len(exported_rows),
            "accepted_count": sum(
                1 for r in exported_rows if r["accepted"] == "true"),
            "rejected_count": sum(
                1 for r in exported_rows if r["accepted"] == "false"),
            "edited_count": sum(
                1 for r in exported_rows
                if r["is_hallucination_updated"] == "true"),
        })


class ThreadedServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def main():
    parser = argparse.ArgumentParser(
        description="Delulu Benchmark Viewer Server")
    parser.add_argument("--port", "-p", type=int, default=8000)
    parser.add_argument(
        "--bind", default="127.0.0.1",
        help=("Bind address. Defaults to 127.0.0.1 (loopback only). Pass "
              "0.0.0.0 only on a trusted network; the API exposes Docker."))
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    url = f"http://{args.bind}:{args.port}/viewer.html"
    review_url = f"http://{args.bind}:{args.port}/review.html"
    print(f"\n{'='*55}")
    print(f"  Delulu Benchmark Viewer Server")
    print(f"{'='*55}")
    print(f"  Viewer:    {url}")
    print(f"  Review:    {review_url}")
    print(f"  API:       http://{args.bind}:{args.port}/api/health")
    print(f"  Static:    {STATIC_DIR}")
    print(f"  Allowlist: {', '.join(_image_allowlist())}")
    print(f"{'='*55}")
    print(f"  Press Ctrl+C to stop\n")

    if not args.no_browser:
        webbrowser.open(url)

    server = ThreadedServer((args.bind, args.port), ViewerHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()
