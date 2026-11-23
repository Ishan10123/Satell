# Phase 6 candidate validation evidence

**Run date:** 2026-11-20 (local environment, Asia/Kolkata). **Scope:** isolated image candidates and read-only checks of the existing local runtime. No candidate was deployed.

## Candidate artifacts

| Image | Digest | Build result | Runtime checks |
|---|---|---|---|
| `satell-django:phase6-candidate` | `sha256:aa08af08903a6d3756bd115be6647a9036bb73853b06dfe8137304984d56e1f9` | Docker build succeeded; dependency install and `pip check` succeeded; Django static collection copied 131 files and post-processed 393 | Django 5.2.17; msgpack 1.2.3; urllib3 2.8.0; pip/setuptools absent; zlib 1.3.1 |
| `satell-rag-api:phase6-candidate` | `sha256:0ab84e45ec8fd0f85a371d62d6d0c0bde01ce0b9f1dbb72fdc869d946c2f8c78` | Docker build succeeded; dependency install and `pip check` succeeded | FastAPI 0.163.1; msgpack 1.2.3; urllib3 2.8.0; pip/setuptools absent; zlib 1.3.1 |

Builds use the pinned Python base digest `sha256:e48f59cdba69a3cbd9ed2cf0f348d90d45a8d350d98134cf1070bc106ee9ed90`. Debian's mutable security repository was used at build time to install the exact fixed `zlib1g` package version; therefore the OS package set is not fully reproducible from the base digest alone. A Debian snapshot source or a reviewed base digest containing the fix is still needed for clean reproducible release builds.

## Test and validation results

| Check | Result |
|---|---|
| Windows host RAG tests | 270 run, passed; one Windows symlink-capability test skipped |
| Linux container RAG tests | 270 run, all passed; source/test tree mounted read-only into the candidate dependency/runtime environment |
| Isolated Django candidate SQLite tests | 65 run; 63 passed, 2 opt-in integration tests skipped |
| Existing Django PostgreSQL suite | 65 passed in the prior verified run, before this candidate-only Dockerfile change |
| Existing Django SQLite suite | 65 passed in the prior verified run, before this candidate-only Dockerfile change |
| Host compileall | Passed for `src`, `scripts`, `tests` |
| Host pip check | Passed, no broken requirements |
| Candidate pip check | Passed during each candidate image build |
| Existing Django checks | Passed with expected warning `accounts.W001`: SMTP is not configured |
| Django migration check | No changes detected |
| Existing index validation | Passed; `rag_docs_v2`, 6,565 docs and 58,856 chunks, `operator_authorized_unreviewed` |
| Existing Qdrant read-only status | Green; 58,856 points |

Commands run from `E:\RAG_Project` in PowerShell (image scan/SBOM filenames shown):

```powershell
docker build --pull -f django_app/Dockerfile -t satell-django:phase6-candidate .
docker build --pull -f Dockerfile.rag-api -t satell-rag-api:phase6-candidate .
docker run --rm --network none -e DJANGO_SECRET_KEY=phase6-isolated-test-key -e DJANGO_DEBUG=0 -e DJANGO_DB_ENGINE=sqlite -e DJANGO_SQLITE_PATH=/tmp/phase6-candidate.sqlite3 satell-django:phase6-candidate python manage.py test
docker run --rm --network none -v "E:\RAG_Project:/workspace:ro" -w /workspace -e PYTHONPATH=/workspace:/workspace/src satell-rag-api:phase6-candidate python -m unittest discover -s tests
docker scout cves local://satell-django:phase6-candidate --only-severity critical,high --format markdown --output docs/phase6/evidence/django_candidate_high_critical.md
docker scout cves local://satell-rag-api:phase6-candidate --only-severity critical,high --format markdown --output docs/phase6/evidence/rag_api_candidate_high_critical.md
docker scout sbom local://satell-django:phase6-candidate --format spdx --output docs/phase6/evidence/django_candidate.spdx.json
docker scout sbom local://satell-rag-api:phase6-candidate --format spdx --output docs/phase6/evidence/rag_api_candidate.spdx.json
```

The host RAG checks used `& .\.venv\Scripts\python.exe -m unittest discover -s tests`, `-m compileall -q src scripts tests`, `-m pip check` and `scripts/ragctl.py validate-index`. The existing running Django container passed `python manage.py check` and `python manage.py makemigrations --check --dry-run`. The only `check` warning is the SMTP configuration warning.

## Candidate vulnerability scan and SBOM

Docker Scout CLI 1.28.0 scanned the exact candidate image digests, filtering to **critical and high** severity. Each image has **0 critical and 3 high** findings on OpenSSL 3.5.7-1~deb13u3: CVE-2026-107493, CVE-2026-84786 and CVE-2026-107496. Scout lists no fixed version. These results are unresolved; no applicability exception or VEX statement was applied. The candidates have 145 packages (Django) and 196 packages (API). Zlib findings and vulnerabilities in the removed package-manager build tooling no longer appear in candidate scan results. This scan does not establish exploitability or absence of other findings.

- [Django candidate high/critical scan](django_candidate_high_critical.md)
- [FastAPI candidate high/critical scan](rag_api_candidate_high_critical.md)
- [Django SPDX SBOM](django_candidate.spdx.json)
- [FastAPI SPDX SBOM](rag_api_candidate.spdx.json)

## Live data and runtime preservation

No live services were restarted or replaced. Existing Django and FastAPI containers remained healthy and retained their pre-candidate image IDs. Qdrant returned 58,856 points and the index manifest remained `operator_authorized_unreviewed`; validation succeeded. The application database at final inspection held 1 user, 3 conversations, 44 messages and 39 citation snapshots. These counts differ from an earlier snapshot in prior documentation; this run's test/build commands used isolated candidate SQLite and local RAG fixtures, and did not write application records. Shared app activity may have occurred between snapshots.

All 14 legal source decisions remain pending; production document approval registry remains absent. Candidate image results do not imply legal approval, production readiness or permission to promote/deploy.
