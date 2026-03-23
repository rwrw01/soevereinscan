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
        "LU": "Luxemburg",
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
    for (var j = 0; j < ipAnalyses.length; j++) {
        if (ipAnalyses[j].hostname === hostname) return ipAnalyses[j];
    }
    return null;
}

/* --- Energy label scoring --- */

function scoreToLabel(avg) {
    if (avg >= 4.5) return "A";
    if (avg >= 4.0) return "B";
    if (avg >= 3.0) return "C";
    if (avg >= 2.0) return "D";
    if (avg >= 1.0) return "E";
    return "F";
}

function getTopActions(orgMap) {
    var actions = [];
    var orgKeys = Object.keys(orgMap);
    var hasTracking = false;
    var hasNonEuAnalytics = false;
    var hasNonEuCdn = false;
    var hasNonEuHosting = false;
    var hasNonEuFonts = false;

    for (var i = 0; i < orgKeys.length; i++) {
        var key = orgKeys[i];
        var org = orgMap[key];
        if (org.level >= 4) continue;

        if (/pixel|track|pinterest|facebook|doubleclick|fb\.com|hotjar/.test(key)) {
            hasTracking = true;
        }
        if (/analytics|gtag|google-analytics|googletagmanager/.test(key) || (key.indexOf("google") !== -1 && !hasTracking)) {
            hasNonEuAnalytics = true;
        }
        if (/cloudflare|akamai|fastly|cloudfront|bunny|cdn/.test(key)) {
            hasNonEuCdn = true;
        }
        if (/amazon|aws|microsoft|azure/.test(key)) {
            hasNonEuHosting = true;
        }
        if (/adobe|typekit|fonts\.googleapis/.test(key)) {
            hasNonEuFonts = true;
        }
    }

    if (hasTracking) {
        actions.push("onnodige tracking te verwijderen");
    }
    if (hasNonEuAnalytics && actions.length < 2) {
        actions.push("over te stappen op Europese bezoekersstatistieken");
    }
    if (hasNonEuFonts && actions.length < 2) {
        actions.push("lettertypen zelf te hosten");
    }
    if (hasNonEuCdn && actions.length < 2) {
        actions.push("een Europees CDN-alternatief te overwegen");
    }
    if (hasNonEuHosting && actions.length < 2) {
        actions.push("Europese hosting te bespreken met uw leverancier");
    }
    return actions;
}

function getAlternative(orgKey) {
    var alts = {
        "cloudflare": "Europese alternatieven: Gcore (Luxemburg) en OVHcloud (Frankrijk)",
        "google": "Europees alternatief: Matomo of Fathom",
        "akamai": "Europese alternatieven: Gcore (Luxemburg) en OVHcloud (Frankrijk)",
        "fastly": "Europese alternatieven: Gcore (Luxemburg) en OVHcloud (Frankrijk)",
        "amazon": "Europese alternatieven: Hetzner (Duitsland), Scaleway (Frankrijk)",
        "microsoft": "Europese alternatieven: Nextcloud, Collabora",
        "adobe": "Tip: lettertypen zelf hosten op uw eigen server",
        "facebook": "Tip: tracking verwijderen, niet relevant voor overheidsdienstverlening",
        "pinterest": "Tip: tracking verwijderen, niet relevant voor overheidsdienstverlening",
        "doubleclick": "Tip: advertentietracking verwijderen",
        "hotjar": "Europees alternatief: Open Web Analytics",
    };
    var altKeys = Object.keys(alts);
    for (var i = 0; i < altKeys.length; i++) {
        if (orgKey.indexOf(altKeys[i]) !== -1) {
            return alts[altKeys[i]];
        }
    }
    return null;
}

/* Build reverse map: org -> hostnames */
function buildOrgHostnames(orgMap, hostnameIps) {
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
    return orgHostnames;
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
    var euOrgCount = 0;
    var nonEuOrgCount = 0;
    for (var k = 0; k < orgKeys.length; k++) {
        if (orgMap[orgKeys[k]].level >= 4) {
            euOrgCount++;
        } else {
            nonEuOrgCount++;
        }
    }

    // Build org->hostnames map
    var orgHostnames = buildOrgHostnames(orgMap, hostnameIps);

    // Redirect notice
    renderRedirectNotice(summary);

    // 1. Score Summary
    renderScoreSummary(averageLevel, totalOrgs, euOrgCount, nonEuOrgCount, orgMap);

    // 2. Services (grouped by provider)
    renderServices(orgMap, orgHostnames, data.url);

    // 3. Improvement path
    renderImprovementPath(orgMap, averageLevel, ipList);

    // 4. More info (section 4)
    renderQuestions(orgMap, hostnameIps, ipList, data.url);
    renderDistribution(distribution, total);
    if (summary.resource_tree) {
        renderTree(summary.resource_tree, data.url, ipList, hostnameIps);
    }
    renderCountryBars(ipList);
    renderMap(ipList);
    renderServiceTable(orgMap, hostnameIps);
    renderIpTable(ipList);
    renderLegalBackground();
}

/* --- Redirect notice --- */

function renderRedirectNotice(summary) {
    var container = document.getElementById("redirect-notice");
    if (!container) return;
    container.textContent = "";

    if (!summary.has_redirect) {
        container.classList.add("hidden");
        return;
    }

    container.classList.remove("hidden");

    var title = document.createElement("strong");
    title.textContent = "Let op: doorverwijzing gedetecteerd";
    container.appendChild(title);

    var p1 = document.createElement("p");
    p1.textContent = "U heeft " + (summary.original_url || "") + " gescand. Deze website verwijst automatisch door naar " + (summary.final_url || "") + ". De onderstaande resultaten gelden voor de website waar u uiteindelijk terechtkomt.";
    container.appendChild(p1);

    var p2 = document.createElement("p");
    p2.textContent = "Controleer bij uw leverancier of deze doorverwijzing bewust is ingesteld.";
    container.appendChild(p2);
}

/* --- SECTION 1: Score Summary --- */

function renderScoreSummary(averageLevel, totalOrgs, euCount, nonEuCount, orgMap) {
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

    // Energy label
    var label = scoreToLabel(avg);
    var labelEl = document.getElementById("energy-label");
    labelEl.textContent = label;
    labelEl.className = "energy-label energy-label-" + label.toLowerCase();

    // Summary text
    var summaryText = document.getElementById("exec-summary-text");
    summaryText.textContent = "Uw website gebruikt " + totalOrgs + " diensten. " +
        euCount + " daarvan zijn Europees. " + nonEuCount + " niet.";

    // Action text
    var actionText = document.getElementById("exec-action-text");
    var actions = getTopActions(orgMap);
    if (actions.length > 0) {
        actionText.textContent = "Dit kunt u verbeteren door: " + actions.join(" en ") + ".";
    } else {
        actionText.textContent = "Uw website scoort goed op digitale soevereiniteit.";
    }
}

/* --- SECTION 2: Services grouped by provider --- */

function renderServices(orgMap, orgHostnames, scanUrl) {
    var container = document.getElementById("services-container");
    if (!container) return;
    container.textContent = "";

    var orgKeys = Object.keys(orgMap);

    // Sort: worst level first
    orgKeys.sort(function (a, b) { return orgMap[a].level - orgMap[b].level; });

    for (var i = 0; i < orgKeys.length; i++) {
        var orgKey = orgKeys[i];
        var org = orgMap[orgKey];

        var row = document.createElement("div");
        row.className = "service-row";
        if (org.level >= 4) {
            row.classList.add("service-row-ok");
        } else if (org.level <= 2) {
            row.classList.add("service-row-warn");
        }

        // Provider name
        var nameSpan = document.createElement("span");
        nameSpan.className = "service-name";
        nameSpan.textContent = org.name;
        row.appendChild(nameSpan);

        // Country
        if (org.country) {
            var countrySpan = document.createElement("span");
            countrySpan.className = "service-country";
            countrySpan.textContent = countryName(org.country);
            row.appendChild(countrySpan);
        }

        // Level badge
        var badge = document.createElement("span");
        badge.className = "badge badge-level-" + org.level;
        badge.textContent = "Niveau " + org.level;
        row.appendChild(badge);

        // Action hint: check if any hostnames are third-party
        var hostnames = orgHostnames[orgKey] || [];
        var hasThirdParty = false;
        for (var h = 0; h < hostnames.length; h++) {
            if (isThirdParty(hostnames[h], scanUrl)) {
                hasThirdParty = true;
                break;
            }
        }

        if (org.level < 4) {
            var actionSpan = document.createElement("span");
            actionSpan.className = "service-action";
            if (hasThirdParty) {
                actionSpan.textContent = "U kunt dit wijzigen";
            } else {
                actionSpan.textContent = "Dit hoort bij uw websitepakket";
            }
            row.appendChild(actionSpan);
        }

        // Alternative suggestion
        var alt = getAlternative(orgKey);
        if (alt && org.level < 4) {
            var altSpan = document.createElement("span");
            altSpan.className = "service-alternative";
            altSpan.textContent = alt;
            row.appendChild(altSpan);
        }

        // Hostnames as monospace
        if (hostnames.length > 0) {
            var hostsSpan = document.createElement("span");
            hostsSpan.className = "service-hosts";
            hostsSpan.textContent = hostnames.join(", ");
            row.appendChild(hostsSpan);
        }

        container.appendChild(row);
    }

    if (orgKeys.length === 0) {
        var emptyP = document.createElement("p");
        emptyP.className = "section-desc";
        emptyP.textContent = "Geen diensten gevonden.";
        container.appendChild(emptyP);
    }
}

/* --- SECTION 3: Improvement path with energy labels --- */

function renderImprovementPath(orgMap, currentAvg, ipList) {
    var container = document.getElementById("improvement-path");
    if (!container) return;
    container.textContent = "";

    var avg = parseFloat(currentAvg);
    var currentLabel = scoreToLabel(avg);
    var totalIps = ipList.length || 1;

    // Check if already good
    if (avg >= 4.0) {
        var goodP = document.createElement("p");
        goodP.className = "improvement-intro";
        goodP.textContent = "Uw website heeft een " + currentLabel + ". Er zijn geen directe verbeterstappen nodig.";
        container.appendChild(goodP);
        return;
    }

    var introP = document.createElement("p");
    introP.className = "improvement-intro";
    introP.textContent = "Uw website heeft nu een " + currentLabel + ". Met de onderstaande stappen kunt u dit verbeteren.";
    container.appendChild(introP);

    // Build steps dynamically based on what was found
    var steps = [];
    var orgKeys = Object.keys(orgMap);

    // Check for tracking
    var hasTracking = false;
    for (var ti = 0; ti < orgKeys.length; ti++) {
        if (/pixel|track|pinterest|facebook|doubleclick|fb\.com|hotjar/.test(orgKeys[ti]) && orgMap[orgKeys[ti]].level < 4) {
            hasTracking = true;
            break;
        }
    }

    // Check for non-EU analytics
    var hasNonEuAnalytics = false;
    for (var ai = 0; ai < orgKeys.length; ai++) {
        if (/analytics|gtag|google-analytics|googletagmanager|google/.test(orgKeys[ai]) && orgMap[orgKeys[ai]].level < 4) {
            hasNonEuAnalytics = true;
            break;
        }
    }

    // Check for non-EU infra
    var hasNonEuInfra = false;
    for (var ii = 0; ii < orgKeys.length; ii++) {
        if (/cloudflare|akamai|fastly|amazon|aws|microsoft|azure|adobe|typekit/.test(orgKeys[ii]) && orgMap[orgKeys[ii]].level < 4) {
            hasNonEuInfra = true;
            break;
        }
    }

    if (hasTracking) {
        steps.push({
            title: "Verwijder onnodige tracking",
            description: "Verwijder tracking pixels en advertentiediensten. Deze zijn niet nodig voor overheidsdienstverlening.",
            timeline: "1-2 weken",
            who: "Leverancier",
            keywords: ["pixel", "track", "pinterest", "facebook", "doubleclick", "fb.com", "hotjar"],
            targetLevel: 5,
        });
    }

    if (hasNonEuAnalytics) {
        steps.push({
            title: "Stap over op Europese bezoekersstatistieken",
            description: "Vervang Google Analytics door een Europees alternatief zoals Matomo of Fathom. Veel webhosters bieden dit standaard aan.",
            timeline: "2-4 weken",
            who: "Leverancier",
            keywords: ["analytics", "gtag", "google-analytics", "googletagmanager", "google"],
            targetLevel: 4,
        });
    }

    if (hasNonEuInfra) {
        steps.push({
            title: "Bespreek Europese alternatieven voor infrastructuur",
            description: "Bespreek met uw leverancier of CDN, hosting of lettertypen bij een Europese partij ondergebracht kunnen worden.",
            timeline: "1-6 maanden",
            who: "Organisatie + Leverancier",
            keywords: ["cloudflare", "akamai", "fastly", "amazon", "aws", "microsoft", "azure", "adobe", "typekit", "cloudfront", "fonts."],
            targetLevel: 4,
        });
    }

    // Limit to max 3 steps
    if (steps.length > 3) {
        steps = steps.slice(0, 3);
    }

    // Simulate scores
    var simulatedLevels = {};
    for (var oi = 0; oi < ipList.length; oi++) {
        simulatedLevels[ipList[oi].ip_address] = getSovereigntyLevel(ipList[oi]);
    }

    for (var s = 0; s < steps.length; s++) {
        var step = steps[s];

        // Apply improvement
        var hostIpKeys = Object.keys(orgMap);
        for (var ok = 0; ok < hostIpKeys.length; ok++) {
            var orgKeyLower = hostIpKeys[ok];
            var matched = false;
            for (var kw = 0; kw < step.keywords.length; kw++) {
                if (orgKeyLower.indexOf(step.keywords[kw]) !== -1) {
                    matched = true;
                    break;
                }
            }
            if (matched) {
                var orgIps = orgMap[orgKeyLower].ips;
                for (var oip = 0; oip < orgIps.length; oip++) {
                    if (simulatedLevels[orgIps[oip]] < step.targetLevel) {
                        simulatedLevels[orgIps[oip]] = step.targetLevel;
                    }
                }
            }
        }

        // Calculate new average
        var simSum = 0;
        var simKeys = Object.keys(simulatedLevels);
        for (var sk = 0; sk < simKeys.length; sk++) {
            simSum += simulatedLevels[simKeys[sk]];
        }
        var simAvg = (simSum / totalIps).toFixed(1);
        var simLabel = scoreToLabel(parseFloat(simAvg));

        var stepDiv = document.createElement("div");
        stepDiv.className = "improvement-step";

        var stepTitle = document.createElement("h5");
        stepTitle.textContent = "Stap " + (s + 1) + ": " + step.title;
        stepDiv.appendChild(stepTitle);

        var stepDesc = document.createElement("p");
        stepDesc.textContent = step.description;
        stepDiv.appendChild(stepDesc);

        var metaDiv = document.createElement("div");
        metaDiv.className = "step-meta";

        var timeSpan = document.createElement("span");
        timeSpan.className = "step-timeline";
        timeSpan.textContent = "Doorlooptijd: " + step.timeline;
        metaDiv.appendChild(timeSpan);

        var whoSpan = document.createElement("span");
        whoSpan.className = "step-who";
        whoSpan.textContent = step.who;
        metaDiv.appendChild(whoSpan);

        stepDiv.appendChild(metaDiv);

        var estimate = document.createElement("p");
        estimate.className = "step-estimate";
        estimate.textContent = "Verwachte score: " + simAvg + " / 5 (label " + simLabel + ")";
        stepDiv.appendChild(estimate);

        container.appendChild(stepDiv);
    }

    if (steps.length === 0) {
        var noStepsP = document.createElement("p");
        noStepsP.className = "section-desc";
        noStepsP.textContent = "Bespreek met uw leverancier welke diensten bij Europese partijen ondergebracht kunnen worden.";
        container.appendChild(noStepsP);
    }
}

/* --- Vragen voor uw informatieadviseur (section 4) --- */

function renderQuestions(orgMap, hostnameIps, ipList, scanUrl) {
    var container = document.getElementById("questions-container");
    if (!container) return;
    container.textContent = "";

    var questions = [];
    var orgKeys = Object.keys(orgMap);

    // For each org with level <= 2: verwerkersovereenkomst question
    for (var i = 0; i < orgKeys.length; i++) {
        var org = orgMap[orgKeys[i]];
        if (org.level <= 2) {
            questions.push({
                category: "Verwerkersovereenkomsten",
                text: "Heeft u een verwerkersovereenkomst met " + org.name + "?",
            });
        }
    }

    // For third-party hostnames: is it part of website package?
    var hostKeys = Object.keys(hostnameIps);
    var seenHostQuestion = {};
    for (var h = 0; h < hostKeys.length; h++) {
        var hostname = hostKeys[h];
        if (isThirdParty(hostname, scanUrl) && !seenHostQuestion[hostname]) {
            seenHostQuestion[hostname] = true;
            var ipInfo = findIpForHostname(hostname, ipList, hostnameIps);
            if (ipInfo && getSovereigntyLevel(ipInfo) < 4) {
                questions.push({
                    category: "Externe diensten",
                    text: "Is " + hostname + " standaard bij uw websitepakket, of apart geconfigureerd?",
                });
            }
        }
    }

    // For unknown domains (no parent_company)
    for (var j = 0; j < ipList.length; j++) {
        var ip = ipList[j];
        if (!ip.parent_company && ip.asn_org) {
            var alreadyAsked = false;
            for (var qa = 0; qa < questions.length; qa++) {
                if (questions[qa].text.indexOf(ip.asn_org) !== -1) {
                    alreadyAsked = true;
                    break;
                }
            }
            if (!alreadyAsked && isThirdParty(ip.ip_address, scanUrl)) {
                questions.push({
                    category: "Onbekende diensten",
                    text: "Wat is de rol van " + ip.asn_org + " en wie heeft deze dienst ingeschakeld?",
                });
            }
        }
    }

    // Always show DPIA question
    questions.push({
        category: "Compliance",
        text: "Moet u een DPIA uitvoeren op basis van deze bevindingen?",
    });

    // Group by category
    var catGroups = {};
    for (var q = 0; q < questions.length; q++) {
        var qCat = questions[q].category;
        if (!catGroups[qCat]) catGroups[qCat] = [];
        catGroups[qCat].push(questions[q].text);
    }

    var catGroupKeys = Object.keys(catGroups);
    var questionNumber = 1;
    for (var cg = 0; cg < catGroupKeys.length; cg++) {
        var catTitle = document.createElement("h5");
        catTitle.className = "question-category";
        catTitle.textContent = catGroupKeys[cg];
        container.appendChild(catTitle);

        var ol = document.createElement("ol");
        ol.className = "questions-list";
        ol.setAttribute("start", String(questionNumber));
        var qItems = catGroups[catGroupKeys[cg]];
        for (var qi = 0; qi < qItems.length; qi++) {
            var li = document.createElement("li");
            li.textContent = qItems[qi];
            ol.appendChild(li);
            questionNumber++;
        }
        container.appendChild(ol);
    }
}

/* --- Legal background (section 4, neutral tone) --- */

function renderLegalBackground() {
    var container = document.getElementById("legal-context");
    if (!container) return;
    container.textContent = "";

    var p1 = document.createElement("p");
    p1.textContent = "Diensten van niet-Europese bedrijven kunnen onder buitenlandse wetgeving vallen, zoals de Amerikaanse CLOUD Act en FISA Section 702. Dit betekent dat een buitenlands bedrijf juridisch verplicht kan worden om gegevens te verstrekken aan de overheid van het land waar het hoofdkantoor gevestigd is, ook als de data in een Europees datacenter staan.";
    container.appendChild(p1);

    var p2 = document.createElement("p");
    p2.textContent = "De Rijksoverheid heeft in de Rijksvisie Digitale Soevereiniteit (december 2025) het belang onderstreept van bewuste keuzes bij de inzet van niet-Europese diensten. Het DICTU-toetsingsinstrument (januari 2026) biedt overheidsorganisaties een kader om deze risico's te beoordelen.";
    container.appendChild(p2);

    var p3 = document.createElement("p");
    p3.textContent = "Het gaat niet om de vraag of er op dit moment een concreet risico is, maar of uw organisatie kan verantwoorden dat er bewuste keuzes zijn gemaakt over de inzet van deze diensten.";
    container.appendChild(p3);
}

/* --- Distribution bars --- */

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

/* --- Resource Tree --- */

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

/* --- Country bars chart --- */

function renderCountryBars(ipAnalyses) {
    var container = document.getElementById("country-bars");
    if (!container) return;
    container.textContent = "";

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

/* --- World Map with continent outlines --- */

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

    var bg = document.createElementNS(ns, "rect");
    bg.setAttribute("width", String(width));
    bg.setAttribute("height", String(height));
    bg.setAttribute("fill", "#1a2332");
    svg.appendChild(bg);

    var continentPaths = [
        "M390,80 L395,75 410,72 420,68 435,70 440,75 445,80 450,88 445,95 440,100 430,105 420,108 410,110 400,108 392,102 388,95 Z",
        "M395,115 L410,112 425,115 435,120 440,135 438,155 432,175 425,190 418,200 410,205 400,200 392,190 388,175 385,155 388,135 Z",
        "M450,60 L470,55 490,52 510,55 530,58 550,55 570,60 585,65 595,72 600,82 605,95 600,105 590,110 575,115 560,118 545,120 530,118 515,112 500,108 490,100 480,95 470,88 460,82 455,75 Z",
        "M120,65 L140,58 160,55 180,58 200,62 220,68 240,75 255,82 260,92 258,105 250,118 238,130 225,140 210,148 195,152 180,148 168,140 155,130 142,118 135,105 128,92 122,80 Z",
        "M210,160 L225,155 238,158 248,168 252,180 250,195 245,210 238,225 228,238 218,248 208,252 198,248 190,238 185,225 182,210 185,195 190,180 198,168 Z",
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

    var levelColors = {
        5: "#15803d", 4: "#22c55e", 3: "#eab308",
        2: "#f97316", 1: "#fb923c", 0: "#9ca3af",
    };

    var clusters = {};
    for (var ci = 0; ci < ipAnalyses.length; ci++) {
        var ipItem = ipAnalyses[ci];
        if (ipItem.latitude == null || ipItem.longitude == null) continue;
        var clat = Math.round(ipItem.latitude * 10) / 10;
        var clng = Math.round(ipItem.longitude * 10) / 10;
        var key = clat + "," + clng;
        if (!clusters[key]) {
            clusters[key] = { lat: clat, lng: clng, count: 0, level: 5, ips: [] };
        }
        clusters[key].count++;
        var clvl = getSovereigntyLevel(ipItem);
        if (clvl < clusters[key].level) clusters[key].level = clvl;
        clusters[key].ips.push(ipItem);
    }

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

/* --- Service table grouped by organisation --- */

function renderServiceTable(orgMap, hostnameIps) {
    var container = document.getElementById("service-table-container");
    if (!container) return;
    container.textContent = "";

    var orgHostnames = buildOrgHostnames(orgMap, hostnameIps);

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

    var orgKeys = Object.keys(orgMap);
    orgKeys.sort(function (a, b) { return orgMap[a].level - orgMap[b].level; });

    for (var si = 0; si < orgKeys.length; si++) {
        var sOrgKey = orgKeys[si];
        var sOrg = orgMap[sOrgKey];

        var row = document.createElement("tr");
        row.className = levelRowClass(sOrg.level);

        var tdService = document.createElement("td");
        var hostnames = orgHostnames[sOrgKey] || [];
        if (hostnames.length > 0) {
            tdService.textContent = hostnames.join(", ");
        } else {
            tdService.textContent = sOrg.ips.join(", ");
        }
        row.appendChild(tdService);

        var tdOrg = document.createElement("td");
        tdOrg.textContent = sOrg.name;
        row.appendChild(tdOrg);

        var tdCountry = document.createElement("td");
        tdCountry.textContent = sOrg.country ? countryName(sOrg.country) : "-";
        row.appendChild(tdCountry);

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

/* --- IP table --- */

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
