<!-- SPDX-License-Identifier: MIT -->

# Sample Artifact — Synthetic Hardcoded Secrets

This fixture is the FAIL case for `secret-leak-grep`. Each value below
is a synthetic test placeholder that matches a vendor-issued credential
shape; none authenticates against any real service. The grep flags
each occurrence regardless.

## Synthetic credentials

```text
AWS_ACCESS_KEY_ID = AKIAEXAMPLEFIXTUREZZ
GITHUB_PERSONAL_TOKEN = ghp_EXAMPLEFIXTURE0000000000000000000000
GITHUB_OAUTH_TOKEN = gho_EXAMPLEFIXTURE0000000000000000000000
GITHUB_SERVER_TOKEN = ghs_EXAMPLEFIXTURE0000000000000000000000
GITHUB_USER_TOKEN = ghu_EXAMPLEFIXTURE0000000000000000000000
GITHUB_REFRESH_TOKEN = ghr_EXAMPLEFIXTURE0000000000000000000000
OPENAI_KEY = sk-EXAMPLEFIXTURE0000000000000000000000
GOOGLE_API_KEY = AIzaEXAMPLEFIXTURE000000000000000000000
SLACK_TOKEN = xoxb-EXAMPLEFIXTURE0000
JWT = eyJExample.eyJExample.signaturefixture
-----BEGIN RSA PRIVATE KEY-----
synthetic-fixture-body-line-1
-----END RSA PRIVATE KEY-----
```

The grep produces one finding per credential class above (or more if the
high-entropy heuristic also fires on adjacent tokens).
