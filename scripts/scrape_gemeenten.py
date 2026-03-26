"""
Scrape alle Nederlandse gemeenten + websites.
Stap 1: Haal volledige lijst van Wikipedia (342+ gemeenten)
Stap 2: Afleiden website URLs (www.{naam}.nl patroon + handmatige overrides)
Stap 3: Verifieer steekproef
Output: gemeenten_websites.json en gemeenten_websites.csv
"""
import csv
import json
import time
from playwright.sync_api import sync_playwright


# Known overrides where the website doesn't follow www.{naam}.nl
WEBSITE_OVERRIDES = {
    "'s-Hertogenbosch": "www.s-hertogenbosch.nl",
    "Den Haag": "www.denhaag.nl",
    "De Bilt": "www.debilt.nl",
    "De Ronde Venen": "www.derondevenen.nl",
    "De Wolden": "www.dewolden.nl",
    "De Fryske Marren": "www.defryskemarren.nl",
    "Het Hogeland": "www.hethogeland.nl",
    "Bergen (L.)": "www.bergen.nl",
    "Bergen (NH.)": "www.bergen-nh.nl",
    "Súdwest-Fryslân": "www.sudwestfryslan.nl",
    "Noardeast-Fryslân": "www.noardeast-fryslan.nl",
    "Nuenen, Gerwen en Nederwetten": "www.nuenen.nl",
    "Hof van Twente": "www.hofvantwente.nl",
    "Loon op Zand": "www.loonopzand.nl",
    "Bergen op Zoom": "www.bergenopzoom.nl",
    "Mook en Middelaar": "www.mookenmiddelaar.nl",
    "Peel en Maas": "www.peelenmaas.nl",
    "West Maas en Waal": "www.westmaasenwaal.nl",
    "West Betuwe": "www.westbetuwe.nl",
    "Oost Gelre": "www.oostgelre.nl",
    "Berg en Dal": "www.bergendal.nl",
    "Sint-Michielsgestel": "www.sint-michielsgestel.nl",
    "Gilze en Rijen": "www.gilzerijen.nl",
    "Land van Cuijk": "www.landvancuijk.nl",
    "Son en Breugel": "www.sonenbreugel.nl",
    "Dijk en Waard": "www.dijkenwaard.nl",
    "Stede Broec": "www.stedebroec.nl",
    "Edam-Volendam": "www.edam-volendam.nl",
    "Gooise Meren": "www.gooisemeren.nl",
    "Hollands Kroon": "www.hollandskroon.nl",
    "Ouder-Amstel": "www.ouder-amstel.nl",
    "Alphen aan den Rijn": "www.alphenaandenrijn.nl",
    "Valkenburg aan de Geul": "www.valkenburg.nl",
    "Horst aan de Maas": "www.horstaan demaas.nl",
    "Rijssen-Holten": "www.rijssen-holten.nl",
    "Olst-Wijhe": "www.olst-wijhe.nl",
    "Sittard-Geleen": "www.sittard-geleen.nl",
    "Eijsden-Margraten": "www.eijsden-margraten.nl",
    "Echt-Susteren": "www.echt-susteren.nl",
    "Gulpen-Wittem": "www.gulpen-wittem.nl",
    "Geldrop-Mierlo": "www.geldrop-mierlo.nl",
    "Gemert-Bakel": "www.gemert-bakel.nl",
    "Heeze-Leende": "www.heeze-leende.nl",
    "Reusel-De Mierden": "www.reuseldemierden.nl",
    "Alphen-Chaam": "www.alphen-chaam.nl",
    "Neder-Betuwe": "www.neder-betuwe.nl",
    "Oude IJsselstreek": "www.oude-ijsselstreek.nl",
    "Stichtse Vecht": "www.stichtsevecht.nl",
    "Utrechtse Heuvelrug": "www.heuvelrug.nl",
    "Altena": "www.gemeentealtena.nl",
    "Dantumadiel": "www.dantumadiel.frl",
    "Tietjerksteradeel": "www.t-diel.nl",
    "Rozendaal": "www.gemeenterozendaal.nl",
    "Beek": "www.gemeentebeek.nl",
    "Pijnacker-Nootdorp": "www.pijnacker-nootdorp.nl",
    "Leidschendam-Voorburg": "www.lv.nl",
    "Kaag en Braassem": "www.kaagenbraassem.nl",
    "Horst aan de Maas": "www.horstaandemaas.nl",
    "Midden-Groningen": "www.midden-groningen.nl",
    "Midden-Drenthe": "www.middendrenthe.nl",
    "Capelle aan den IJssel": "www.capelleaandenijssel.nl",
    "Krimpen aan den IJssel": "www.krimpenaandenijssel.nl",
    "Bergeijk": "www.bergeijk.nl",
    "Opsterland": "www.opsterland.nl",
    "Ooststellingwerf": "www.ooststellingwerf.nl",
    "Weststellingwerf": "www.weststellingwerf.nl",
    "Smallingerland": "www.smallingerland.nl",
    "Borger-Odoorn": "www.borger-odoorn.nl",
}


def derive_website(naam):
    """Derive the most likely website URL for a gemeente."""
    if naam in WEBSITE_OVERRIDES:
        return f"https://{WEBSITE_OVERRIDES[naam]}"

    # Default: clean the name and use www.{cleaned}.nl
    clean = naam.lower()
    # Remove parenthetical suffixes like "(L.)" or "(NH.)"
    if "(" in clean:
        clean = clean[:clean.index("(")].strip()
    # Remove special chars, keep hyphens
    clean = clean.replace(" ", "").replace("'", "").replace(".", "")
    clean = clean.replace("ë", "e").replace("é", "e").replace("ü", "u")
    clean = clean.replace("ú", "u").replace("ô", "o").replace("â", "a")
    clean = clean.replace("ï", "i")

    return f"https://www.{clean}.nl"


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Step 1: Wikipedia
        print("=== Stap 1: Wikipedia lijst ophalen ===")
        page.goto(
            "https://nl.wikipedia.org/wiki/Lijst_van_Nederlandse_gemeenten",
            wait_until="networkidle",
            timeout=30000,
        )
        time.sleep(2)

        # Use JS evaluate for reliable extraction
        raw = page.evaluate("""() => {
            const table = document.querySelector('table.wikitable');
            const rows = table.querySelectorAll('tr');
            const result = [];
            for (let i = 1; i < rows.length; i++) {
                const row = rows[i];
                const th = row.querySelector('th');
                const tds = row.querySelectorAll('td');
                if (th && tds.length >= 3) {
                    result.push({
                        naam: th.textContent.trim(),
                        provincie: tds[2].textContent.trim(),
                        cbs_code: tds[1].textContent.trim()
                    });
                }
            }
            return result;
        }""")

        gemeenten = []
        for r in raw:
            if r["naam"]:
                gemeenten.append({
                    "naam": r["naam"],
                    "provincie": r["provincie"],
                    "cbs_code": r["cbs_code"],
                    "website": derive_website(r["naam"]),
                })

        print(f"Gevonden: {len(gemeenten)} gemeenten")

        # Step 2: Quick verify a sample
        print(f"\n=== Stap 2: Verificatie (steekproef van 15) ===")
        import random
        random.seed(42)
        sample = random.sample(range(len(gemeenten)), min(15, len(gemeenten)))

        ok_count = 0
        err_count = 0
        for idx in sample:
            g = gemeenten[idx]
            url = g["website"]
            try:
                resp = page.goto(url, wait_until="domcontentloaded", timeout=8000)
                status = resp.status if resp else "?"
                final_url = page.url
                ok_count += 1
                print(f"  OK  {g['naam']:30s} {url} -> {status}")
            except Exception as e:
                err_count += 1
                err_msg = str(e).split("at https://")[0][:50]
                print(f"  ERR {g['naam']:30s} {url} -> {err_msg}")

        print(f"\nSteekproef: {ok_count} OK, {err_count} fouten")

        browser.close()

    # Output CSV
    output_csv = "scripts/gemeenten_websites.csv"
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["naam", "provincie", "cbs_code", "website"])
        writer.writeheader()
        for g in gemeenten:
            writer.writerow(g)

    # Output JSON
    output_json = "scripts/gemeenten_websites.json"
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(gemeenten, f, indent=2, ensure_ascii=False)

    print(f"\n=== Resultaat ===")
    print(f"Totaal: {len(gemeenten)} gemeenten")
    print(f"CSV: {output_csv}")
    print(f"JSON: {output_json}")

    # Show per provincie
    from collections import Counter
    prov_counts = Counter(g["provincie"] for g in gemeenten)
    print(f"\nPer provincie:")
    for prov, count in sorted(prov_counts.items()):
        print(f"  {prov:25s} {count}")

    return gemeenten


if __name__ == "__main__":
    main()
