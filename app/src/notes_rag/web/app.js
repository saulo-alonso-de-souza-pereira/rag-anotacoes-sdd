const state = { user: null, notes: [], editing: null, semanticTimer: null };
const byId = (id) => document.getElementById(id);
const status = (message) => { byId("status").textContent = message; };
const csrf = () => document.cookie.split("; ").find((item) => item.startsWith("notes_csrf="))?.split("=")[1] || "";

async function api(path, options = {}) {
  const method = options.method || "GET";
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (!["GET", "HEAD"].includes(method)) headers["X-CSRF-Token"] = decodeURIComponent(csrf());
  const response = await fetch("/api/v1" + path, { credentials: "same-origin", ...options, method, headers });
  if (response.status === 204) return null;
  const body = await response.json();
  if (!response.ok) {
    const error = new Error(body.error?.message || "Não foi possível concluir a operação.");
    error.code = body.error?.code; throw error;
  }
  return body;
}

function show(view) {
  ["auth", "notes", "search", "chat"].forEach((name) => {
    byId(name + "-view").hidden = name !== view;
  });
}

function escapeHtml(value) {
  const node = document.createElement("div"); node.textContent = value; return node.innerHTML;
}

function authForm() {
  byId("auth-content").innerHTML = '<form id="auth-form"><label>Nome de usuário <input name="username" autocomplete="username" required minlength="3"></label><label>Senha <input name="password" type="password" autocomplete="current-password" required minlength="12"></label><div class="actions"><button name="action" value="login">Entrar</button><button name="action" value="register">Cadastrar</button></div></form>';
  byId("auth-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const payload = JSON.stringify(Object.fromEntries(new FormData(event.currentTarget)));
    try {
      if (event.submitter.value === "register") {
        await api("/auth/register", { method: "POST", body: payload });
        status("Cadastro concluído. Agora entre.");
      } else { await api("/auth/login", { method: "POST", body: payload }); await bootstrap(); }
    } catch (error) { status(error.message); }
  });
}

function noteForm(note) {
  const title = escapeHtml(note?.title || "");
  const content = escapeHtml(note?.content || "");
  return '<form id="note-form"><label>Título <input name="title" required maxlength="200" value="' + title + '"></label><label>Conteúdo <textarea name="content" required maxlength="100000">' + content + '</textarea></label><div class="actions"><button>Salvar</button>' + (note ? '<button type="button" id="cancel-edit">Cancelar</button>' : "") + '</div></form>';
}

async function renderNotes() {
  window.clearTimeout(state.semanticTimer);
  const page = await api("/notes"); state.notes = page.items;
  const current = state.editing ? await api("/notes/" + state.editing) : null;
  const rows = state.notes.map((note) => '<li><button class="note-title" data-edit="' + note.id + '">' + escapeHtml(note.title) + '</button><span class="semantic ' + note.semantic_status + '">' + note.semantic_status + '</span>' + (note.semantic_status === "failed" ? '<button data-retry="' + note.id + '">Tentar indexar novamente</button>' : "") + '<button class="danger" data-delete="' + note.id + '">Excluir</button></li>').join("");
  byId("notes-content").innerHTML = noteForm(current) + '<ul class="note-list">' + (rows || "<li>Nenhuma anotação.</li>") + "</ul>";
  byId("note-form").addEventListener("submit", saveNote);
  byId("cancel-edit")?.addEventListener("click", () => { state.editing = null; renderNotes(); });
  document.querySelectorAll("[data-edit]").forEach((button) => button.addEventListener("click", () => { state.editing = button.dataset.edit; renderNotes(); }));
  document.querySelectorAll("[data-delete]").forEach((button) => button.addEventListener("click", async () => {
    if (!window.confirm("Excluir permanentemente esta anotação?")) return;
    try { await api("/notes/" + button.dataset.delete, { method: "DELETE" }); state.editing = null; await renderNotes(); }
    catch (error) { status(error.message); }
  }));
  document.querySelectorAll("[data-retry]").forEach((button) => button.addEventListener("click", async () => {
    try { await api("/notes/" + button.dataset.retry + "/retry-indexing", { method: "POST" }); status("Indexação reiniciada."); await renderNotes(); }
    catch (error) { status(error.message); }
  }));
  if (state.notes.some((note) => ["pending", "processing"].includes(note.semantic_status))) {
    state.semanticTimer = window.setTimeout(renderNotes, 1500);
  }
}

function renderSearch() {
  byId("search-content").innerHTML = '<form id="search-form"><label>O que você procura? <input name="query" required maxlength="2000"></label><button>Buscar</button></form><div id="search-results" aria-live="polite"><p>Digite uma ideia para encontrar anotações relacionadas.</p></div>';
  byId("search-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const query = new FormData(event.currentTarget).get("query");
    try {
      const body = await api("/search/semantic", { method: "POST", body: JSON.stringify({ query }) });
      const items = body.results.map((item) => '<article class="search-result"><h3>' + escapeHtml(item.title) + '</h3><p>' + escapeHtml(item.excerpt) + '</p><a href="#" data-source="' + item.note_id + '">Abrir fonte</a></article>').join("");
      byId("search-results").innerHTML = items || "<p>Nenhuma anotação suficientemente relacionada.</p>";
      document.querySelectorAll("[data-source]").forEach((link) => link.addEventListener("click", (click) => {
        click.preventDefault(); state.editing = link.dataset.source; show("notes"); renderNotes();
      }));
    } catch (error) { status(error.message); }
  });
}

function renderChat() {
  byId("chat-content").innerHTML = '<form id="chat-form"><label>Pergunte às suas anotações <textarea name="message" required maxlength="4000"></textarea></label><button>Enviar</button></form><div id="chat-messages"></div>';
  byId("chat-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = event.currentTarget.querySelector("button");
    const message = new FormData(event.currentTarget).get("message");
    button.disabled = true; status("Consultando suas anotações...");
    try {
      const body = await api("/chat/messages", { method: "POST", body: JSON.stringify({ message }) });
      const sources = body.sources.map((source) => '<li><a href="#" data-source="' + source.note_id + '">' + escapeHtml(source.title) + '</a><p>' + escapeHtml(source.excerpt) + '</p></li>').join("");
      const created = body.created_note ? '<p><a href="#" data-source="' + body.created_note.id + '">Abrir anotação criada</a></p>' : "";
      byId("chat-messages").innerHTML = '<article><p>' + escapeHtml(body.answer) + '</p>' + (sources ? '<h3>Fontes</h3><ul>' + sources + '</ul>' : "") + created + '</article>';
      document.querySelectorAll("#chat-messages [data-source]").forEach((link) => link.addEventListener("click", (click) => {
        click.preventDefault(); state.editing = link.dataset.source; show("notes"); renderNotes();
      }));
      status(body.needs_clarification ? "O chatbot precisa de mais informações." : "Resposta concluída.");
    } catch (error) { status(error.message); }
    finally { button.disabled = false; }
  });
}

async function saveNote(event) {
  event.preventDefault(); const payload = Object.fromEntries(new FormData(event.currentTarget));
  try {
    if (state.editing) {
      const current = await api("/notes/" + state.editing);
      await api("/notes/" + state.editing, { method: "PATCH", headers: { "If-Match": '"' + current.version + '"' }, body: JSON.stringify(payload) });
    } else { await api("/notes", { method: "POST", body: JSON.stringify(payload) }); }
    state.editing = null; status("Anotação salva."); await renderNotes();
  } catch (error) { status(error.code === "version_conflict" ? "A anotação mudou. Recarregue antes de salvar." : error.message); }
}

async function bootstrap() {
  try { state.user = await api("/auth/me"); renderSearch(); renderChat(); show("notes"); await renderNotes(); }
  catch { state.user = null; show("auth"); authForm(); }
}

document.querySelectorAll("[data-view]").forEach((button) => button.addEventListener("click", () => { if (state.user) { show(button.dataset.view); if (button.dataset.view === "search") renderSearch(); if (button.dataset.view === "chat") renderChat(); } }));
byId("logout").addEventListener("click", async () => { try { await api("/auth/logout", { method: "POST" }); } finally { await bootstrap(); } });
bootstrap();
