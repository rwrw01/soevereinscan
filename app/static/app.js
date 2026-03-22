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

    // New features: choices, tree, map
    if (summary.resource_tree) {
        renderTree(summary.resource_tree, data.url, ipList);
    }
    renderChoices(summary.resource_tree, ipList, data.url);
    renderMap(ipList);
}

function extractDomain(url) {
    try {
        return new URL(url).hostname;
    } catch (_) {
        return url;
    }
}

function findIpForDomain(domain, ipAnalyses) {
    for (const ip of ipAnalyses) {
        if (ip.domains && ip.domains.indexOf(domain) !== -1) return ip;
        if (ip.hostname === domain) return ip;
    }
    return null;
}

function categorizeDomain(domain) {
    const d = domain.toLowerCase();
    if (/analytics|gtag|ga\.|google-analytics|googletagmanager/.test(d)) return "Analytics";
    if (/fonts\.|typekit/.test(d)) return "Lettertypen";
    if (/pixel|track|pinterest|facebook|doubleclick|fb\.com/.test(d)) return "Tracking";
    if (/cdn\.|cloudfront|akamai|fastly|cloudflare/.test(d)) return "CDN";
    return "Overig";
}

function isThirdParty(domain, scanUrl) {
    const scanDomain = extractDomain(scanUrl);
    const scanParts = scanDomain.split(".");
    const domParts = domain.split(".");
    const scanBase = scanParts.slice(-2).join(".");
    const domBase = domParts.slice(-2).join(".");
    return domBase !== scanBase;
}

function collectTreeDomains(node, list) {
    if (!node) return list;
    list.push(node);
    if (node.children) {
        for (const child of node.children) {
            collectTreeDomains(child, list);
        }
    }
    return list;
}

/* Feature 1: Resource Tree */
function renderTree(treeData, scanUrl, ipAnalyses) {
    const container = document.getElementById("resource-tree");
    if (!container || !treeData) return;
    container.textContent = "";

    function buildNode(node, depth) {
        const li = document.createElement("li");
        const nodeDiv = document.createElement("div");
        nodeDiv.className = "tree-node";

        const thirdParty = isThirdParty(node.domain || "", scanUrl);
        if (thirdParty) nodeDiv.classList.add("tree-third-party");

        const hasChildren = node.children && node.children.length > 0;
        const startCollapsed = depth > 0;

        // Toggle indicator
        const toggle = document.createElement("span");
        toggle.className = "tree-toggle";
        toggle.textContent = hasChildren ? (startCollapsed ? "\u25B6" : "\u25BC") : " ";
        nodeDiv.appendChild(toggle);

        // Domain name
        const domainSpan = document.createElement("span");
        domainSpan.textContent = node.domain || "onbekend";
        domainSpan.className = "tree-domain";
        nodeDiv.appendChild(domainSpan);

        // Request count
        if (node.count) {
            const countSpan = document.createElement("span");
            countSpan.className = "tree-count";
            countSpan.textContent = " (" + node.count + " verzoeken)";
            nodeDiv.appendChild(countSpan);
        }

        // Hosting info from ipAnalyses
        const ipInfo = findIpForDomain(node.domain || "", ipAnalyses);
        if (ipInfo && ipInfo.asn_org) {
            const hostSpan = document.createElement("span");
            hostSpan.className = "tree-host";
            const country = ipInfo.country_code || "?";
            hostSpan.textContent = " \u2014 Gehost bij " + ipInfo.asn_org + " (" + country + ")";
            nodeDiv.appendChild(hostSpan);
        }

        // Third-party warning marker
        if (thirdParty) {
            const warn = document.createElement("span");
            warn.className = "tree-tp-label";
            warn.textContent = " \u26A0 Uw keuze";
            nodeDiv.appendChild(warn);
        }

        li.appendChild(nodeDiv);

        // Children
        if (hasChildren) {
            const childUl = document.createElement("ul");
            if (startCollapsed) childUl.classList.add("tree-children-hidden");
            for (const child of node.children) {
                childUl.appendChild(buildNode(child, depth + 1));
            }
            li.appendChild(childUl);

            nodeDiv.addEventListener("click", function () {
                const hidden = childUl.classList.toggle("tree-children-hidden");
                toggle.textContent = hidden ? "\u25B6" : "\u25BC";
            });
        }

        return li;
    }

    const rootUl = document.createElement("ul");
    rootUl.appendChild(buildNode(treeData, 0));
    container.appendChild(rootUl);
}

/* Feature 2: World Map */
function renderMap(ipAnalyses) {
    const container = document.getElementById("world-map");
    if (!container) return;
    container.textContent = "";

    const mapDiv = document.createElement("div");
    mapDiv.className = "world-map";

    const width = 800;
    const height = 400;
    const ns = "http://www.w3.org/2000/svg";

    const svg = document.createElementNS(ns, "svg");
    svg.setAttribute("viewBox", "0 0 " + width + " " + height);
    svg.setAttribute("role", "img");

    const titleEl = document.createElementNS(ns, "title");
    titleEl.textContent = "Wereldkaart met serverlocaties";
    svg.appendChild(titleEl);

    // Background
    const bg = document.createElementNS(ns, "rect");
    bg.setAttribute("width", width);
    bg.setAttribute("height", height);
    bg.setAttribute("fill", "#1a2332");
    svg.appendChild(bg);

    // Grid lines
    for (let lon = -180; lon <= 180; lon += 30) {
        const x = ((lon + 180) / 360) * width;
        const line = document.createElementNS(ns, "line");
        line.setAttribute("x1", x);
        line.setAttribute("y1", 0);
        line.setAttribute("x2", x);
        line.setAttribute("y2", height);
        line.setAttribute("stroke", "rgba(255,255,255,0.1)");
        line.setAttribute("stroke-width", "0.5");
        svg.appendChild(line);
    }
    for (let lat = -90; lat <= 90; lat += 30) {
        const y = ((90 - lat) / 180) * height;
        const line = document.createElementNS(ns, "line");
        line.setAttribute("x1", 0);
        line.setAttribute("y1", y);
        line.setAttribute("x2", width);
        line.setAttribute("y2", y);
        line.setAttribute("stroke", "rgba(255,255,255,0.1)");
        line.setAttribute("stroke-width", "0.5");
        svg.appendChild(line);
    }

    // Sovereignty level colors
    const levelColors = {
        5: "#15803d",
        4: "#22c55e",
        3: "#eab308",
        2: "#f97316",
        1: "#fb923c",
        0: "#9ca3af",
    };

    // Cluster IPs by rounded lat/lng
    const clusters = {};
    for (const ip of ipAnalyses) {
        if (ip.latitude == null || ip.longitude == null) continue;
        const lat = Math.round(ip.latitude * 10) / 10;
        const lng = Math.round(ip.longitude * 10) / 10;
        const key = lat + "," + lng;
        if (!clusters[key]) {
            clusters[key] = { lat: lat, lng: lng, count: 0, level: 5, ips: [] };
        }
        clusters[key].count++;
        const lvl = getSovereigntyLevel(ip);
        if (lvl < clusters[key].level) clusters[key].level = lvl;
        clusters[key].ips.push(ip);
    }

    // Draw dots
    for (const key of Object.keys(clusters)) {
        const c = clusters[key];
        const cx = ((c.lng + 180) / 360) * width;
        const cy = ((90 - c.lat) / 180) * height;
        const r = Math.max(4, Math.min(12, 3 + c.count * 2));

        const circle = document.createElementNS(ns, "circle");
        circle.setAttribute("cx", cx);
        circle.setAttribute("cy", cy);
        circle.setAttribute("r", r);
        circle.setAttribute("fill", levelColors[c.level] || "#9ca3af");
        circle.setAttribute("opacity", "0.85");
        circle.setAttribute("class", "map-dot");

        // Tooltip via title element
        const ipNames = c.ips.map(function (ip) {
            return (ip.asn_org || ip.ip_address) + " (" + (ip.country_code || "?") + ")";
        });
        const unique = ipNames.filter(function (v, i, a) { return a.indexOf(v) === i; });
        const tipEl = document.createElementNS(ns, "title");
        tipEl.textContent = unique.join(", ") + " — niveau " + c.level;
        circle.appendChild(tipEl);

        svg.appendChild(circle);
    }

    // "Geen locatiegegevens" message if no dots
    if (Object.keys(clusters).length === 0) {
        const txt = document.createElementNS(ns, "text");
        txt.setAttribute("x", width / 2);
        txt.setAttribute("y", height / 2);
        txt.setAttribute("text-anchor", "middle");
        txt.setAttribute("fill", "rgba(255,255,255,0.5)");
        txt.setAttribute("font-size", "14");
        txt.textContent = "Geen locatiegegevens beschikbaar";
        svg.appendChild(txt);
    }

    mapDiv.appendChild(svg);
    container.appendChild(mapDiv);
}

/* Feature 3: Choices categorization */
function renderChoices(treeData, ipAnalyses, scanUrl) {
    const container = document.getElementById("choices-container");
    if (!container) return;
    container.textContent = "";

    const allNodes = [];
    if (treeData) collectTreeDomains(treeData, allNodes);

    if (allNodes.length === 0) {
        const noData = document.createElement("p");
        noData.className = "choices-empty";
        noData.textContent = "Geen afhankelijkheidsboom beschikbaar.";
        container.appendChild(noData);
        return;
    }

    // Build categories
    const categories = {};
    const rootDomain = treeData.domain || "";

    for (const node of allNodes) {
        const domain = node.domain || "";
        const ipInfo = findIpForDomain(domain, ipAnalyses);
        const level = ipInfo ? getSovereigntyLevel(ipInfo) : null;
        const thirdParty = isThirdParty(domain, scanUrl);

        let cat;
        if (!thirdParty) {
            cat = "Hosting";
        } else {
            cat = categorizeDomain(domain);
        }

        if (!categories[cat]) categories[cat] = [];
        categories[cat].push({
            domain: domain,
            level: level,
            org: ipInfo ? (ipInfo.asn_org || "-") : "-",
            country: ipInfo ? (ipInfo.country_code || "-") : "-",
            thirdParty: thirdParty,
        });
    }

    const levelDots = {
        5: "\uD83D\uDFE2",  // green circle
        4: "\uD83D\uDFE2",
        3: "\uD83D\uDFE1",  // yellow circle
        2: "\uD83D\uDFE0",  // orange circle
        1: "\uD83D\uDD34",  // red circle
        0: "\u26AA",        // white circle
    };

    // Calculate overall average
    let totalLevel = 0;
    let levelCount = 0;
    for (const cat of Object.keys(categories)) {
        for (const item of categories[cat]) {
            if (item.level !== null) {
                totalLevel += item.level;
                levelCount++;
            }
        }
    }
    const currentAvg = levelCount > 0 ? totalLevel / levelCount : 0;

    // Calculate improvement potential (what if third-party tracking/analytics were replaced)
    let improvedTotal = totalLevel;
    let improvableCount = 0;
    for (const cat of Object.keys(categories)) {
        if (cat === "Hosting" || cat === "CDN") continue;
        for (const item of categories[cat]) {
            if (item.thirdParty && item.level !== null && item.level < 4) {
                improvedTotal += (4 - item.level);
                improvableCount++;
            }
        }
    }
    const improvedAvg = levelCount > 0 ? improvedTotal / levelCount : 0;

    // Category display order
    const catOrder = ["Hosting", "Analytics", "Lettertypen", "Tracking", "CDN", "Overig"];

    for (const cat of catOrder) {
        if (!categories[cat] || categories[cat].length === 0) continue;

        const catDiv = document.createElement("div");
        catDiv.className = "choice-category";

        // Deduplicate by domain within category
        const seen = {};
        const items = [];
        for (const item of categories[cat]) {
            if (!seen[item.domain]) {
                seen[item.domain] = true;
                items.push(item);
            }
        }

        for (const item of items) {
            const row = document.createElement("div");
            row.className = "choice-item";
            if (item.level !== null && item.level <= 2) {
                row.classList.add("choice-item-warn");
            } else if (item.level !== null && item.level >= 4) {
                row.classList.add("choice-item-ok");
            }

            const dot = document.createElement("span");
            dot.className = "choice-dot";
            dot.textContent = item.level !== null ? (levelDots[item.level] || "\u26AA") : "\u26AA";
            row.appendChild(dot);

            const info = document.createElement("span");
            info.className = "choice-info";
            const label = cat + ": " + item.org;
            if (item.country !== "-") {
                info.textContent = label + " (" + item.country + ")";
            } else {
                info.textContent = label;
            }
            row.appendChild(info);

            if (item.level !== null) {
                const lvlSpan = document.createElement("span");
                lvlSpan.className = "choice-level badge badge-level-" + item.level;
                lvlSpan.textContent = "niveau " + item.level;
                row.appendChild(lvlSpan);
            }

            if (item.thirdParty) {
                const tag = document.createElement("span");
                tag.className = "choice-changeable";
                tag.textContent = "be\u00EFnvloedbaar";
                row.appendChild(tag);
            }

            catDiv.appendChild(row);
        }

        container.appendChild(catDiv);
    }

    // Tip section
    if (improvableCount > 0 && improvedAvg > currentAvg) {
        const tip = document.createElement("div");
        tip.className = "choice-tip";

        const tipIcon = document.createElement("span");
        tipIcon.className = "choice-tip-icon";
        // Lightbulb SVG icon (Material Design)
        tipIcon.textContent = "\uD83D\uDCA1";
        tip.appendChild(tipIcon);

        const tipText = document.createElement("span");
        tipText.textContent = "Tip: Door be\u00EFnvloedbare diensten te vervangen door EU-alternatieven stijgt uw gemiddelde niveau van "
            + currentAvg.toFixed(1) + " naar " + improvedAvg.toFixed(1) + ".";
        tip.appendChild(tipText);

        container.appendChild(tip);
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
