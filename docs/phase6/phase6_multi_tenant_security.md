# Multi-tenant security design and status

**Status: NOT IMPLEMENTED for RAG tenancy; production blocked.** Current Django ownership is per user, while FastAPI uses one configured `RAG_TENANT_ID` and `RAG_PRINCIPAL_ID` for the whole application. There is no organization, tenant membership or per-user document ACL model. Existing configuration must not be mistaken for tenant isolation.

## Proposed data model

- User: Django identity.
- Tenant: organization boundary and lifecycle status.
- Membership: `(tenant, user, role, status, valid_from, revoked_at)` unique active relationship.
- Role: platform administrator (platform operations only), tenant administrator (membership/collection administration), user (query/read own permitted workspace), read-only user (read only). Deny by default.
- Collection: tenant owner, purpose, index version, allowed source/document set and policy version.
- Document: stable ID, content hash, source/provenance, tenant/collection, version and authorization state.
- Document ACL: tenant/document/principal or group/permission, status, effective dates and audit reference.
- Conversation: owner plus tenant, with tenant membership checked at every read/mutation.
- Retrieval scope: server-created immutable object containing tenant, principals, collection, allowed docs, denied docs and policy version.

## Request flow

1. Django resolves user from session; never trusts tenant or collection from browser fields.
2. Application service verifies active membership and role in a transaction.
3. Django sends a signed short-lived service assertion or mTLS-authenticated request with user/tenant scope. This identity contract is not yet implemented; passing a raw browser-chosen scope is prohibited.
4. FastAPI validates service identity, expiry/audience, membership/policy version and derives scope.
5. Qdrant applies tenant, collection, source, document and ACL filters; context assembler rechecks exact document ACL/hash. Missing metadata denies.
6. Citation snapshots store stable source/document references; each citation read/share/export revalidates current access when policy requires.
7. Share links are capabilities to an owned conversation, but they must not freeze document access: revoked citations should be removed/redacted or link revoked according to approved policy.

## Required isolation test matrix

Same-tenant users with distinct ACLs; tenant admin/user/read-only roles; revoked membership; revoked document ACL; malicious tenant/collection fields; cross-tenant Qdrant results; missing ACL metadata; citation read/export; share link after revocation; replay/expired service assertions; membership change during long inference. Use a separate staging database and a separate temporary Qdrant collection. Never mutate `rag_docs_v2` or the application database to simulate tenant migration.

## Current evidence and risk

Conversation owner filtering is implemented in `django_app/conversations/views.py::_owned_conversation`; existing owner tests pass. FastAPI scope currently comes from environment and is not bound to the Django user's membership. Therefore conversation isolation is present, but tenant/document isolation is not. The architecture needs a human-approved distinction between shared company knowledge and tenant-private corpora. No staging tenant implementation or test was created in this milestone.
