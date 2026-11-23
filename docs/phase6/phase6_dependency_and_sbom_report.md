# Dependency and SBOM assessment

**Assessment date:** 2026-11-20. Docker Scout CLI 1.28.0 was used for high/critical candidate image scans and SPDX image SBOM generation. No other scanner was installed.

## Dependency sources found

- Root direct runtime pins: `requirements.txt`.
- FastAPI image pins: `requirements-api.txt`.
- Synthetic test API pins: `requirements-synthetic-api.txt`.
- End-to-end tooling: `requirements-e2e.txt`.
- Django image pins: `django_app/requirements-docker.txt`.
- Local `.venv` is not a lock source. No comprehensive transitive lock file or SBOM is maintained. Root requirements include parser libraries in addition to serving dependencies, while Docker image requirements are narrower.
- Host and candidate build-time `pip check` passed (no broken installed requirements). This is not a vulnerability scan.
- Root downloader scripts import `arxiv`; no reviewed requirements file declares it. Those scripts are operator utilities and not in the serving path.

## Scanner availability

Docker Scout 1.28.0 scanned the exact isolated candidate image digests with `--only-severity critical,high`; SPDX SBOMs were generated for both candidates. Results:

| Candidate image | Digest | Packages | Critical | High | Finding |
|---|---|---:|---:|---:|---|
| `satell-django:phase6-candidate` | `sha256:aa08af08903a6d3756bd115be6647a9036bb73853b06dfe8137304984d56e1f9` | 145 | 0 | 3 | OpenSSL 3.5.7-1~deb13u3; scanner reports CVE-2026-107493, CVE-2026-84786, CVE-2026-107496 without a fixed version |
| `satell-rag-api:phase6-candidate` | `sha256:0ab84e45ec8fd0f85a371d62d6d0c0bde01ce0b9f1dbb72fdc869d946c2f8c78` | 196 | 0 | 3 | Same OpenSSL package and three advisories |

The candidate Dockerfiles pin Python base image digest `sha256:e48f59cdba69a3cbd9ed2cf0f348d90d45a8d350d98134cf1070bc106ee9ed90`, upgrade Debian `zlib1g` to `1:1.3.dfsg+really1.3.1-1+deb13u1` (fixing two Scout findings), pin Django 5.2.17, msgpack 1.2.3 and urllib3 2.8.0, run `pip check` at build time, and remove pip/setuptools/wheel from final runtime layers. Runtime probes confirm the intended Python package versions, absence of package managers and zlib 1.3.1. Candidate test suites pass as documented in `phase6/evidence/phase6_candidate_validation_20261120.md`.

Candidate scans retain three high OpenSSL advisories with no fixed version in Scout's database. This is a release blocker; scanner results are not an applicability analysis. No VEX exception was applied. The scan filters out medium/low findings and is not a license review or full supply-chain assessment. Reports: [Django candidate scan](evidence/django_candidate_high_critical.md), [API candidate scan](evidence/rag_api_candidate_high_critical.md). SPDX files: [Django candidate SBOM](evidence/django_candidate.spdx.json), [API candidate SBOM](evidence/rag_api_candidate.spdx.json).

## Production actions

1. Choose deployment target and image registry first; scan exact immutable image digests.
2. Produce a fully resolved lock per image/environment, including transitive package versions and hashes.
3. Generate SPDX or CycloneDX SBOM for Python wheels and container image OS packages.
4. Scan dependencies, base images and model/tokenizer artifacts using approved tools; retain database version/date and scanner configuration.
5. Inventory package and model licenses for governance; do not equate scanner output with legal advice.
6. Define critical/high remediation SLA, exception signer, rebuild process, provenance/signing and recurring rescan schedule.
7. Add CI policy only after target registry and vulnerability exception process are approved.

**Status: PARTIAL/BLOCKED.** Candidate builds have digest-bound SPDX/scanner evidence; three unresolved high OpenSSL advisories remain, transitive dependency locks/hashes are incomplete, and there is no recurring scan or approved exception process. No clean bill of health can be claimed. Existing runtime images were not changed.
