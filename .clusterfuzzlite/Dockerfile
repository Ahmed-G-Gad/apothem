# SPDX-License-Identifier: MIT

# The ClusterFuzzLite build image. The OSS-Fuzz Python base ships Python 3.11,
# Atheris and PyInstaller, so this file installs nothing: the targets import
# apothem and its vendored dependencies from the checkout. The base is pinned by
# digest, and Dependabot proposes a new digest (the docker entry for
# /.clusterfuzzlite in .github/dependabot.yml).
FROM gcr.io/oss-fuzz-base/base-builder-python:v1@sha256:21f6fab17ace4dc76e1c56de91ee95d3d03da021df94b41056ba036f6c6f55e9
COPY . $SRC/apothem
WORKDIR $SRC/apothem
COPY .clusterfuzzlite/build.sh $SRC/
