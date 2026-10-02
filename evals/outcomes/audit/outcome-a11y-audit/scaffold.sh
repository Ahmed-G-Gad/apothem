#!/usr/bin/env bash
# SPDX-License-Identifier: MIT

# Seeds the workspace for this case (runs only with --scaffold).
set -euo pipefail

mkdir -p 'site'
cat > 'site/index.html' <<'FIXTURE'
<!doctype html>
<html>
  <body>
    <img src="logo.png">
    <input type="text" name="q">
    <div onclick="search()">Search</div>
  </body>
</html>
FIXTURE
