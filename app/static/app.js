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
                const res = await fetch("/api/scan", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ url }),
                });
                const data = await res.json();
                if (res.ok) {
                    window.location.href = `/results/${data.id}`;
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
        const res = await fetch(`/api/scan/${scanId}`);
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

function renderResults(data) {
    document.getElementById("scan-url").textContent = data.url;

    const summary = data.summary || {};
    document.getElementById("us-count").textContent = summary.us_count || 0;
    document.getElementById("eu-count").textContent = summary.eu_count || 0;
    document.getElementById("unknown-count").textContent = summary.unknown_count || 0;

    const euPct = summary.total_ips > 0
        ? Math.round((summary.eu_count / summary.total_ips) * 100)
        : 0;
    const meterFill = document.getElementById("meter-fill");
    meterFill.style.width = `${euPct}%`;
    meterFill.className = `meter-fill ${euPct >= 80 ? "safe" : euPct >= 50 ? "warning" : "danger"}`;
    document.getElementById("meter-label").textContent =
        `${euPct}% van het verkeer binnen EU-jurisdictie`;

    const tbody = document.getElementById("ip-tbody");
    tbody.textContent = "";
    for (const ip of data.ip_analyses) {
        const row = document.createElement("tr");
        row.className = ip.cloud_act_risk ? "row-danger" : "row-safe";

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
        const badge = document.createElement("span");
        const safeJurisdiction = ip.jurisdiction === "us" ? "us" : ip.jurisdiction === "eu" ? "eu" : "unknown";
        badge.className = `badge badge-${safeJurisdiction}`;
        badge.textContent = ip.jurisdiction.toUpperCase();
        jurisdictionTd.appendChild(badge);
        row.appendChild(jurisdictionTd);

        const riskTd = document.createElement("td");
        riskTd.textContent = ip.cloud_act_risk ? "Ja" : "Nee";
        row.appendChild(riskTd);

        tbody.appendChild(row);
    }
}
