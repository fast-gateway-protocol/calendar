# FGP Calendar Daemon Docker Image
#
# Provides fast Google Calendar operations via API.
# Uses multi-stage build for minimal image size.

# Stage 1: Build the Rust binary
FROM rust:slim-bookworm AS builder

WORKDIR /app

# Install build dependencies (including Python dev for the python feature)
RUN apt-get update && apt-get install -y \
    pkg-config \
    libssl-dev \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy manifests first for better layer caching
COPY Cargo.toml Cargo.lock ./

# Create dummy src to build dependencies
RUN mkdir src && echo "fn main() {}" > src/main.rs
RUN cargo build --release && rm -rf src target/release/fgp-calendar

# Copy actual source and build
COPY src ./src
RUN touch src/main.rs && cargo build --release

# Stage 2: Runtime image with Python
FROM debian:bookworm-slim

# Install Python and runtime dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Google API Python libraries
RUN pip3 install --break-system-packages \
    google-auth \
    google-auth-oauthlib \
    google-api-python-client \
    python-dateutil

# Create non-root user for security
RUN useradd -m -s /bin/bash fgp

# Copy binary from builder
COPY --from=builder /app/target/release/fgp-calendar /usr/local/bin/

# Copy Python module
COPY module /usr/local/bin/module

# Set up FGP directory structure
RUN mkdir -p /home/fgp/.fgp/services/calendar/logs \
    && chown -R fgp:fgp /home/fgp/.fgp

USER fgp
WORKDIR /home/fgp

ENV FGP_SOCKET_DIR=/home/fgp/.fgp/services

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD fgp-calendar status || exit 1

# Mount points for credentials and socket
VOLUME ["/home/fgp/.fgp/services", "/home/fgp/.config/google"]

ENTRYPOINT ["fgp-calendar"]
CMD ["start", "--foreground"]
