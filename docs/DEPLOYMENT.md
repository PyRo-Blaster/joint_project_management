# Deployment

The app ships as one Docker image serving the API and the built frontend on port 8000.
A new server needs only Docker and a directory containing `docker-compose.yml` and `.env`.

## Get the image

**From GHCR (built and published by CI on version tags):**

```bash
export IMAGE=ghcr.io/<owner>/<repo>     # e.g. ghcr.io/pyro-blaster/joint_project_management
export APP_VERSION=1.0.0                 # a published tag, or `latest`
docker compose pull
docker compose up -d
```

**Offline (no registry access) — copy a tarball:**

```bash
# On a machine with the image (or after `docker compose build`):
docker save "$IMAGE:$APP_VERSION" | gzip > cmc-tracker.tar.gz
# On the server:
gunzip -c cmc-tracker.tar.gz | docker load
docker compose up -d
```

`docker-compose.yml` references the image as `${IMAGE:-joint-cmc-tracker}:${APP_VERSION:-latest}`,
so set `IMAGE`/`APP_VERSION` in `.env` for registry or tarball images; leave them unset to run a
locally built `joint-cmc-tracker:latest` (`docker compose up -d --build`).

## First run

Copy `.env.example` to `.env` and set at least `SECRET_KEY`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`.
On start the container migrates, creates the first admin, seeds vocabularies, and — if
`INITIAL_IMPORT_PATH` points at a mounted xlsx and the program has no items — imports it once.
Open `http://localhost:8000`.

## Profiles

- **PostgreSQL:** set `DATABASE_URL=postgresql+psycopg://cmc:<pw>@postgres:5432/cmc` and
  `POSTGRES_PASSWORD` in `.env`, then `docker compose --profile postgres up -d`. The same
  migrations apply; the entrypoint waits for the database before migrating.
- **HTTPS (Caddy):** set `DOMAIN` and `APP_ORIGIN=https://$DOMAIN`, then
  `docker compose --profile proxy up -d`. Caddy obtains and renews certificates automatically.
  Combine profiles: `docker compose --profile postgres --profile proxy up -d`.

## Backup & restore

- **SQLite (default):** the database is one file on the `app-data` volume. Back up with
  `docker compose cp app:/data/app.db ./app.db.bak` (or copy the volume). Restore by placing the
  file back before starting.
- **PostgreSQL:** use `pg_dump`/`pg_restore` against the `postgres` service.

## Upgrade

`docker compose pull && docker compose up -d` (registry), or load a newer tarball and
`docker compose up -d`. Migrations run automatically on start; back up first.

## Release (maintainers)

Tag a version on the default branch to publish the image to GHCR:

```bash
git tag v1.0.0 && git push origin v1.0.0   # triggers .github/workflows/release.yml
```
