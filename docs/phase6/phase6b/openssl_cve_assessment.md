# Phase 6B OpenSSL CVE assessment

**Assessment date:** 2026-11-20  
**Status:** OPEN — candidate images remain blocked from release pending a supported fix or explicit security-risk approval.

## Images and scanner evidence

| Candidate | Docker image ID | Platform | Runtime identity |
|---|---|---|---|
| `satell-django:phase6-candidate` | `sha256:aa08af08903a6d3756bd115be6647a9036bb73853b06dfe8137304984d56e1f9` | linux/amd64 | `django` |
| `satell-rag-api:phase6-candidate` | `sha256:0ab84e45ec8fd0f85a371d62d6d0c0bde01ce0b9f1dbb72fdc869d946c2f8c78` | linux/amd64 | `ragapi` |

Docker Scout CLI 1.28.0 reports the same three **High** OpenSSL findings on both image IDs. The package is Debian Trixie `openssl` `3.5.7-1~deb13u3`; the SBOM also records `libssl3t64` and `openssl-provider-legacy` at that Debian package version. A complete OpenSSL-only scan reports 11 findings in total (3 high, 1 medium, 7 low); the release-gate highs are listed below. The scanner SARIF does not provide an invocation time or vulnerability-database timestamp. The scan was run on 2026-11-20; the database freshness cannot be established from the artifact.

| CVE | Scout severity | Installed package | Scanner fixed version | Advisory / current status |
|---|---|---|---|---|
| CVE-2026-107493 | High | `openssl 3.5.7-1~deb13u3` | Not fixed | OpenSSL’s Nov 17 advisory classifies this as Low and says releases containing fixes are scheduled for Dec 1, 2026. OpenSSL 3.5.10 is the stated fix. Exposure requires an application to pass an existing non-NULL stack to the PEM X.509 info reader and then reuse it after failure; OpenSSL’s own TLS callers pass NULL. Debian Trixie security still marks the package vulnerable and the fixed version as unfixed. |
| CVE-2026-84786 | High | `openssl 3.5.7-1~deb13u3` | Not fixed | A DANE-enabled TLS client can encounter a null dereference for a specific certificate/TLSA combination. Debian Trixie security marks the package vulnerable with no fixed version. The OpenSSL pull request fixing the issue was still open on the assessment date; it is not a released package fix. |
| CVE-2026-107496 | High | `openssl 3.5.7-1~deb13u3` | Not fixed | Infinite loop/CPU denial of service in CMS encryption with an attacker-controlled EC recipient certificate whose group order is 1. OpenSSL classifies it as Low and states the ordinary TLS/QUIC code does not use this path. Debian Trixie security still marks the installed package vulnerable and unfixed. |

Severity differs by source: Docker Scout classifies all three as High; OpenSSL’s published material classifies CVE-2026-107493 and CVE-2026-107496 as Low, while Debian’s tracker records package status rather than a matching severity. This report preserves the scanner result and records the disagreement; it does not downgrade or suppress findings.

## Package origin and runtime requirement

Both Dockerfiles start from the same pinned base: `python:3.13-slim@sha256:e48f59cdba69a3cbd9ed2cf0f348d90d45a8d350d98134cf1070bc106ee9ed90`. Their Dockerfiles install a pinned zlib update but do not install or upgrade OpenSSL. Scout attributes package metadata to layer diff ID `sha256:dd57f90311a2567b55ff22eeacff1602fd04ad7566e315957731359eab173b90` (`/var/lib/dpkg/status`) and OpenSSL configuration to `sha256:ba2541ec790ab743d0e3ee06e9eb5b3e8343b1fdc09cb65853c7c90803bbff00` (`/etc/ssl/openssl.cnf`), both inherited from the Python/Debian base layers.

`ldd` on each candidate’s Python `_ssl` extension resolves `libssl.so.3` and `libcrypto.so.3` from the installed operating-system package. Python reports OpenSSL 3.5.7 at runtime. Removing the package would break the Python TLS module used by the application’s HTTP clients, so package removal is not a valid remediation.

## Evidence references

- Docker Scout SARIF: `evidence/django_openssl_findings.sarif.json`, `evidence/api_openssl_findings.sarif.json`.
- CycloneDX SBOMs: `evidence/django_candidate.sbom.json`, `evidence/api_candidate.sbom.json`.
- [OpenSSL Security Advisory, 2026-11-17](https://www.openssl-library.org/news/secadv/20261117.txt)
- [Debian CVE-2026-84786 tracker](https://security-tracker.debian.org/tracker/CVE-2026-84786)
- [Debian CVE-2026-107493 tracker](https://security-tracker.debian.org/tracker/CVE-2026-107493)
- [Debian CVE-2026-107496 tracker](https://security-tracker.debian.org/tracker/CVE-2026-107496)
- [OpenSSL upstream fix pull request for CVE-2026-84786](https://github.com/openssl/openssl/pull/33634)

No finding is marked fixed or accepted. A formal exception would require a named security owner, documented threat/exposure analysis, compensating controls, expiry date, and approval. No such approval was present.
Scanner evidence is retained in `evidence/django_openssl_high.md`, `evidence/api_openssl_high.md`, and the two `*_openssl_locations.txt` files, in addition to the full SARIF reports.
