# Dependency Hub — Database Security Model

## 1. Security Architecture Principles

Dependency Hub is designed following strict defense-in-depth principles:

1. **Zero-Trust Multi-Tenancy**: Tenant data boundaries are enforced at the root organization level.
2. **Cryptographic Protection of Assets**: Source code artifacts are stored encrypted at rest using envelope encryption.
3. **No Sensitive Secrets in Database**: PostgreSQL never stores master encryption keys, plaintext passwords, or raw session tokens.
4. **Append-Only Auditing**: Audit records are immutable and append-only.
5. **Least Privilege RBAC**: Granular role-to-permission mapping scopes operational capabilities.

---

## 2. Multi-Tenant Data Isolation

- **Tenant Boundary**: Every business entity (`projects`, `findings`, `policies`, `audit_logs`) links directly or hierarchically to `organizations.id`.
- **Composite Slug Scoping**: Projects use unique composite keys `(organization_id, slug)`, preventing name collision and isolating project namespaces across tenants.
- **Membership Verification**: User authorization is verified through active records in `organization_members` before admitting data queries.

---

## 3. Credential & Authentication Security

### Passwords
- **No Plaintext Passwords**: Passwords must be hashed using modern algorithms (Argon2id or bcrypt) before reaching the persistence layer.
- **Verification & Soft Deletion**: The `users` table tracks verification (`is_verified`) and soft deletion (`deleted_at`) to preserve audit references without leaving accounts accessible.

### Refresh Tokens
- **One-Way Token Hashing**: The `refresh_tokens` table stores only cryptographic hashes (`token_hash` e.g., SHA-256) of raw tokens.
- **Revocation & Expiry**: Session revocation is tracked via `revoked_at` and `expires_at`, with indexed queries (`idx_refresh_tokens_user_active`) allowing instantaneous revocation.

---

## 4. Envelope Encryption & Key Management Boundary

```text
External Key Management Service (KMS)
[HashiCorp Vault / AWS KMS / GCP KMS / Azure Key Vault]
         │
         ▼  Master Key / Key Encryption Key (KEK)
   Encrypts / Decrypts DEK
         │
         ▼
Data Encryption Key (DEK) ──(AES-256-GCM)──► Stored Project Artifact (Encrypted Zip/Tar)
         │
         ▼
[PostgreSQL Database]
Stored in `artifact_encryption_metadata`:
- initialization_vector (IV / Nonce)
- authentication_tag (GCM Tag)
- encrypted_dek_reference (Encrypted DEK)
- checksum (SHA-256 Ciphertext Hash)
- key_reference (KMS Key Identifier)
```

### Critical Security Rule
- **PostgreSQL NEVER contains the Master Key or Plaintext DEK**.
- Compromising the database alone does NOT expose customer source code, as decrypting the stored artifacts requires access to the external KMS.

---

## 5. Ephemeral Analysis Sandboxes & Source-Code Protection

- **Untouched Original Artifact**: The `project_artifacts` row is strictly immutable (`is_immutable=True`).
- **Temporary Workspace Sandboxes**: The scanner extracts code only into temporary `analysis_workspaces` records with finite lifetimes (`expires_at`, `destroyed_at`).
- **Destruction**: Workspaces are purged and destroyed following scan completion, ensuring customer source code is not retained in analysis environments.

---

## 6. Immutable Audit Trail

- **Append-Only Event Ledger**: The `audit_logs` table records actor (`user_id`), tenant (`organization_id`), event type (`action`), affected entity (`entity_type`, `entity_id`), client network context (`ip_address`, `user_agent`), and differential changes (`old_values`, `new_values`).
- **No Update / Delete APIs**: Applications must never expose endpoints allowing modification or truncation of audit records.
