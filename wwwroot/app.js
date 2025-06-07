let thread = null, vs_id = null;

async function send() {
  const file = fileInp.files[0];
  if (file) {
    const fd = new FormData();
    fd.append("file", file);
    if (thread) fd.append("thread_id", thread);
    if (vs_id)  fd.append("vs_id", vs_id);

    const upResp = await fetch("/api/upload", { method: "POST", body: fd });
    if (!upResp.ok) {
      log.textContent += "Error al subir archivo: " + upResp.status + "\n";
      return;
    }
    const up = await upResp.json();
    vs_id = up.vs_id;
    thread = up.thread_id;
    fileInp.value = "";
  }

  const txt = msg.value.trim();
  if (!txt) return;

  log.textContent += "👤 " + txt + "\n";

  const chatResp = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message: txt, thread_id: thread, vs_id })
  });

  if (!chatResp.ok) {
    log.textContent += "Error en chat: " + chatResp.status + "\n";
    return;
  }

  const data = await chatResp.json();
  thread = data.thread_id;
  vs_id = data.vs_id;
  log.textContent += "🤖 " + data.reply + "\n\n";
  msg.value = "";
}
