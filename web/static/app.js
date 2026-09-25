const hero = document.getElementById("hero");
const thread = document.getElementById("thread");
const form = document.getElementById("form");
const input = document.getElementById("input");
const send = document.getElementById("send");
const modelMeta = document.getElementById("modelMeta");

let busy = false;

async function boot() {
  try {
    const res = await fetch("/api/health");
    const data = await res.json();
    if (data.model) modelMeta.textContent = `${data.model} · local`;
  } catch (_) {
    modelMeta.textContent = "offline";
  }
  input.focus();
}

function showThread() {
  if (!thread.hidden) return;
  hero.hidden = true;
  thread.hidden = false;
  thread.style.display = "block";
}

function addMessage(role, text, sources = []) {
  showThread();
  const el = document.createElement("article");
  el.className = `msg ${role}`;
  const roleLabel = role === "user" ? "You" : "Athena";
  el.innerHTML = `<div class="msg-role">${roleLabel}</div><div class="msg-body"></div>`;
  el.querySelector(".msg-body").textContent = text;
  if (sources.length) {
    const box = document.createElement("div");
    box.className = "sources";
    sources.forEach((s) => {
      const span = document.createElement("span");
      span.className = "source";
      span.textContent = s;
      box.appendChild(span);
    });
    el.appendChild(box);
  }
  thread.appendChild(el);
  thread.scrollTop = thread.scrollHeight;
  return el;
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  if (busy) return;
  const q = input.value.trim();
  if (!q) return;

  busy = true;
  send.disabled = true;
  input.value = "";
  addMessage("user", q);

  const pending = addMessage("assistant", "Думаю");
  pending.classList.add("pending");
  pending.querySelector(".msg-body").innerHTML = 'Думаю<span class="dots"></span>';

  try {
    const res = await fetch("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: q }),
    });
    if (!res.ok) {
      let detail = `HTTP ${res.status}`;
      try {
        const err = await res.json();
        if (err?.detail) detail = typeof err.detail === "string" ? err.detail : JSON.stringify(err.detail);
      } catch (_) {}
      throw new Error(detail);
    }    const data = await res.json();
    pending.classList.remove("pending");
    pending.querySelector(".msg-body").textContent = data.answer || "Пустой ответ";
    if (data.sources?.length) {
      const box = document.createElement("div");
      box.className = "sources";
      data.sources.forEach((s) => {
        const span = document.createElement("span");
        span.className = "source";
        span.textContent = s;
        box.appendChild(span);
      });
      pending.appendChild(box);
    }
  } catch (err) {
    pending.classList.remove("pending");
    pending.querySelector(".msg-body").textContent =
      "Не удалось получить ответ. Проверьте Ollama и сервер.";
    console.error(err);
  } finally {
    busy = false;
    send.disabled = false;
    input.focus();
    thread.scrollTop = thread.scrollHeight;
  }
});

boot();
