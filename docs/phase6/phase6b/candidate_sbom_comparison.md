# Phase 6B candidate SBOM comparison

## Artifacts and image identities

Docker Scout 1.28.0 generated CycloneDX SBOMs for the two candidate image IDs:

- Django: `sha256:aa08af08903a6d3756bd115be6647a9036bb73853b06dfe8137304984d56e1f9` — `evidence/django_candidate.sbom.json`
- FastAPI: `sha256:0ab84e45ec8fd0f85a371d62d6d0c0bde01ce0b9f1dbb72fdc869d946c2f8c78` — `evidence/api_candidate.sbom.json`

The generated CycloneDX files contain 145 and 188 components respectively. Scout’s console reports 145 and 196 packages indexed; these are scanner indexing counts, not the CycloneDX component count. Set comparison of the SBOM components found 135 common name/version pairs, 10 Django-only pairs, and 53 API-only pairs. The additional API dependencies are expected for retrieval and model clients.

## OpenSSL and build-tool comparison

Both SBOMs contain the same Debian Trixie OpenSSL runtime packages:

- `openssl 3.5.7-1~deb13u3`
- `libssl3t64 3.5.7-1~deb13u3`
- `openssl-provider-legacy 3.5.7-1~deb13u3`

The SBOM also lists upstream OpenSSL as `3.5.7`; this is the same runtime distribution package, not a separate remediation. Docker Scout identifies the same three High OpenSSL CVEs for each image. Full OpenSSL-only scan artifacts are retained as SARIF alongside the SBOMs.

Neither SBOM has components named `pip`, `setuptools`, or `wheel`, consistent with their removal from runtime images. Both candidate image configurations use non-root runtime users and contain no `RAG_API_TOKEN` or `POSTGRES_PASSWORD` environment entry. Credentials were passed only to isolated runtime containers for testing, not baked into the candidate image configuration.

## Package origin

Both images use `python:3.13-slim` pinned to digest `sha256:e48f59cdba69a3cbd9ed2cf0f348d90d45a8d350d98134cf1070bc106ee9ed90`. The Dockerfiles install a pinned zlib update only. Scout attributes the OpenSSL package metadata and configuration paths to base-image layers; the package is not introduced by the Django or RAG requirements files.

## Security interpretation

The images share the same vulnerable operating-system OpenSSL package. The API SBOM is larger because it includes the RAG stack; the Django SBOM includes Django, Gunicorn, Psycopg, and WhiteNoise. SBOM equivalence does not imply equivalent application exposure, and it does not close the OpenSSL findings.

Docker Scout’s SARIF output does not contain a vulnerability-database timestamp. Scanner version and scan date are recorded, but database freshness remains unknown.
