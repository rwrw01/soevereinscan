var BASE = document.documentElement.dataset.base || "";

document.addEventListener("DOMContentLoaded", function () {
    var form = document.getElementById("scan-form");
    if (form) {
        form.addEventListener("submit", function (e) {
            e.preventDefault();
            var url = document.getElementById("scan-url").value;
            var statusDiv = document.getElementById("scan-status");
            var statusText = document.getElementById("status-text");
            var btn = document.getElementById("scan-btn");

            btn.disabled = true;
            statusDiv.classList.remove("hidden");
            statusText.textContent = "Scan wordt gestart...";

            fetch(BASE + "/api/scan", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ url: url }),
            })
                .then(function (res) {
                    return res.json().then(function (data) {
                        if (res.ok) {
                            window.location.href = BASE + "/results/" + data.id;
                        } else {
                            statusText.textContent = "Fout: " + (data.detail || "Onbekende fout");
                            btn.disabled = false;
                        }
                    });
                })
                .catch(function () {
                    statusText.textContent = "Verbindingsfout. Probeer het opnieuw.";
                    btn.disabled = false;
                });
        });
    }
});

function loadResults(scanId) {
    var loading = document.getElementById("loading");
    var results = document.getElementById("results");
    var statusMsg = loading.querySelector("p");
    var pollCount = 0;

    var statusLabels = {
        pending: "Scan wordt voorbereid...",
        scanning: "Website wordt geladen in de browser... Dit kan 30-60 seconden duren.",
        analyzing: "IP-adressen worden geanalyseerd op soevereiniteit...",
    };

    function poll() {
        pollCount++;
        fetch(BASE + "/api/scan/" + scanId)
            .then(function (res) { return res.json(); })
            .then(function (data) {
                if (data.status === "done") {
                    loading.classList.add("hidden");
                    results.classList.remove("hidden");
                    renderResults(data);
                } else if (data.status === "error") {
                    statusMsg.textContent = "Scan is mislukt. Probeer het opnieuw.";
                    loading.querySelector(".spinner").style.display = "none";
                } else {
                    var msg = statusLabels[data.status] || "Bezig...";
                    var elapsed = pollCount * 3;
                    statusMsg.textContent = msg + " (" + elapsed + "s)";
                    setTimeout(poll, 3000);
                }
            });
    }
    poll();
}

/* --- Helper functions --- */

function getSovereigntyLevel(ip) {
    return typeof ip.sovereignty_level === "number" ? ip.sovereignty_level : 0;
}

function sovereigntyLabel(level) {
    var labels = {
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
    return "badge-level-" + level;
}

function levelRowClass(level) {
    if (level >= 4) return "row-level-high";
    if (level >= 2) return "row-level-mid";
    return "row-level-low";
}

function countryName(code) {
    var names = {
        "NL": "Nederland", "DE": "Duitsland", "US": "Verenigde Staten",
        "IE": "Ierland", "FR": "Frankrijk", "GB": "Verenigd Koninkrijk",
        "BE": "Belgie", "SE": "Zweden", "FI": "Finland", "CH": "Zwitserland",
        "AT": "Oostenrijk", "ES": "Spanje", "IT": "Italie", "NO": "Noorwegen",
        "DK": "Denemarken", "PL": "Polen", "CZ": "Tsjechie", "JP": "Japan",
        "SG": "Singapore", "AU": "Australie", "CA": "Canada", "BR": "Brazilie",
    };
    return names[code] || code;
}

function groupByOrganisation(ipList) {
    var orgMap = {};
    for (var i = 0; i < ipList.length; i++) {
        var ip = ipList[i];
        var orgKey = (ip.parent_company || ip.asn_org || ip.ip_address).toLowerCase();
        if (!orgMap[orgKey]) {
            orgMap[orgKey] = {
                name: ip.parent_company || ip.asn_org || ip.ip_address,
                country: ip.country_code,
                level: ip.sovereignty_level,
                label: ip.sovereignty_label,
                ips: [],
                hostnames: [],
            };
        }
        orgMap[orgKey].ips.push(ip.ip_address);
        if (ip.sovereignty_level < orgMap[orgKey].level) {
            orgMap[orgKey].level = ip.sovereignty_level;
            orgMap[orgKey].label = ip.sovereignty_label;
        }
    }
    return orgMap;
}

function generateRecommendations(orgMap) {
    var tips = {
        "google": "Overweeg Google-diensten te vervangen door EU-alternatieven (Matomo voor analytics, zelf-gehoste fonts).",
        "facebook": "Verwijder de Facebook/Meta tracking pixel als deze niet noodzakelijk is voor een overheidswebsite.",
        "meta": "Verwijder de Meta/Facebook tracking pixel als deze niet noodzakelijk is voor een overheidswebsite.",
        "pinterest": "Verwijder de Pinterest tracking pixel -- niet relevant voor gemeentelijke dienstverlening.",
        "doubleclick": "Blokkeer DoubleClick (Google advertenties) -- tracking zonder meerwaarde voor een overheidswebsite.",
        "cloudflare": "Overweeg Cloudflare te vervangen door een Europese CDN-aanbieder.",
        "akamai": "Akamai is een Amerikaans bedrijf. Overweeg een Europees CDN-alternatief.",
        "fastly": "Fastly is een Amerikaans bedrijf. Overweeg een Europees alternatief.",
        "adobe": "Adobe/Typekit lettertypen worden extern geladen. Overweeg zelf-gehoste lettertypen.",
        "amazon": "Amazon Web Services (AWS) is Amerikaans. Overweeg Europese hosting-alternatieven.",
        "microsoft": "Microsoft-diensten vallen onder Amerikaanse jurisdictie, ook bij EU-datacenters.",
    };
    var recs = [];
    var seen = {};
    var keys = Object.keys(orgMap);
    for (var i = 0; i < keys.length; i++) {
        var orgKey = keys[i];
        var org = orgMap[orgKey];
        if (org.level >= 4) continue;
        var tipKeys = Object.keys(tips);
        for (var j = 0; j < tipKeys.length; j++) {
            var keyword = tipKeys[j];
            if (orgKey.indexOf(keyword) !== -1 && !seen[tips[keyword]]) {
                recs.push(tips[keyword]);
                seen[tips[keyword]] = true;
                break;
            }
        }
    }
    return recs;
}

function extractDomain(url) {
    try {
        return new URL(url).hostname;
    } catch (_) {
        return url;
    }
}

function isThirdParty(domain, scanUrl) {
    var scanDomain = extractDomain(scanUrl);
    var scanParts = scanDomain.split(".");
    var domParts = domain.split(".");
    var scanBase = scanParts.slice(-2).join(".");
    var domBase = domParts.slice(-2).join(".");
    return domBase !== scanBase;
}

function categorizeDomain(domain) {
    var d = domain.toLowerCase();
    if (/analytics|gtag|ga\.|google-analytics|googletagmanager/.test(d)) return "Analytics";
    if (/fonts\.|typekit/.test(d)) return "Lettertypen";
    if (/pixel|track|pinterest|facebook|doubleclick|fb\.com/.test(d)) return "Tracking";
    if (/cdn\.|cloudfront|akamai|fastly|cloudflare/.test(d)) return "CDN";
    return "Overig";
}

function collectTreeDomains(node, list) {
    if (!node) return list;
    list.push(node);
    if (node.children) {
        for (var i = 0; i < node.children.length; i++) {
            collectTreeDomains(node.children[i], list);
        }
    }
    return list;
}

/* Match hostname to IP analysis using hostname_ips mapping */
function findIpForHostname(hostname, ipAnalyses, hostnameIps) {
    if (hostnameIps && hostnameIps[hostname]) {
        var mappedIps = hostnameIps[hostname];
        for (var i = 0; i < ipAnalyses.length; i++) {
            if (mappedIps.indexOf(ipAnalyses[i].ip_address) !== -1) {
                return ipAnalyses[i];
            }
        }
    }
    // Fallback: try hostname match on ip fields
    for (var j = 0; j < ipAnalyses.length; j++) {
        if (ipAnalyses[j].hostname === hostname) return ipAnalyses[j];
    }
    return null;
}

/* --- Main render --- */

function renderResults(data) {
    document.getElementById("scan-url").textContent = data.url;

    var summary = data.summary || {};
    var ipList = data.ip_analyses || [];
    var hostnameIps = summary.hostname_ips || {};

    // Group by organisation
    var orgMap = groupByOrganisation(ipList);
    var orgKeys = Object.keys(orgMap);
    var totalOrgs = orgKeys.length;

    // Count levels per IP for distribution
    var distribution = { 0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0 };
    var levelSum = 0;
    for (var i = 0; i < ipList.length; i++) {
        var level = getSovereigntyLevel(ipList[i]);
        distribution[level] = (distribution[level] || 0) + 1;
        levelSum += level;
    }
    var total = ipList.length || 1;
    var averageLevel = (levelSum / total).toFixed(1);

    // Count sovereign vs non-sovereign ORGANISATIONS
    var sovOrgCount = 0;
    var nonSovOrgCount = 0;
    for (var k = 0; k < orgKeys.length; k++) {
        if (orgMap[orgKeys[k]].level >= 4) {
            sovOrgCount++;
        } else if (orgMap[orgKeys[k]].level <= 2) {
            nonSovOrgCount++;
        }
    }

    // --- Layer 1: Executive Summary ---
    renderExecutiveSummary(averageLevel, totalOrgs, sovOrgCount, nonSovOrgCount, orgMap);

    // --- Layer 2: Uw keuzes ---
    renderChoices(summary.resource_tree, ipList, data.url, hostnameIps, orgMap);

    // --- Layer 3: Visual ---
    renderDistribution(distribution, total);
    if (summary.resource_tree) {
        renderTree(summary.resource_tree, data.url, ipList, hostnameIps);
    }
    renderCountryBars(ipList);
    renderMap(ipList);

    // --- Layer 4: Technical ---
    renderServiceTable(orgMap, hostnameIps);
    renderIpTable(ipList);
}

/* --- Layer 1: Executive Summary --- */

function renderExecutiveSummary(averageLevel, totalOrgs, sovCount, nonSovCount, orgMap) {
    var circle = document.getElementById("score-circle");
    var scoreValue = document.getElementById("score-value");
    scoreValue.textContent = averageLevel;

    var avg = parseFloat(averageLevel);
    if (avg >= 4) {
        circle.className = "score-circle score-green";
    } else if (avg >= 2.5) {
        circle.className = "score-circle score-amber";
    } else {
        circle.className = "score-circle score-red";
    }

    var summaryText = document.getElementById("exec-summary-text");
    summaryText.textContent = "Van de " + totalOrgs + " diensten die uw website gebruikt, scoren " +
        sovCount + " soeverein (niveau 4-5) en " + nonSovCount + " niet-soeverein (niveau 0-2).";

    // Recommendations
    var recs = generateRecommendations(orgMap);
    var recsContainer = document.getElementById("exec-recommendations");
    recsContainer.textContent = "";

    if (recs.length > 0) {
        var recsTitle = document.createElement("h4");
        recsTitle.textContent = "Aanbevelingen";
        recsContainer.appendChild(recsTitle);

        var maxRecs = Math.min(recs.length, 3);
        for (var i = 0; i < maxRecs; i++) {
            var recDiv = document.createElement("div");
            recDiv.className = "recommendation";

            var recIcon = document.createElement("span");
            recIcon.className = "rec-icon";
            recIcon.textContent = "[tip]";
            recDiv.appendChild(recIcon);

            var recText = document.createElement("span");
            recText.textContent = recs[i];
            recDiv.appendChild(recText);

            recsContainer.appendChild(recDiv);
        }
    }
}

/* --- Layer 2: Uw keuzes --- */

function renderChoices(treeData, ipAnalyses, scanUrl, hostnameIps, orgMap) {
    var container = document.getElementById("choices-container");
    if (!container) return;
    container.textContent = "";

    // Build categories from hostname_ips mapping
    var categories = {};
    var hostKeys = Object.keys(hostnameIps);

    if (hostKeys.length === 0 && treeData) {
        // Fallback: use tree domains
        var allNodes = [];
        collectTreeDomains(treeData, allNodes);
        for (var n = 0; n < allNodes.length; n++) {
            hostKeys.push(allNodes[n].domain || "");
        }
    }

    for (var i = 0; i < hostKeys.length; i++) {
        var hostname = hostKeys[i];
        if (!hostname) continue;
        var ipInfo = findIpForHostname(hostname, ipAnalyses, hostnameIps);
        var lvl = ipInfo ? getSovereigntyLevel(ipInfo) : null;
        var thirdParty = isThirdParty(hostname, scanUrl);

        var cat;
        if (!thirdParty) {
            cat = "Hosting";
        } else {
            cat = categorizeDomain(hostname);
        }

        if (!categories[cat]) categories[cat] = [];
        categories[cat].push({
            domain: hostname,
            level: lvl,
            org: ipInfo ? (ipInfo.parent_company || ipInfo.asn_org || "-") : "-",
            country: ipInfo ? (ipInfo.country_code || "-") : "-",
            thirdParty: thirdParty,
        });
    }

    // Category display order and Dutch labels
    var catOrder = ["Hosting", "Analytics", "Lettertypen", "Tracking", "CDN", "Overig"];
    var catDescriptions = {
        "Hosting": "Uw website draait bij",
        "Analytics": "U gebruikt",
        "Lettertypen": "Lettertypen worden geladen van",
        "Tracking": "Tracking actief van",
        "CDN": "Content wordt geleverd door",
        "Overig": "Overige diensten van",
    };

    for (var c = 0; c < catOrder.length; c++) {
        var catName = catOrder[c];
        if (!categories[catName] || categories[catName].length === 0) continue;

        var catDiv = document.createElement("div");
        catDiv.className = "choice-category";

        var catHeader = document.createElement("h5");
        catHeader.className = "choice-cat-header";
        catHeader.textContent = catName;
        catDiv.appendChild(catHeader);

        // Deduplicate by org within category
        var seen = {};
        var items = [];
        for (var d = 0; d < categories[catName].length; d++) {
            var item = categories[catName][d];
            var key = item.org + "|" + item.domain;
            if (!seen[key]) {
                seen[key] = true;
                items.push(item);
            }
        }

        for (var e = 0; e < items.length; e++) {
            var it = items[e];
            var row = document.createElement("div");
            row.className = "choice-item";
            if (it.level !== null && it.level <= 2) {
                row.classList.add("choice-item-warn");
            } else if (it.level !== null && it.level >= 4) {
                row.classList.add("choice-item-ok");
            }

            // Description text
            var info = document.createElement("span");
            info.className = "choice-info";
            var desc = catDescriptions[catName] || "";
            var orgLabel = it.org !== "-" ? it.org : it.domain;
            var countryLabel = it.country !== "-" ? countryName(it.country) : "";
            if (countryLabel) {
                info.textContent = desc + " " + orgLabel + " in " + countryLabel;
            } else {
                info.textContent = desc + " " + orgLabel;
            }
            row.appendChild(info);

            // Level badge
            if (it.level !== null) {
                var lvlSpan = document.createElement("span");
                lvlSpan.className = "badge badge-level-" + it.level;
                lvlSpan.textContent = "Niveau " + it.level;
                row.appendChild(lvlSpan);
            }

            // Beinvloedbaar tag
            if (it.thirdParty) {
                var tag = document.createElement("span");
                tag.className = "choice-changeable";
                tag.textContent = "beinvloedbaar";
                row.appendChild(tag);
            }

            catDiv.appendChild(row);
        }

        container.appendChild(catDiv);
    }
}

/* --- Layer 3: Distribution bars --- */

function renderDistribution(distribution, total) {
    var distContainer = document.getElementById("level-distribution");
    distContainer.textContent = "";

    for (var lvl = 5; lvl >= 0; lvl--) {
        var count = distribution[lvl] || 0;
        var pct = Math.round((count / total) * 100);

        var row = document.createElement("div");
        row.className = "dist-row";

        var label = document.createElement("span");
        label.className = "dist-label";
        label.textContent = lvl + " -- " + sovereigntyLabel(lvl);

        var barOuter = document.createElement("div");
        barOuter.className = "dist-bar-outer";

        var barInner = document.createElement("div");
        barInner.className = "dist-bar-inner dist-bar-level-" + lvl;
        barInner.style.width = pct + "%";

        var countSpan = document.createElement("span");
        countSpan.className = "dist-count";
        countSpan.textContent = count + " (" + pct + "%)";

        barOuter.appendChild(barInner);
        row.appendChild(label);
        row.appendChild(barOuter);
        row.appendChild(countSpan);
        distContainer.appendChild(row);
    }
}

/* --- Layer 3: Resource Tree --- */

function renderTree(treeData, scanUrl, ipAnalyses, hostnameIps) {
    var container = document.getElementById("resource-tree");
    if (!container || !treeData) return;
    container.textContent = "";

    function buildNode(node, depth) {
        var li = document.createElement("li");
        var nodeDiv = document.createElement("div");
        nodeDiv.className = "tree-node";

        var thirdParty = isThirdParty(node.domain || "", scanUrl);
        if (thirdParty) nodeDiv.classList.add("tree-third-party");

        var hasChildren = node.children && node.children.length > 0;
        var startCollapsed = depth > 0;

        var toggle = document.createElement("span");
        toggle.className = "tree-toggle";
        toggle.textContent = hasChildren ? (startCollapsed ? ">" : "v") : " ";
        nodeDiv.appendChild(toggle);

        var domainSpan = document.createElement("span");
        domainSpan.textContent = node.domain || "onbekend";
        domainSpan.className = "tree-domain";
        nodeDiv.appendChild(domainSpan);

        if (node.count) {
            var countSpan = document.createElement("span");
            countSpan.className = "tree-count";
            countSpan.textContent = " (" + node.count + " verzoeken)";
            nodeDiv.appendChild(countSpan);
        }

        var ipInfo = findIpForHostname(node.domain || "", ipAnalyses, hostnameIps);
        if (ipInfo && ipInfo.asn_org) {
            var hostSpan = document.createElement("span");
            hostSpan.className = "tree-host";
            var country = ipInfo.country_code || "?";
            hostSpan.textContent = " -- " + ipInfo.asn_org + " (" + country + ")";
            nodeDiv.appendChild(hostSpan);
        }

        if (thirdParty) {
            var warn = document.createElement("span");
            warn.className = "tree-tp-label";
            warn.textContent = " [extern]";
            nodeDiv.appendChild(warn);
        }

        li.appendChild(nodeDiv);

        if (hasChildren) {
            var childUl = document.createElement("ul");
            if (startCollapsed) childUl.classList.add("tree-children-hidden");
            for (var ci = 0; ci < node.children.length; ci++) {
                childUl.appendChild(buildNode(node.children[ci], depth + 1));
            }
            li.appendChild(childUl);

            nodeDiv.addEventListener("click", (function (ul, tog) {
                return function () {
                    var hidden = ul.classList.toggle("tree-children-hidden");
                    tog.textContent = hidden ? ">" : "v";
                };
            })(childUl, toggle));
        }

        return li;
    }

    var rootUl = document.createElement("ul");
    rootUl.appendChild(buildNode(treeData, 0));
    container.appendChild(rootUl);
}

/* --- Layer 3: Country bars chart --- */

function renderCountryBars(ipAnalyses) {
    var container = document.getElementById("country-bars");
    if (!container) return;
    container.textContent = "";

    // Group by country
    var countryCounts = {};
    var countryLevels = {};
    for (var i = 0; i < ipAnalyses.length; i++) {
        var ip = ipAnalyses[i];
        var cc = ip.country_code || "??";
        if (!countryCounts[cc]) {
            countryCounts[cc] = 0;
            countryLevels[cc] = 5;
        }
        countryCounts[cc]++;
        var lvl = getSovereigntyLevel(ip);
        if (lvl < countryLevels[cc]) countryLevels[cc] = lvl;
    }

    // Sort by count descending
    var countries = Object.keys(countryCounts);
    countries.sort(function (a, b) { return countryCounts[b] - countryCounts[a]; });

    var maxCount = 0;
    for (var j = 0; j < countries.length; j++) {
        if (countryCounts[countries[j]] > maxCount) maxCount = countryCounts[countries[j]];
    }

    var heading = document.createElement("h5");
    heading.textContent = "Servers per land";
    heading.className = "country-bars-heading";
    container.appendChild(heading);

    for (var k = 0; k < countries.length; k++) {
        var code = countries[k];
        var count = countryCounts[code];
        var worstLevel = countryLevels[code];
        var pct = maxCount > 0 ? Math.round((count / maxCount) * 100) : 0;

        var row = document.createElement("div");
        row.className = "country-bar-row";

        var nameSpan = document.createElement("span");
        nameSpan.className = "country-bar-name";
        nameSpan.textContent = countryName(code);
        row.appendChild(nameSpan);

        var barOuter = document.createElement("div");
        barOuter.className = "country-bar-outer";

        var barInner = document.createElement("div");
        barInner.className = "country-bar-inner dist-bar-level-" + worstLevel;
        barInner.style.width = pct + "%";
        barOuter.appendChild(barInner);
        row.appendChild(barOuter);

        var countSpan = document.createElement("span");
        countSpan.className = "country-bar-count";
        countSpan.textContent = count + " server" + (count !== 1 ? "s" : "");
        row.appendChild(countSpan);

        container.appendChild(row);
    }
}

/* --- Layer 3: World Map with continent outlines --- */

function renderMap(ipAnalyses) {
    var container = document.getElementById("world-map");
    if (!container) return;
    container.textContent = "";

    var mapDiv = document.createElement("div");
    mapDiv.className = "world-map-inner";

    var width = 800;
    var height = 400;
    var ns = "http://www.w3.org/2000/svg";

    var svg = document.createElementNS(ns, "svg");
    svg.setAttribute("viewBox", "0 0 " + width + " " + height);
    svg.setAttribute("role", "img");

    var titleEl = document.createElementNS(ns, "title");
    titleEl.textContent = "Wereldkaart met serverlocaties";
    svg.appendChild(titleEl);

    // Background
    var bg = document.createElementNS(ns, "rect");
    bg.setAttribute("width", String(width));
    bg.setAttribute("height", String(height));
    bg.setAttribute("fill", "#1a2332");
    svg.appendChild(bg);

    // Simplified continent outlines (equirectangular projection)
    var continentPaths = [
        // Europe
        "M390,80 L395,75 410,72 420,68 435,70 440,75 445,80 450,88 445,95 440,100 430,105 420,108 410,110 400,108 392,102 388,95 Z",
        // Africa
        "M395,115 L410,112 425,115 435,120 440,135 438,155 432,175 425,190 418,200 410,205 400,200 392,190 388,175 385,155 388,135 Z",
        // Asia
        "M450,60 L470,55 490,52 510,55 530,58 550,55 570,60 585,65 595,72 600,82 605,95 600,105 590,110 575,115 560,118 545,120 530,118 515,112 500,108 490,100 480,95 470,88 460,82 455,75 Z",
        // North America
        "M120,65 L140,58 160,55 180,58 200,62 220,68 240,75 255,82 260,92 258,105 250,118 238,130 225,140 210,148 195,152 180,148 168,140 155,130 142,118 135,105 128,92 122,80 Z",
        // South America
        "M210,160 L225,155 238,158 248,168 252,180 250,195 245,210 238,225 228,238 218,248 208,252 198,248 190,238 185,225 182,210 185,195 190,180 198,168 Z",
        // Australia
        "M560,195 L575,188 590,190 602,195 608,205 605,215 598,222 585,225 572,222 565,215 562,205 Z",
    ];

    for (var p = 0; p < continentPaths.length; p++) {
        var path = document.createElementNS(ns, "path");
        path.setAttribute("d", continentPaths[p]);
        path.setAttribute("fill", "rgba(255,255,255,0.08)");
        path.setAttribute("stroke", "rgba(255,255,255,0.15)");
        path.setAttribute("stroke-width", "0.5");
        svg.appendChild(path);
    }

    // Grid lines
    var lon, lat, x, y, line;
    for (lon = -180; lon <= 180; lon += 60) {
        x = ((lon + 180) / 360) * width;
        line = document.createElementNS(ns, "line");
        line.setAttribute("x1", String(x));
        line.setAttribute("y1", "0");
        line.setAttribute("x2", String(x));
        line.setAttribute("y2", String(height));
        line.setAttribute("stroke", "rgba(255,255,255,0.06)");
        line.setAttribute("stroke-width", "0.5");
        svg.appendChild(line);
    }
    for (lat = -60; lat <= 60; lat += 30) {
        y = ((90 - lat) / 180) * height;
        line = document.createElementNS(ns, "line");
        line.setAttribute("x1", "0");
        line.setAttribute("y1", String(y));
        line.setAttribute("x2", String(width));
        line.setAttribute("y2", String(y));
        line.setAttribute("stroke", "rgba(255,255,255,0.06)");
        line.setAttribute("stroke-width", "0.5");
        svg.appendChild(line);
    }

    // Sovereignty level colors
    var levelColors = {
        5: "#15803d", 4: "#22c55e", 3: "#eab308",
        2: "#f97316", 1: "#fb923c", 0: "#9ca3af",
    };

    // Cluster IPs by rounded lat/lng
    var clusters = {};
    for (var ci = 0; ci < ipAnalyses.length; ci++) {
        var ip = ipAnalyses[ci];
        if (ip.latitude == null || ip.longitude == null) continue;
        var clat = Math.round(ip.latitude * 10) / 10;
        var clng = Math.round(ip.longitude * 10) / 10;
        var key = clat + "," + clng;
        if (!clusters[key]) {
            clusters[key] = { lat: clat, lng: clng, count: 0, level: 5, ips: [] };
        }
        clusters[key].count++;
        var clvl = getSovereigntyLevel(ip);
        if (clvl < clusters[key].level) clusters[key].level = clvl;
        clusters[key].ips.push(ip);
    }

    // Draw dots
    var clusterKeys = Object.keys(clusters);
    for (var di = 0; di < clusterKeys.length; di++) {
        var c = clusters[clusterKeys[di]];
        var cx = ((c.lng + 180) / 360) * width;
        var cy = ((90 - c.lat) / 180) * height;
        var r = Math.max(5, Math.min(14, 4 + c.count * 2));

        var circle = document.createElementNS(ns, "circle");
        circle.setAttribute("cx", String(cx));
        circle.setAttribute("cy", String(cy));
        circle.setAttribute("r", String(r));
        circle.setAttribute("fill", levelColors[c.level] || "#9ca3af");
        circle.setAttribute("opacity", "0.9");
        circle.setAttribute("stroke", "rgba(255,255,255,0.3)");
        circle.setAttribute("stroke-width", "1");
        circle.setAttribute("class", "map-dot");

        var ipNames = [];
        for (var ni = 0; ni < c.ips.length; ni++) {
            var name = (c.ips[ni].asn_org || c.ips[ni].ip_address) + " (" + (c.ips[ni].country_code || "?") + ")";
            if (ipNames.indexOf(name) === -1) ipNames.push(name);
        }
        var tipEl = document.createElementNS(ns, "title");
        tipEl.textContent = ipNames.join(", ") + " -- niveau " + c.level;
        circle.appendChild(tipEl);

        svg.appendChild(circle);

        // Add country label next to large clusters
        if (c.count >= 2) {
            var labelEl = document.createElementNS(ns, "text");
            labelEl.setAttribute("x", String(cx + r + 3));
            labelEl.setAttribute("y", String(cy + 4));
            labelEl.setAttribute("fill", "rgba(255,255,255,0.7)");
            labelEl.setAttribute("font-size", "10");
            labelEl.setAttribute("font-family", "sans-serif");
            var labelCountry = c.ips[0].country_code || "?";
            labelEl.textContent = countryName(labelCountry) + " (" + c.count + ")";
            svg.appendChild(labelEl);
        }
    }

    if (clusterKeys.length === 0) {
        var txt = document.createElementNS(ns, "text");
        txt.setAttribute("x", String(width / 2));
        txt.setAttribute("y", String(height / 2));
        txt.setAttribute("text-anchor", "middle");
        txt.setAttribute("fill", "rgba(255,255,255,0.5)");
        txt.setAttribute("font-size", "14");
        txt.textContent = "Geen locatiegegevens beschikbaar";
        svg.appendChild(txt);
    }

    mapDiv.appendChild(svg);
    container.appendChild(mapDiv);
}

/* --- Layer 4: Service table grouped by organisation --- */

function renderServiceTable(orgMap, hostnameIps) {
    var container = document.getElementById("service-table-container");
    if (!container) return;
    container.textContent = "";

    var table = document.createElement("table");
    table.className = "service-table";

    var thead = document.createElement("thead");
    var headerRow = document.createElement("tr");
    var headers = ["Dienst", "Aanbieder", "Land", "Niveau"];
    for (var h = 0; h < headers.length; h++) {
        var th = document.createElement("th");
        th.textContent = headers[h];
        headerRow.appendChild(th);
    }
    thead.appendChild(headerRow);
    table.appendChild(thead);

    var tbody = document.createElement("tbody");

    // Reverse-map: find hostnames for each org
    var orgHostnames = {};
    var hostKeys = Object.keys(hostnameIps);
    var orgKeys = Object.keys(orgMap);

    for (var oi = 0; oi < orgKeys.length; oi++) {
        var orgKey = orgKeys[oi];
        var org = orgMap[orgKey];
        var matchedHostnames = [];

        for (var hi = 0; hi < hostKeys.length; hi++) {
            var hostname = hostKeys[hi];
            var ips = hostnameIps[hostname];
            for (var ii = 0; ii < ips.length; ii++) {
                if (org.ips.indexOf(ips[ii]) !== -1 && matchedHostnames.indexOf(hostname) === -1) {
                    matchedHostnames.push(hostname);
                }
            }
        }
        orgHostnames[orgKey] = matchedHostnames;
    }

    // Sort orgs by level ascending (worst first)
    orgKeys.sort(function (a, b) { return orgMap[a].level - orgMap[b].level; });

    for (var si = 0; si < orgKeys.length; si++) {
        var sOrgKey = orgKeys[si];
        var sOrg = orgMap[sOrgKey];

        var row = document.createElement("tr");
        row.className = levelRowClass(sOrg.level);

        // Dienst (hostnames)
        var tdService = document.createElement("td");
        var hostnames = orgHostnames[sOrgKey] || [];
        if (hostnames.length > 0) {
            tdService.textContent = hostnames.join(", ");
        } else {
            tdService.textContent = sOrg.ips.join(", ");
        }
        row.appendChild(tdService);

        // Aanbieder
        var tdOrg = document.createElement("td");
        tdOrg.textContent = sOrg.name;
        row.appendChild(tdOrg);

        // Land
        var tdCountry = document.createElement("td");
        tdCountry.textContent = sOrg.country ? countryName(sOrg.country) : "-";
        row.appendChild(tdCountry);

        // Niveau badge
        var tdLevel = document.createElement("td");
        var badge = document.createElement("span");
        badge.className = "badge badge-level-" + sOrg.level;
        badge.textContent = sOrg.level + " -- " + (sOrg.label || sovereigntyLabel(sOrg.level));
        tdLevel.appendChild(badge);
        row.appendChild(tdLevel);

        tbody.appendChild(row);
    }

    table.appendChild(tbody);
    container.appendChild(table);
}

/* --- Layer 4: IP table --- */

function renderIpTable(ipList) {
    var tbody = document.getElementById("ip-tbody");
    tbody.textContent = "";

    for (var i = 0; i < ipList.length; i++) {
        var ip = ipList[i];
        var level = getSovereigntyLevel(ip);
        var row = document.createElement("tr");
        row.className = levelRowClass(level);

        var cells = [
            ip.ip_address,
            ip.asn || "-",
            ip.asn_org || "-",
            ip.country_code || "-",
            ip.parent_company || "-",
        ];
        for (var ci = 0; ci < cells.length; ci++) {
            var td = document.createElement("td");
            td.textContent = String(cells[ci]);
            row.appendChild(td);
        }

        var levelTd = document.createElement("td");
        var badge = document.createElement("span");
        badge.className = "badge " + levelBadgeClass(level);
        badge.textContent = level + " -- " + (ip.sovereignty_label || sovereigntyLabel(level));
        levelTd.appendChild(badge);
        row.appendChild(levelTd);

        tbody.appendChild(row);
    }
}

// Auto-load results if scan-id is present on the script tag
(function () {
    var script = document.querySelector("script[data-scan-id]");
    if (script) {
        var scanId = script.dataset.scanId;
        if (scanId) {
            document.addEventListener("DOMContentLoaded", function () { loadResults(scanId); });
        }
    }
})();
