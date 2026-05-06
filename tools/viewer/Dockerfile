# Delulu Benchmark Viewer - Docker image
#
# Bundles the HTML viewer (viewer.html, review.html) and the API server
# (serve_viewer.py) plus the latest delulu benchmark CSV so users can
# browse the benchmark with a single docker run command.
#
# To run actual benchmark image pulls/verifies from the viewer UI, the
# host's Docker socket must be mounted into this container at
# /var/run/docker.sock.

FROM python:3.12-slim

# Install Docker CLI (no daemon — we use the host's daemon via mounted socket)
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl gnupg \
    && install -m 0755 -d /etc/apt/keyrings \
    && curl -fsSL https://download.docker.com/linux/debian/gpg \
       | gpg --dearmor -o /etc/apt/keyrings/docker.gpg \
    && chmod a+r /etc/apt/keyrings/docker.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian $(. /etc/os-release && echo $VERSION_CODENAME) stable" \
       > /etc/apt/sources.list.d/docker.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends docker-ce-cli \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy viewer assets and API server.
# Build context is expected to be the verification/ directory.
COPY viewer.html review.html serve_viewer.py /app/

# Empty output/ — users mount their CSV directory at runtime, e.g.
#   -v /path/to/csvs:/app/output
# Without a mount the dropdown will be empty.
RUN mkdir -p /app/output

# Strip script execute bits — keep things simple.
EXPOSE 8000

# Run on 0.0.0.0 inside the container so it's reachable from the host. The
# API drives the Docker daemon, so always publish to loopback only:
#   docker run -p 127.0.0.1:8000:8000 -v /var/run/docker.sock:/var/run/docker.sock ...
ENTRYPOINT ["python", "/app/serve_viewer.py", "--port", "8000", "--bind", "0.0.0.0", "--no-browser"]
