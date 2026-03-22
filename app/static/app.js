const BASE = document.documentElement.dataset.base || "";

document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("scan-form");
    if (form) {
        form.addEventListener("submit", async (e) => {
            e.preventDefault();
            const url = document.getElementById("scan-url").value;
            const statusDiv = document.getElementById("scan-status");
            const statusText = document.getElementById("status-text");
            const btn = document.getElementById("scan-btn");

            btn.disabled = true;
            statusDiv.classList.remove("hidden");
            statusText.textContent = "Scan wordt gestart...";

            try {
                const res = await fetch(`${BASE}/api/scan`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ url }),
                });
                const data = await res.json();
                if (res.ok) {
                    window.location.href = `${BASE}/results/${data.id}`;
                } else {
                    statusText.textContent = `Fout: ${data.detail || "Onbekende fout"}`;
                    btn.disabled = false;
                }
            } catch (err) {
                statusText.textContent = "Verbindingsfout. Probeer het opnieuw.";
                btn.disabled = false;
            }
        });
    }
});

async function loadResults(scanId) {
    const loading = document.getElementById("loading");
    const results = document.getElementById("results");
    const statusMsg = loading.querySelector("p");
    let pollCount = 0;

    const statusText = {
        pending: "Scan wordt voorbereid...",
        scanning: "Website wordt geladen in de browser... Dit kan 30-60 seconden duren.",
        analyzing: "IP-adressen worden geanalyseerd op soevereiniteit...",
    };

    const poll = async () => {
        pollCount++;
        const res = await fetch(`${BASE}/api/scan/${scanId}`);
        const data = await res.json();

        if (data.status === "done") {
            loading.classList.add("hidden");
            results.classList.remove("hidden");
            renderResults(data);
        } else if (data.status === "error") {
            statusMsg.textContent = "Scan is mislukt. Probeer het opnieuw.";
            loading.querySelector(".spinner").style.display = "none";
        } else {
            const msg = statusText[data.status] || "Bezig...";
            const elapsed = pollCount * 3;
            statusMsg.textContent = `${msg} (${elapsed}s)`;
            setTimeout(poll, 3000);
        }
    };
    poll();
}

function getSovereigntyLevel(ip) {
    return typeof ip.sovereignty_level === "number" ? ip.sovereignty_level : 0;
}

function sovereigntyLabel(level) {
    const labels = {
        5: "Volledig soeverein",
        4: "Grotendeels soeverein",
        3: "Gedeeltelijk soeverein",
        2: "Beperkt soeverein",
        1: "Minimaal soeverein",
        0: "Niet soeverein",
    };
    return labels[level] || "Onbekend";
}

function levelBadgeClass(level) {
    return `badge-level-${level}`;
}

function levelRowClass(level) {
    if (level >= 4) return "row-level-high";
    if (level >= 2) return "row-level-mid";
    return "row-level-low";
}

function renderResults(data) {
    document.getElementById("scan-url").textContent = data.url;

    const summary = data.summary || {};
    const ipList = data.ip_analyses || [];

    // Count per level
    const distribution = { 0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0 };
    let levelSum = 0;

    for (const ip of ipList) {
        const level = getSovereigntyLevel(ip);
        distribution[level] = (distribution[level] || 0) + 1;
        levelSum += level;
    }

    const total = ipList.length || 1;
    const averageLevel = (levelSum / total).toFixed(1);

    // Meter: average level on 0-5 scale
    const meterFill = document.getElementById("meter-fill");
    const meterPct = Math.round((averageLevel / 5) * 100);
    meterFill.style.width = `${meterPct}%`;

    if (averageLevel >= 4) {
        meterFill.className = "meter-fill meter-level-high";
    } else if (averageLevel >= 2.5) {
        meterFill.className = "meter-fill meter-level-mid";
    } else {
        meterFill.className = "meter-fill meter-level-low";
    }

    document.getElementById("meter-label").textContent =
        `Gemiddeld niveau: ${averageLevel} / 5`;

    // Distribution bars
    const distContainer = document.getElementById("level-distribution");
    distContainer.textContent = "";

    for (let lvl = 5; lvl >= 0; lvl--) {
        const count = distribution[lvl] || 0;
        const pct = Math.round((count / total) * 100);

        const row = document.createElement("div");
        row.className = "dist-row";

        const label = document.createElement("span");
        label.className = "dist-label";
        label.textContent = `${lvl} — ${sovereigntyLabel(lvl)}`;

        const barOuter = document.createElement("div");
        barOuter.className = "dist-bar-outer";

        const barInner = document.createElement("div");
        barInner.className = `dist-bar-inner dist-bar-level-${lvl}`;
        barInner.style.width = `${pct}%`;

        const countSpan = document.createElement("span");
        countSpan.className = "dist-count";
        countSpan.textContent = `${count} (${pct}%)`;

        barOuter.appendChild(barInner);
        row.appendChild(label);
        row.appendChild(barOuter);
        row.appendChild(countSpan);
        distContainer.appendChild(row);
    }

    // Table
    const tbody = document.getElementById("ip-tbody");
    tbody.textContent = "";

    for (const ip of ipList) {
        const level = getSovereigntyLevel(ip);
        const row = document.createElement("tr");
        row.className = levelRowClass(level);

        const cells = [
            ip.ip_address,
            ip.asn || "-",
            ip.asn_org || "-",
            ip.country_code || "-",
            ip.parent_company || "-",
        ];
        for (const text of cells) {
            const td = document.createElement("td");
            td.textContent = String(text);
            row.appendChild(td);
        }

        const levelTd = document.createElement("td");
        const badge = document.createElement("span");
        badge.className = `badge ${levelBadgeClass(level)}`;
        badge.textContent = `${level} — ${ip.sovereignty_label || sovereigntyLabel(level)}`;
        levelTd.appendChild(badge);
        row.appendChild(levelTd);

        tbody.appendChild(row);
    }
}

// Auto-load results if scan-id is present on the script tag
(function () {
    const script = document.querySelector("script[data-scan-id]");
    if (script) {
        const scanId = script.dataset.scanId;
        if (scanId) {
            document.addEventListener("DOMContentLoaded", () => loadResults(scanId));
        }
    }
})();
