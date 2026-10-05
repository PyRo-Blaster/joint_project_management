# Updating an existing database

The public application uses `org_a`, `org_b`, and `joint` as organization codes,
with “Organization A” and “Organization B” as display labels. Existing
organization codes must be converted before running the updated application.

Stop application writers and back up the database. Set `LEGACY_ORG_A` and
`LEGACY_ORG_B` privately to the two existing organization codes, preserving their
existing order and meaning. Run `uv run alembic upgrade head` from `backend/`.
The migration updates users, action ownership, invitations, and organization
references in audit summaries and change JSON. It preserves IDs, roles, unrelated
fields, and the shared `joint` ownership value. Missing mappings stop the migration
before it changes any schema or records.

Fresh databases require no legacy mapping. Keep any existing deployment-specific
program code in the private `PROGRAM_CODE` environment setting; the public default
is a demo identifier. Update API clients and import override values to use the
neutral codes at the same time as the application. Test the migration against a
database copy before deploying. Downgrading keeps neutral organization identifiers.

Removing values from the public source does not update old Git commits, tags,
discussion edit history, or retained build artifacts. Those require separate cleanup.
