---
name: addon-release
description: Bump the Menu Planner version and release the add-on and integration images and metadata. Use when preparing a release tag or changing the add-on image or architectures.
---

# Release the add-on

Versions must match in these places:
- `addon/config.yaml` `version:` (drives the image tag in `build-addon.yaml`)
- `custom_components/menu_planner/manifest.json` `version`

Image naming: `ghcr.io/<owner>/<arch>-addon-menu-planner:<version>` from the `image:` line in `addon/config.yaml`. The owner is lowercased in the workflow because GHCR requires lowercase names.

Architectures: `armv7` (Raspberry Pi 2/3 32-bit), `aarch64` (Pi 3/4/5 64-bit), `amd64`. Do not drop armv7 without updating README and `addon/config.yaml`.

Build details:
- `build-addon.yaml` builds per arch with QEMU for armv7. It does not use `prepare-multi-arch-matrix`, which rejects armv7.
- The Dockerfile selects the base image from `BUILD_ARCH`. Supervisor passes `BUILD_FROM` itself.
- PRs build without pushing. `main` pushes.

Steps:
1. Run the `run-checks` skill. Everything must pass.
2. Bump both version fields in one commit.
3. Add a WORKFILE log row and update the README if install steps changed.
4. Push to `main`. Confirm the `Build add-on` workflow passes for all three architectures.
5. Tag `v<version>` and create a GitHub release.

Not yet done (open): cosign signing of published images, and a live check that Supervisor resolves the armv7 image.
