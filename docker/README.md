# Docker images

System tools that would otherwise need `sudo apt install` on the host live here. Each subdirectory holds one Dockerfile + supporting context.

See [`../docs/standards/environment_standard.md`](../docs/standards/environment_standard.md) for the rationale and policy.

## Images in this project

| Image | Purpose | Build command |
|-------|---------|---------------|
| `ml-class-project/tesseract` | Tesseract 5 + Telugu language pack — baseline OCR comparison | `docker build -t ml-class-project/tesseract docker/tesseract/` |

`scripts/setup_env.sh` builds all of these as part of the bootstrap workflow. You should not need to run the build commands manually unless you are iterating on a Dockerfile.
