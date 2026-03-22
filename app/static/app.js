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

    const poll = async () => {
        const res = await fetch(`${BASE}/api/scan/${scanId}`);
        const data = await res.json();

        if (data.status === "done") {
            loading.classList.add("hidden");
            results.classList.remove("hidden");
            renderResults(data);
        } else if (data.status === "error") {
            loading.querySelector("p").textContent = "Scan is mislukt. Probeer het opnieuw.";
            loading.querySelector(".spinner").style.display = "none";
        } else {
            setTimeout(poll, 3000);
        }
    };
    poll();
}

function classifyRisk(ip) {
    const isEuServer = ip.country_code && isEuCountry(ip.country_code);
    const isUsParent = ip.jurisdiction === "us";

    if (!isUsParent && isEuServer) {
        return "low";
    }
    if (isUsParent && isEuServer) {
        return "medium";
    }
    if (isUsParent || !isEuServer) {
        return "high";
    }
    return "unknown";
}

function isEuCountry(code) {
    const euCountries = [
        "AT","BE","BG","HR","CY","CZ","DK","EE","FI","FR",
        "DE","GR","HU","IE","IT","LV","LT","LU","MT","NL",
        "PL","PT","RO","SK","SI","ES","SE",
        "NO","IS","LI","CH"
    ];
    return euCountries.includes(String(code).toUpperCase());
}

function riskLabel(level) {
    const labels = {
        low: "Soeverein",
        medium: "Aandacht vereist",
        high: "Significant risico",
        unknown: "Onbekend"
    };
    return labels[level] || "Onbekend";
}

function renderResults(data) {
    document.getElementById("scan-url").textContent = data.url;

    const summary = data.summary || {};
    const ipList = data.ip_analyses || [];

    let highCount = 0;
    let mediumCount = 0;
    let lowCount = 0;
    let unknownCount = 0;

    for (const ip of ipList) {
        const risk = classifyRisk(ip);
        if (risk === "high") highCount++;
        else if (risk === "medium") mediumCount++;
        else if (risk === "low") lowCount++;
        else unknownCount++;
    }

    document.getElementById("us-count").textContent = String(highCount);
    document.getElementById("attention-count").textContent = String(mediumCount);
    document.getElementById("eu-count").textContent = String(lowCount);
    document.getElementById("unknown-count").textContent = String(unknownCount);

    const total = ipList.length || 1;
    const sovereignPct = Math.round((lowCount / total) * 100);
    const meterFill = document.getElementById("meter-fill");
    meterFill.style.width = `${sovereignPct}%`;

    if (sovereignPct >= 80) {
        meterFill.className = "meter-fill safe";
    } else if (sovereignPct >= 50) {
        meterFill.className = "meter-fill warning";
    } else {
        meterFill.className = "meter-fill danger";
    }

    document.getElementById("meter-label").textContent =
        `${sovereignPct}% van de infrastructuur is soeverein (EU-bedrijf, EU-servers)`;

    const tbody = document.getElementById("ip-tbody");
    tbody.textContent = "";

    for (const ip of ipList) {
        const risk = classifyRisk(ip);
        const row = document.createElement("tr");

        if (risk === "high") {
            row.className = "row-danger";
        } else if (risk === "medium") {
            row.className = "row-warning";
        } else {
            row.className = "row-safe";
        }

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

        const jurisdictionTd = document.createElement("td");
        jurisdictionTd.textContent = ip.jurisdiction
            ? String(ip.jurisdiction).toUpperCase()
            : "-";
        row.appendChild(jurisdictionTd);

        const riskTd = document.createElement("td");
        const badge = document.createElement("span");
        const badgeClass = risk === "high" ? "badge-risk-high"
            : risk === "medium" ? "badge-risk-medium"
            : risk === "low" ? "badge-risk-low"
            : "badge-unknown";
        badge.className = `badge ${badgeClass}`;
        badge.textContent = riskLabel(risk);
        riskTd.appendChild(badge);
        row.appendChild(riskTd);

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
