# Phase 6C remaining limitations

## Resolved in this closure

- Candidate Docker builds, non-root/read-only runtime checks, Compose validation, and health checks.
- Django tests against SQLite and PostgreSQL; RAG regression suite.
- Chrome desktop/mobile workflow and actual candidate-stack real RAG query.
- Owner binding after verifying the active account, with only additive migrations.
- Runtime API image includes its Qdrant compatibility manifest; readiness now passes.

## Still open

1. **Production legal authorization:** all 14 source legal statuses remain pending; document approval registry is absent. Keep production mode fail-closed. Local demo operator authorization is not legal approval.
2. **Container vulnerabilities:** Docker Scout found 0 Critical and 6 High findings in each candidate image: four OpenSSL findings and two glibc findings. The scanner reports no fixed OpenSSL version and a newer fixed glibc version. Do not promote the current candidates until patched and rescanned or handled by an explicit security acceptance.
3. **Email delivery:** `SMTP_HOST` and provider credentials are not configured; password reset only returns generic confirmation and cannot deliver mail. The local base URL is HTTP, so HTTPS deployment configuration is also required before external recovery links.
4. **Deployment operations:** production TLS/reverse proxy, backup/restore drill, monitoring, incident response, resource/load limits, and recovery procedures have not been validated as a production deployment.
5. **Answer quality:** the browser RAG check was partially verified. Abstentions and partially verified answers remain possible and should be represented as such.
6. **Release promotion:** candidate containers were kept separate. Existing running app/API were not replaced; real traffic is still served by the previously running deployment.

See [final blockers](phase6c_final_blockers.md) for readiness decisions and the next actions.
