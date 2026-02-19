let token = localStorage.getItem("token");
let user = JSON.parse(localStorage.getItem("user") || "null");

const loginScreen = document.getElementById("login-screen");
const header = document.getElementById("header");
const mainPanel = document.getElementById("main-panel");
const userDisplay = document.getElementById("user-display");
const logoutBtn = document.getElementById("logout-btn");
const uploadZone = document.getElementById("upload-zone");
const fileInput = document.getElementById("file-input");
const docList = document.getElementById("doc-list");
const docEmpty = document.getElementById("doc-empty");
const chatHistory = document.getElementById("chat-history");
const chatWelcome = document.getElementById("chat-welcome");
const userInput = document.getElementById("user-input");
const sendBtn = document.getElementById("send-btn");
const statusBadge = document.getElementById("status-badge");
const memEmpty = document.getElementById("mem-empty");

function toast(msg, isError = false) {
    const el = document.getElementById("toast");
    el.textContent = msg;
    el.className = "toast" + (isError ? " error" : "");
    el.classList.add("show");
    setTimeout(() => el.classList.remove("show"), 3000);
}

function showUI() {
    if (token && user) {
        loginScreen.classList.add("hidden");
        header.style.display = "flex";
        mainPanel.style.display = "grid";
        userDisplay.textContent = user.username;
        logoutBtn.style.display = "inline-block";
        fetchDocs();
        fetchMemory();
    } else {
        loginScreen.classList.remove("hidden");
        header.style.display = "none";
        mainPanel.style.display = "none";
        userDisplay.textContent = "";
        logoutBtn.style.display = "none";
    }
}

async function api(method, path, body) {
    const opts = { method, headers: {} };
    if (token) opts.headers["Authorization"] = `Bearer ${token}`;
    if (body) {
        opts.headers["Content-Type"] = "application/json";
        opts.body = JSON.stringify(body);
    }
    const r = await fetch(path, opts);
    if (r.status === 401) {
        token = null;
        user = null;
        localStorage.removeItem("token");
        localStorage.removeItem("user");
        showUI();
        throw new Error("Session expired");
    }
    return r;
}

async function login(register = false) {
    const username = document.getElementById("username").value.trim();
    const password = document.getElementById("password").value;
    const errEl = document.getElementById("login-error");
    errEl.textContent = "";

    if (!username || !password) {
        errEl.textContent = "Enter username and password";
        return;
    }
    try {
        const r = await api("POST", `/users/${register ? "register" : "login"}`, { username, password });
        const data = await r.json();
        if (!r.ok) {
            errEl.textContent = data.detail || "Failed";
            return;
        }
        token = data.access_token;
        user = { id: data.user_id, username: data.username };
        localStorage.setItem("token", token);
        localStorage.setItem("user", JSON.stringify(user));
        showUI();
        toast(register ? "Account created" : "Signed in");
    } catch (e) {
        errEl.textContent = "Connection error";
    }
}

document.getElementById("login-btn").onclick = () => login(false);
document.getElementById("register-btn").onclick = () => login(true);
logoutBtn.onclick = () => {
    token = null;
    user = null;
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    showUI();
    toast("Signed out");
};

uploadZone.onclick = () => fileInput.click();
uploadZone.ondragover = (e) => { e.preventDefault(); uploadZone.classList.add("drag"); };
uploadZone.ondragleave = () => uploadZone.classList.remove("drag");
uploadZone.ondrop = (e) => {
    e.preventDefault();
    uploadZone.classList.remove("drag");
    if (e.dataTransfer.files.length) uploadFile(e.dataTransfer.files[0]);
};

fileInput.onchange = () => {
    if (fileInput.files.length) uploadFile(fileInput.files[0]);
    fileInput.value = "";
};

async function uploadFile(file) {
    const ext = "." + (file.name.split(".").pop() || "").toLowerCase();
    if (![".pdf", ".txt", ".md", ".html", ".htm"].includes(ext)) {
        toast("Unsupported file type. Use PDF, TXT, MD, or HTML.", true);
        return;
    }
    const fd = new FormData();
    fd.append("file", file);
    const opts = { method: "POST", headers: {} };
    if (token) opts.headers["Authorization"] = `Bearer ${token}`;
    opts.body = fd;
    try {
        const res = await fetch("/upload", opts);
        const data = await res.json();
        if (!res.ok) {
            toast(data.detail?.error || data.detail || "Upload failed", true);
            return;
        }
        fetchDocs();
        toast(`Added ${data.filename}`);
    } catch (e) {
        toast("Upload failed", true);
    }
}

async function fetchDocs() {
    const r = await api("GET", "/documents");
    if (!r.ok) return;
    const docs = await r.json();
    const countEl = document.getElementById("doc-count");
    if (countEl) countEl.textContent = docs.length ? `${docs.length} doc${docs.length > 1 ? "s" : ""}` : "";
    if (docEmpty) docEmpty.style.display = docs.length ? "none" : "block";
    docList.style.display = docs.length ? "block" : "none";
    docList.innerHTML = docs.map((d) =>
        `<li><span class="filename" title="${escapeHtml(d.filename)}">${escapeHtml(d.filename)}</span><button data-id="${d.id}" title="Remove">×</button></li>`
    ).join("");
    docList.querySelectorAll("button").forEach((b) => {
        b.onclick = async () => {
            const id = b.dataset.id;
            const delR = await api("DELETE", `/documents/${id}`);
            if (delR.ok) {
                fetchDocs();
                toast("Document removed");
            }
        };
    });
}

async function fetchMemory() {
    const r = await api("GET", "/memory");
    if (!r.ok) return;
    const data = await r.json();
    const userLines = (data.user_memory || "").split("\n").filter((l) => l.trim());
    const companyLines = (data.company_memory || "").split("\n").filter((l) => l.trim());
    const hasMem = userLines.length || companyLines.length;
    if (memEmpty) memEmpty.style.display = hasMem ? "none" : "block";
    document.getElementById("user-mem").innerHTML = userLines.map((l) => `<div class="mem-item">${escapeHtml(l)}</div>`).join("") || "";
    document.getElementById("company-mem").innerHTML = companyLines.map((l) => `<div class="mem-item">${escapeHtml(l)}</div>`).join("") || "";
}

document.querySelectorAll(".tab").forEach((t) => {
    t.onclick = () => {
        document.querySelectorAll(".tab").forEach((x) => x.classList.remove("active"));
        document.querySelectorAll(".tab-content").forEach((x) => x.classList.remove("active"));
        t.classList.add("active");
        const tabId = t.dataset.tab;
        const target = tabId === "graph" ? document.getElementById("graph-panel") : document.getElementById(tabId + "-mem");
        if (target) target.classList.add("active");
        if (tabId === "graph") renderKnowledgeGraph();
    };
});

async function fetchGraphData() {
    const r = await api("GET", "/graph/full");
    if (!r.ok) return { nodes: [], edges: [] };
    return r.json();
}

function renderKnowledgeGraph() {
    const container = document.getElementById("graph-container");
    const empty = document.getElementById("graph-empty");
    if (!container) return;
    container.innerHTML = "";
    if (!token) return;
    fetchGraphData().then((data) => {
        if (!data.nodes || data.nodes.length === 0) {
            if (empty) empty.style.display = "block";
            return;
        }
        if (empty) empty.style.display = "none";
        const w = Math.min(280, container.offsetWidth || 280);
        const h = 220;
        const colorByType = { person: "#3b82f6", org: "#22c55e", concept: "#f97316", term: "#6b7280" };
        const svg = d3.select(container).append("svg").attr("width", w).attr("height", h);
        const g = svg.append("g");
        const simulation = d3.forceSimulation(data.nodes)
            .force("link", d3.forceLink(data.edges).id((d) => d.id).distance(60))
            .force("charge", d3.forceManyBody().strength(-80))
            .force("center", d3.forceCenter(w / 2, h / 2));
        const link = g.append("g").selectAll("line")
            .data(data.edges)
            .join("line")
            .attr("stroke-width", (d) => Math.max(1, Math.min(3, d.weight || 1)))
            .attr("stroke", "#94a3b8");
        const node = g.append("g").selectAll("g")
            .data(data.nodes)
            .join("g")
            .call(d3.drag()
                .on("start", (e, d) => { e.sourceEvent.stopPropagation(); simulation.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; })
                .on("drag", (e, d) => { d.fx = e.x; d.fy = e.y; })
                .on("end", (e, d) => { simulation.alphaTarget(0); d.fx = null; d.fy = null; }));
        node.append("circle")
            .attr("r", (d) => 4 + Math.min(6, (d.degree || 0) / 2))
            .attr("fill", (d) => colorByType[d.type] || "#6b7280")
            .attr("stroke", "#fff")
            .attr("stroke-width", 1.5)
            .on("mouseover", function(e, d) {
                d3.select(this).attr("stroke", "#000").attr("stroke-width", 2);
                node.filter((n) => n.id !== d.id).style("opacity", 0.3);
                link.filter((l) => l.source.id !== d.id && l.target.id !== d.id).attr("stroke-opacity", 0.2);
            })
            .on("mouseout", function() {
                d3.select(this).attr("stroke", "#fff").attr("stroke-width", 1.5);
                node.style("opacity", 1);
                link.attr("stroke-opacity", 1);
            });
        node.append("title").text((d) => d.label || d.id);
        simulation.on("tick", () => {
            link.attr("x1", (d) => d.source.x).attr("y1", (d) => d.source.y)
                .attr("x2", (d) => d.target.x).attr("y2", (d) => d.target.y);
            node.attr("transform", (d) => `translate(${d.x},${d.y})`);
        });
    });
}

function escapeHtml(s) {
    const div = document.createElement("div");
    div.textContent = s;
    return div.innerHTML;
}

function renderCitation(c) {
    const exc = c.excerpt ? `<div class="excerpt">${escapeHtml(c.excerpt)}</div>` : "";
    return `<li><span class="source-name">${escapeHtml(c.source)}</span> <span class="chunk-ref">Chunk ${c.chunk_index}</span>${exc}</li>`;
}

function appendMessage(role, text, citations = []) {
    if (chatWelcome) chatWelcome.classList.add("hidden");
    const row = document.createElement("div");
    row.className = `message-row ${role}`;
    const avatar = role === "user" ? user?.username?.[0]?.toUpperCase() || "U" : "◇";
    row.innerHTML = `<div class="message-avatar">${avatar}</div><div class="message-bubble"><div class="message ${role}"><div class="content">${escapeHtml(text)}</div></div></div>`;
    const bubble = row.querySelector(".message");
    if (citations.length) {
        bubble.innerHTML += `<details class="citations" open><summary>Cited from ${citations.length} source${citations.length > 1 ? "s" : ""}</summary><ul>${citations.map(renderCitation).join("")}</ul></details>`;
    }
    chatHistory.appendChild(row);
    chatHistory.scrollTop = chatHistory.scrollHeight;
}

sendBtn.onclick = sendMessage;
userInput.onkeydown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
};

function autoResize(el) {
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 120) + "px";
}
userInput.addEventListener("input", () => autoResize(userInput));

async function sendMessage() {
    const text = userInput.value.trim();
    if (!text) return;
    userInput.value = "";
    autoResize(userInput);
    appendMessage("user", text);

    const isAnalysis = /analyze|weather/i.test(text);
    if (isAnalysis) {
        sendBtn.disabled = true;
        try {
            const r = await api("POST", "/analyze", { request: text });
            const data = await r.json();
            appendMessage("assistant", data.result || "Error");
        } catch (e) {
            appendMessage("assistant", "Request failed. Try again.");
        }
        sendBtn.disabled = false;
        return;
    }

    const start = Date.now();
    const url = `/ask?query=${encodeURIComponent(text)}&token=${encodeURIComponent(token || "")}`;
    const evtSource = new EventSource(url);

    let fullAnswer = "";
    const row = document.createElement("div");
    row.className = "message-row assistant";
    row.innerHTML = '<div class="message-avatar">◇</div><div class="message-bubble"><div class="message assistant"><div class="content"></div></div></div>';
    const contentEl = row.querySelector(".content");
    contentEl.parentElement.insertAdjacentHTML("beforebegin", '<div class="typing-indicator"><span></span><span></span><span></span></div>');
    const typingEl = row.querySelector(".typing-indicator");
    chatHistory.appendChild(row);
    chatHistory.scrollTop = chatHistory.scrollHeight;
    sendBtn.disabled = true;

    evtSource.onmessage = (e) => {
        if (typingEl) typingEl.remove();
        if (e.data === "[DONE]") {
            evtSource.close();
            const elapsed = Date.now() - start;
            document.getElementById("latency").textContent = elapsed < 1000 ? `${elapsed}ms` : `${(elapsed / 1000).toFixed(1)}s`;
            fetchMemory();
            sendBtn.disabled = false;
            return;
        }
        try {
            const msg = JSON.parse(e.data);
            if (msg.type === "token") {
                fullAnswer += msg.text || "";
                contentEl.textContent = fullAnswer;
            } else if (msg.type === "cached") {
                fullAnswer = msg.answer || "";
                contentEl.textContent = fullAnswer;
                if (msg.citations?.length) {
                    const det = document.createElement("details");
                    det.className = "citations";
                    det.setAttribute("open", "");
                    det.innerHTML = `<summary>Cited from ${msg.citations.length} source${msg.citations.length > 1 ? "s" : ""}</summary><ul>${msg.citations.map(renderCitation).join("")}</ul>`;
                    contentEl.parentElement.appendChild(det);
                }
            } else if (msg.type === "citations") {
                const data = msg.data || [];
                if (data.length) {
                    const det = document.createElement("details");
                    det.className = "citations";
                    det.setAttribute("open", "");
                    det.innerHTML = `<summary>Cited from ${data.length} source${data.length > 1 ? "s" : ""}</summary><ul>${data.map(renderCitation).join("")}</ul>`;
                    contentEl.parentElement.appendChild(det);
                }
            } else if (msg.type === "memory") {
                if (msg.data?.written) fetchMemory();
            } else if (msg.type === "error") {
                contentEl.textContent = msg.message || "Error";
            }
        } catch (_) {}
        chatHistory.scrollTop = chatHistory.scrollHeight;
    };

    evtSource.onerror = () => {
        evtSource.close();
        sendBtn.disabled = false;
        if (typingEl) typingEl.remove();
        if (!fullAnswer) contentEl.textContent = "Connection error. Make sure you have documents uploaded and Ollama is running.";
    };
}

async function checkHealth() {
    try {
        const r = await fetch("/health");
        const d = await r.json();
        statusBadge.title = "Ollama connected";
        statusBadge.className = "status-dot connected";
    } catch {
        statusBadge.title = "Offline";
        statusBadge.className = "status-dot error";
    }
}

checkHealth();
setInterval(checkHealth, 30000);
showUI();
