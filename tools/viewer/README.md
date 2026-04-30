# Delulu CSV Viewer

A small, single-page web UI for browsing the Delulu benchmark CSVs.
Renders prefix / suffix / golden / hallucinated side-by-side with syntax
highlighting, lets you filter by language and hallucination type, and (when
the host's Docker socket is mounted) can pull a sample's verifier image and
run `verify golden` / `verify hallucinated` / `verify patch` directly from the
browser.

## Run via Docker (recommended)

A pre-built image is published on Docker Hub (TBA):

```bash
docker run --rm -p 8000:8000 \
    -v "$PWD/data:/app/output" \
    -v /var/run/docker.sock:/var/run/docker.sock \
    delulubench/delulu-viewer:v1
```

Then open http://localhost:8000.

- The `output/` mount is where the viewer looks for CSV files (the dropdown
  in the top bar lists every `*.csv` it finds).
- Mounting `/var/run/docker.sock` is optional — only needed if you want the
  in-browser "Verify" buttons to work.

## Run from source

```bash
cd tools/viewer
python serve_viewer.py --port 8000
```

By default the server looks for CSVs in `tools/viewer/output/`. Drop or
symlink `data/delulu.csv` there:

```bash
mkdir -p output && cp ../../data/delulu.csv output/
```

## Files

- `viewer.html` — main read-only viewer.
- `review.html` — optional editing UI (for community-driven sample fixes).
- `serve_viewer.py` — small `http.server`-based backend with REST endpoints
  for Docker pull / verify and CSV save/load.
- `Dockerfile` — produces the `delulu-viewer` image used above.
