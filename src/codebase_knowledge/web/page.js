let scanId = "";
document.getElementById("scan").addEventListener("click", () => run(async () => {
  const created = await api("/api/scans", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({files: [{path: document.getElementById("path").value, content: document.getElementById("content").value}]})
  });
  scanId = created.id;
  return created;
}));
document.getElementById("list").addEventListener("click", () => run(() => api("/api/scans")));
document.getElementById("ask").addEventListener("click", () => run(() => api("/api/scans/" + encodeURIComponent(scanId) + "/ask", {
  method: "POST",
  headers: {"Content-Type": "application/json"},
  body: JSON.stringify({question: document.getElementById("question").value})
})));
