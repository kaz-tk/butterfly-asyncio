/**
 * Butterfly xterm.js client
 *
 * Protocol:
 *   Binary frames (client→server): raw terminal input
 *   Text frames (client→server): JSON {"type": "resize", "cols": N, "rows": N}
 *   Binary frames (server→client): raw terminal output
 *   Text frames (server→client): JSON {"type": "session", "id": "..."} / {"type": "exit"}
 */
(function () {
    "use strict";

    // --- Theme management ---
    var currentTheme = localStorage.getItem("butterfly-theme") || "default";
    var defaultThemeColors = {
        background: "#1a1a2e",
        foreground: "#e0e0e0",
        cursor: "#e0e0e0",
        selectionBackground: "rgba(255, 255, 255, 0.2)",
    };

    function loadTheme(name, callback) {
        var xhr = new XMLHttpRequest();
        xhr.open("GET", "/api/themes/" + name);
        xhr.onload = function () {
            if (xhr.status === 200) {
                try {
                    var theme = JSON.parse(xhr.responseText);
                    callback(theme);
                } catch (e) {
                    callback(defaultThemeColors);
                }
            }
        };
        xhr.onerror = function () { callback(defaultThemeColors); };
        xhr.send();
    }

    function applyTheme(name) {
        loadTheme(name, function (colors) {
            term.options.theme = colors;
            document.body.style.background = colors.background || "#000";
            currentTheme = name;
            localStorage.setItem("butterfly-theme", name);
        });
    }

    // --- Terminal setup ---
    var term = new Terminal({
        cursorBlink: true,
        fontSize: 14,
        fontFamily: "'Source Code Pro', 'Fira Code', 'Cascadia Code', monospace",
        theme: defaultThemeColors,
        allowProposedApi: true,
    });

    var fitAddon = new FitAddon.FitAddon();
    var webLinksAddon = new WebLinksAddon.WebLinksAddon();

    term.loadAddon(fitAddon);
    term.loadAddon(webLinksAddon);
    term.open(document.getElementById("terminal"));
    fitAddon.fit();

    // Apply saved theme
    if (currentTheme !== "default") {
        applyTheme(currentTheme);
    }

    // --- Theme picker (Alt+T) ---
    var themePicker = null;

    function showThemePicker() {
        if (themePicker) {
            removeThemePicker();
            return;
        }
        var xhr = new XMLHttpRequest();
        xhr.open("GET", "/api/themes");
        xhr.onload = function () {
            if (xhr.status !== 200) return;
            var data = JSON.parse(xhr.responseText);
            var themes = data.themes;

            themePicker = document.createElement("div");
            themePicker.id = "theme-picker";

            var title = document.createElement("div");
            title.className = "theme-picker-title";
            title.textContent = "Theme";
            themePicker.appendChild(title);

            themes.forEach(function (name) {
                var btn = document.createElement("button");
                btn.className = "theme-btn";
                if (name === currentTheme) btn.classList.add("active");
                btn.textContent = name;
                btn.onclick = function () {
                    applyTheme(name);
                    var btns = themePicker.querySelectorAll(".theme-btn");
                    btns.forEach(function (b) { b.classList.remove("active"); });
                    btn.classList.add("active");
                };
                themePicker.appendChild(btn);
            });

            document.body.appendChild(themePicker);
        };
        xhr.send();
    }

    function removeThemePicker() {
        if (themePicker) {
            themePicker.remove();
            themePicker = null;
            term.focus();
        }
    }

    // --- Session ID from URL path ---
    function getSessionId() {
        var match = window.location.pathname.match(/\/session\/([^/]+)/);
        return match ? match[1] : null;
    }

    // --- WebSocket connection ---
    var ws = null;
    var sessionId = getSessionId();
    var reconnectDelay = 1000;
    var maxReconnectDelay = 16000;

    function connect() {
        var proto = window.location.protocol === "https:" ? "wss:" : "ws:";
        var path = sessionId ? "/ws/" + sessionId : "/ws";
        var params = "?cols=" + term.cols + "&rows=" + term.rows;
        var url = proto + "//" + window.location.host + path + params;

        ws = new WebSocket(url);
        ws.binaryType = "arraybuffer";

        ws.onopen = function () {
            reconnectDelay = 1000;
            term.focus();
        };

        ws.onmessage = function (event) {
            if (event.data instanceof ArrayBuffer) {
                term.write(new Uint8Array(event.data));
            } else {
                try {
                    var msg = JSON.parse(event.data);
                    if (msg.type === "session") {
                        sessionId = msg.id;
                        if (!getSessionId()) {
                            window.history.replaceState(null, "", "/session/" + msg.id);
                        }
                    } else if (msg.type === "exit") {
                        term.write("\r\n\x1b[1;31m[Process exited]\x1b[0m\r\n");
                    }
                } catch (e) {
                    // ignore
                }
            }
        };

        ws.onclose = function () {
            term.write("\r\n\x1b[1;33m[Disconnected \u2014 reconnecting...]\x1b[0m\r\n");
            setTimeout(function () {
                reconnectDelay = Math.min(reconnectDelay * 2, maxReconnectDelay);
                connect();
            }, reconnectDelay);
        };

        ws.onerror = function () {
            ws.close();
        };
    }

    // --- Terminal input → WebSocket (binary) ---
    term.onData(function (data) {
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(new TextEncoder().encode(data));
        }
    });

    // --- Resize handling ---
    function sendResize() {
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({
                type: "resize",
                cols: term.cols,
                rows: term.rows,
            }));
        }
    }

    term.onResize(function () {
        sendResize();
    });

    var resizeTimer = null;
    window.addEventListener("resize", function () {
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(function () {
            fitAddon.fit();
        }, 100);
    });

    // --- Session list (Alt+S) ---
    var sessionListPanel = null;

    function showSessionList() {
        if (sessionListPanel) {
            removeSessionList();
            return;
        }
        var xhr = new XMLHttpRequest();
        xhr.open("GET", "/api/sessions");
        xhr.onload = function () {
            if (xhr.status !== 200) return;
            var sessions = JSON.parse(xhr.responseText);

            sessionListPanel = document.createElement("div");
            sessionListPanel.id = "session-list";

            var title = document.createElement("div");
            title.className = "session-list-title";
            title.textContent = "Sessions (" + sessions.length + ")";
            sessionListPanel.appendChild(title);

            if (sessions.length === 0) {
                var empty = document.createElement("div");
                empty.className = "session-empty";
                empty.textContent = "No active sessions";
                sessionListPanel.appendChild(empty);
            } else {
                sessions.forEach(function (s) {
                    var item = document.createElement("a");
                    item.className = "session-item";
                    item.href = "/session/" + s.id;
                    if (s.id === sessionId) item.classList.add("active");

                    var dot = document.createElement("span");
                    dot.className = "session-status " + (s.alive ? "alive" : "dead");
                    item.appendChild(dot);

                    var idSpan = document.createElement("span");
                    idSpan.className = "session-id";
                    idSpan.textContent = s.id.substring(0, 8);
                    item.appendChild(idSpan);

                    var meta = document.createElement("div");
                    meta.className = "session-meta";
                    var created = new Date(s.created);
                    var timeStr = created.toLocaleTimeString();
                    meta.textContent = timeStr + " \u2022 " + s.clients + " client" + (s.clients !== 1 ? "s" : "") + " \u2022 " + (s.alive ? "running" : "exited");
                    item.appendChild(meta);

                    item.onclick = function (e) {
                        e.preventDefault();
                        removeSessionList();
                        // Navigate to selected session
                        if (s.id !== sessionId) {
                            window.location.href = "/session/" + s.id;
                        }
                    };
                    sessionListPanel.appendChild(item);
                });
            }

            // "New Session" button
            var newBtn = document.createElement("button");
            newBtn.className = "session-new-btn";
            newBtn.textContent = "+ New Session";
            newBtn.onclick = function () {
                removeSessionList();
                window.location.href = "/";
            };
            sessionListPanel.appendChild(newBtn);

            document.body.appendChild(sessionListPanel);
        };
        xhr.send();
    }

    function removeSessionList() {
        if (sessionListPanel) {
            sessionListPanel.remove();
            sessionListPanel = null;
            term.focus();
        }
    }

    // --- Keyboard shortcuts ---
    document.addEventListener("keydown", function (e) {
        // Alt+T: toggle theme picker
        if (e.altKey && e.key === "t") {
            e.preventDefault();
            showThemePicker();
            return;
        }
        // Alt+S: toggle session list
        if (e.altKey && e.key === "s") {
            e.preventDefault();
            showSessionList();
            return;
        }
        // Escape: close overlays
        if (e.key === "Escape") {
            if (themePicker) { removeThemePicker(); return; }
            if (sessionListPanel) { removeSessionList(); return; }
        }
    });

    // --- Start ---
    connect();
})();
