# Tesseract 5 with the Telugu language pack, isolated in a container so the
# host workstation does not need `sudo apt install tesseract-ocr-tel`.
#
# Build:
#   docker build -t ml-class-project/tesseract docker/tesseract/
#
# Usage (typical):
#   docker run --rm \
#       -v "$PWD/data:/data" \
#       ml-class-project/tesseract \
#       tesseract /data/raw/<book_id>/page_001.jpg /data/interim/page_001 -l tel
#
# The repo's scripts/run_tesseract.sh wraps this for ergonomic use from Python.

FROM ubuntu:22.04

# Avoid interactive tzdata prompts during apt install
ENV DEBIAN_FRONTEND=noninteractive

# Pin apt mirror update + install in one layer; clean apt cache after.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-tel \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Sanity-check the language pack actually installed.
RUN tesseract --list-langs | grep -q "^tel$" || (echo "Telugu pack missing" && exit 1)

# Default to the input directory the wrapper mounts to.
WORKDIR /data

# A no-op default; callers pass the real tesseract invocation as arguments.
CMD ["tesseract", "--version"]
