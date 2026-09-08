/** Trigger a browser download of the export endpoint. Cookie-authenticated, same-origin GET;
 * the server sets Content-Disposition, so a transient anchor is enough. */
export function downloadExport(params: URLSearchParams): void {
  const qs = params.toString();
  const a = document.createElement("a");
  a.href = `/api/export/excel${qs ? `?${qs}` : ""}`;
  a.rel = "noopener";
  document.body.appendChild(a);
  a.click();
  a.remove();
}
