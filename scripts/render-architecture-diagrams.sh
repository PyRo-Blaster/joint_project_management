#!/usr/bin/env bash
# Render every Mermaid block tagged `<!-- diagram: NAME -->` in the architecture
# document to docs/superpowers/architecture/diagrams/NAME.svg.
# The Markdown is the single source: edit a diagram there, then run this.
#
# Needs Node (npx) and a Chromium. Set CHROME_PATH if Puppeteer cannot find one.
# Usage: scripts/render-architecture-diagrams.sh   (from the repository root)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DOC="$ROOT/docs/superpowers/architecture/2026-09-25-architecture-and-schema-as-built.md"
OUT="$ROOT/docs/superpowers/architecture/diagrams"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$OUT"

python3 - "$DOC" "$WORK" <<'PY'
import re, sys, pathlib
doc, work = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"), pathlib.Path(sys.argv[2])
pattern = re.compile(r"<!-- diagram: ([\w-]+) -->\s*```mermaid\n(.*?)```", re.S)
found = pattern.findall(doc)
if not found:
    sys.exit("no tagged diagrams found")
for name, body in found:
    (work / f"{name}.mmd").write_text(body, encoding="utf-8")
print(f"{len(found)} diagrams")
PY

CHROME="${CHROME_PATH:-$(find /opt/pw-browsers -maxdepth 3 -name chrome -type f 2>/dev/null | head -1)}"
if [[ -n "$CHROME" ]]; then
  printf '{"executablePath":"%s","args":["--no-sandbox"]}' "$CHROME" > "$WORK/puppeteer.json"
else
  printf '{"args":["--no-sandbox"]}' > "$WORK/puppeteer.json"
fi
printf '{"theme":"neutral"}' \
  > "$WORK/mermaid.json"

for source in "$WORK"/*.mmd; do
  name="$(basename "$source" .mmd)"
  npx -y @mermaid-js/mermaid-cli@11 -q -i "$source" -o "$OUT/$name.svg" \
    -p "$WORK/puppeteer.json" -c "$WORK/mermaid.json" -b white
  echo "rendered diagrams/$name.svg"
done
