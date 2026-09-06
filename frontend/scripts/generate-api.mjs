#!/usr/bin/env node
/**
 * Regenerate OpenAPI TypeScript types.
 *
 * Usage:
 *   Start the API so /api/openapi.json is reachable, OR
 *   OPENAPI_FILE=../path/openapi.json  then run the generate:api script.
 *
 * Default URL: http://127.0.0.1:8000/api/openapi.json
 */
import { execFileSync } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const outPath = resolve(__dirname, "../src/lib/api/schema.d.ts");
const openapiFile = process.env.OPENAPI_FILE;
const openapiUrl = process.env.OPENAPI_URL ?? "http://127.0.0.1:8000/api/openapi.json";

mkdirSync(dirname(outPath), { recursive: true });

let input = openapiUrl;
if (openapiFile) {
  input = resolve(openapiFile);
} else {
  const res = await fetch(openapiUrl);
  if (!res.ok) {
    console.error(`Failed to fetch OpenAPI from ${openapiUrl}: ${res.status}`);
    console.error("Start the API or set OPENAPI_FILE to a local openapi.json");
    process.exit(1);
  }
  const tmp = resolve(__dirname, "../.openapi.cache.json");
  writeFileSync(tmp, await res.text());
  input = tmp;
}

const bin = resolve(__dirname, "../node_modules/.bin/openapi-typescript");
execFileSync(bin, [input, "-o", outPath], { stdio: "inherit" });
console.log(`Wrote ${outPath}`);
