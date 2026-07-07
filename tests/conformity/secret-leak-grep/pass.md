<!-- SPDX-License-Identifier: MIT -->

# Sample Artifact — No Hardcoded Secrets

This fixture is the PASS case for `secret-leak-grep`. The artifact
contains no credential patterns and no high-entropy tokens.

## Configuration

The application reads its credentials from environment variables:

- `AWS_ACCESS_KEY_ID` — populated by the deployment platform.
- `GITHUB_TOKEN` — injected by the workflow runner.
- `JWT_SIGNING_KEY` — fetched from the secrets manager at boot.

## Reference

Each variable is documented in the operations runbook with its
rotation cadence and the rotation owner. None of the actual values
appears in source.
