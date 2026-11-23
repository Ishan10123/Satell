# Phase 6B OpenSSL remediation report

**Decision:** No supported OpenSSL remediation was available for these candidate digests on 2026-11-20. The findings remain **OPEN**. No images were rebuilt, retagged, or promoted in this tranche.

## Options evaluated

| Order | Option | Evidence | Decision |
|---|---|---|---|
| 1 | Supported Debian security update | Debian’s Trixie security tracker lists `3.5.7-1~deb13u3` as vulnerable for the three CVEs and lists no fixed version. | Not available in the assessed package state. Do not report fixed. |
| 2 | Supported patched Python base-image digest | Candidate `FROM` is pinned to the Python 3.13 slim digest recorded in the assessment. Docker Scout recommends refreshing to `sha256:48d884813cf44e927cf64c5529dd630dd3b18338c6dc727991eef9b71e934a20`, but its summary still reports 11 High findings for the refreshed base candidate. No evidence established that the recommendation clears the OpenSSL CVEs. | Not adopted. A base refresh without proof of the package fix would add change risk without satisfying the gate. |
| 3 | Vendor-supported package update | Debian’s Trixie tracker still lists the installed version as vulnerable and the fixed version as unfixed for all three CVEs ([84786](https://security-tracker.debian.org/tracker/CVE-2026-84786), [107493](https://security-tracker.debian.org/tracker/CVE-2026-107493), [107496](https://security-tracker.debian.org/tracker/CVE-2026-107496)). OpenSSL's Nov 17 advisory says the release containing the fix for CVE-2026-107493 is scheduled for Dec 1, 2026. CVE-2026-107496 is a separate Nov 10 entry; its OpenSSL page identifies 3.5.10 as the fixed 3.5 line, without relying on the Nov 17 advisory's schedule. The CVE-2026-84786 upstream change is in an open pull request, not a released Debian package. | Wait for a supported release, then verify the Debian package and image scan before rebuilding. |
| 4 | Remove OpenSSL if unused | Both `_ssl` extension modules dynamically link `libssl.so.3` and `libcrypto.so.3`; runtime HTTP/TLS connections depend on Python TLS. | Rejected as unsafe and functionally incompatible. |
| 5 | Mitigation and approved exception | Application paths inspected do not intentionally use DANE, CMS encryption, or the non-NULL PEM stack pattern. This limits known use cases but is not a package fix and does not establish that every dependent library is unaffected. No security owner approved a risk exception. | No accepted-risk status. Findings remain OPEN. |

The [OpenSSL Nov 17 advisory](https://www.openssl-library.org/news/secadv/20261117.txt) says fixes described there are in the public source repository and releases containing them are scheduled for 2026-12-01; it specifically lists CVE-2026-107493 and OpenSSL 3.5.10. The [OpenSSL vulnerability entries](https://www.openssl-library.org/news/vulnerabilities-1.1.1/index.html) list CVE-2026-107496 separately as published Nov 10 and identify 3.5.10 as the fixed 3.5 line. As the scheduled release date is still in the future relative to this assessment, no unsupported package version or manually compiled library was forced into either candidate.

## Validation after assessment

- Candidate image IDs remained unchanged: Django `sha256:aa08af08903a6d3756bd115be6647a9036bb73853b06dfe8137304984d56e1f9`; API `sha256:0ab84e45ec8fd0f85a371d62d6d0c0bde01ce0b9f1dbb72fdc869d946c2f8c78`.
- Scout reported 3 High OpenSSL findings on each image; no finding was filtered out of the saved full SARIF artifacts.
- The complete OpenSSL package scan reports 11 findings (3 high, 1 medium, 7 low).
- Runtime functionality was exercised with the current library: Python TLS, Ollama HTTP connectivity, candidate FastAPI readiness, generation, citations, and verification worked in the isolated synthetic staging path.
- These tests demonstrate functionality only; they do not make a vulnerable package safe or supersede the security release gate.

## Required next action

After a supported Debian/Python base package includes the relevant fixes, rebuild new candidate digests, regenerate SBOMs, run the full Scout scan, and repeat PostgreSQL and synthetic end-to-end validation. If the deployment must proceed earlier, the release owner must explicitly approve an expiring risk exception. Until either event, keep this candidate blocked.
