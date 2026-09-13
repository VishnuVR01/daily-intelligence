document.addEventListener("DOMContentLoaded", function () {
  const container = document.getElementById("world-map-svg-container");
  if (!container) return;

  const svg = d3.select("#world-map-svg");
  const tooltip = d3.select("#map-tooltip");
  const config = window.WORLD_MAP_CONFIG || {};

  const activeCountry = (config.activeCountry || "").toUpperCase();
  const activeLens = (config.activeLens || "world").toLowerCase();
  const isBricsMode = !!config.isBrics || activeLens === "brics";
  const activeCategory = config.activeCategory || "";
  const countryCounts = config.countryCounts || {};
  const countriesList = config.countriesList || [];
  const lensSet = new Set((config.lensCountryCodes || []).map(c => c.toUpperCase()));

  const bricsSet = new Set(
    countriesList.filter(c => c.is_brics).map(c => c.code.toUpperCase())
  );

  const countryNameMap = {};
  countriesList.forEach(c => {
    countryNameMap[c.code.toUpperCase()] = c.name;
  });

  const ISO_MAP = {
    "004": "AF", "008": "AL", "012": "DZ", "016": "AS", "020": "AD", "024": "AO", "028": "AG", "032": "AR",
    "051": "AM", "036": "AU", "040": "AT", "031": "AZ", "044": "BS", "048": "BH", "050": "BD", "052": "BB",
    "112": "BY", "056": "BE", "084": "BZ", "204": "BJ", "060": "BM", "064": "BT", "068": "BO", "070": "BA",
    "072": "BW", "076": "BR", "096": "BN", "100": "BG", "854": "BF", "108": "BI", "116": "KH", "120": "CM",
    "124": "CA", "132": "CV", "140": "CF", "148": "TD", "152": "CL", "156": "CN", "170": "CO", "174": "KM",
    "178": "CG", "180": "CD", "188": "CR", "384": "CI", "191": "HR", "192": "CU", "196": "CY", "203": "CZ",
    "208": "DK", "262": "DJ", "212": "DM", "214": "DO", "218": "EC", "818": "EG", "222": "SV", "226": "GQ",
    "232": "ER", "233": "EE", "231": "ET", "242": "FJ", "246": "FI", "250": "FR", "266": "GA", "270": "GM",
    "268": "GE", "276": "DE", "288": "GH", "300": "GR", "308": "GD", "320": "GT", "324": "GN", "624": "GW",
    "328": "GY", "332": "HT", "340": "HN", "348": "HU", "352": "IS", "356": "IN", "360": "ID", "364": "IR",
    "368": "IQ", "372": "IE", "376": "IL", "380": "IT", "388": "JM", "392": "JP", "400": "JO", "398": "KZ",
    "404": "KE", "296": "KI", "408": "KP", "410": "KR", "414": "KW", "417": "KG", "418": "LA", "428": "LV",
    "422": "LB", "426": "LS", "430": "LR", "434": "LY", "438": "LI", "440": "LT", "442": "LU", "807": "MK",
    "450": "MG", "454": "MW", "458": "MY", "462": "MV", "466": "ML", "470": "MT", "584": "MH", "478": "MR",
    "480": "MU", "484": "MX", "583": "FM", "498": "MD", "492": "MC", "496": "MN", "499": "ME", "504": "MA",
    "508": "MZ", "104": "MM", "516": "NA", "520": "NR", "524": "NP", "528": "NL", "554": "NZ", "558": "NI",
    "562": "NE", "566": "NG", "578": "NO", "512": "OM", "586": "PK", "585": "PW", "591": "PA", "598": "PG",
    "600": "PY", "604": "PE", "608": "PH", "616": "PL", "620": "PT", "634": "QA", "642": "RO", "643": "RU",
    "646": "RW", "659": "KN", "662": "LC", "670": "VC", "882": "WS", "674": "SM", "678": "ST", "682": "SA",
    "686": "SN", "688": "RS", "690": "SC", "694": "SL", "702": "SG", "703": "SK", "705": "SI", "090": "SB",
    "706": "SO", "710": "ZA", "728": "SS", "724": "ES", "144": "LK", "729": "SD", "740": "SR", "748": "SZ",
    "752": "SE", "756": "CH", "760": "SY", "158": "TW", "762": "TJ", "834": "TZ", "764": "TH", "626": "TL",
    "768": "TG", "776": "TO", "780": "TT", "788": "TN", "792": "TR", "795": "TM", "798": "TV", "800": "UG",
    "804": "UA", "784": "AE", "826": "GB", "840": "US", "858": "UY", "860": "UZ", "548": "VU", "862": "VE",
    "704": "VN", "887": "YE", "894": "ZM", "716": "ZW"
  };

  const NAME_TO_ALPHA2 = {
    "united states of america": "US",
    "united states": "US",
    "china": "CN",
    "united kingdom": "GB",
    "germany": "DE",
    "france": "FR",
    "india": "IN",
    "brazil": "BR",
    "russia": "RU",
    "south africa": "ZA",
    "japan": "JP",
    "canada": "CA",
    "australia": "AU",
    "south korea": "KR",
    "mexico": "MX",
    "indonesia": "ID",
    "turkey": "TR",
    "argentina": "AR",
    "switzerland": "CH",
    "singapore": "SG",
    "egypt": "EG",
    "ethiopia": "ET",
    "iran": "IR",
    "united arab emirates": "AE",
    "saudi arabia": "SA",
    "nigeria": "NG",
    "denmark": "DK",
    "finland": "FI",
    "iceland": "IS",
    "norway": "NO",
    "sweden": "SE",
    "estonia": "EE",
    "latvia": "LV",
    "lithuania": "LT",
    "brunei": "BN",
    "cambodia": "KH",
    "laos": "LA",
    "malaysia": "MY",
    "myanmar": "MM",
    "philippines": "PH",
    "thailand": "TH",
    "timor-leste": "TL",
    "vietnam": "VN"
  };

  function getAlpha2Code(feature) {
    if (!feature || feature.id === undefined || feature.id === null) return null;
    const numId = String(feature.id).padStart(3, '0');
    if (ISO_MAP[numId]) return ISO_MAP[numId];
    const name = (feature.properties && feature.properties.name || "").toLowerCase();
    if (NAME_TO_ALPHA2[name]) return NAME_TO_ALPHA2[name];
    return null;
  }

  function getDensityClass(count) {
    if (count === 0) return "density-0";
    if (count >= 1 && count <= 4) return "density-1-4";
    if (count >= 5 && count <= 9) return "density-5-9";
    if (count >= 10 && count <= 19) return "density-10-19";
    return "density-20-plus";
  }

  // Render standard world map for all country selections (India kept as single country polygon per Part 3 rules)
  renderWorldMap();

  function renderWorldMap() {
    fetch("/static/data/world-110m.json")
      .then(res => res.json())
      .then(worldData => {
        const geojson = topojson.feature(worldData, worldData.objects.countries);
        const width = 960;
        const height = 480;

        const projection = d3.geoNaturalEarth1()
          .scale(160)
          .translate([width / 2, height / 2 + 20]);

        const path = d3.geoPath().projection(projection);

        svg.selectAll("*").remove();

        svg.append("rect")
          .attr("width", width)
          .attr("height", height)
          .attr("fill", "#111815")
          .attr("rx", 10);

        const g = svg.append("g");

        const graticule = d3.geoGraticule10();
        g.append("path")
          .datum(graticule)
          .attr("class", "graticule")
          .attr("d", path)
          .attr("fill", "none")
          .attr("stroke", "#21302A")
          .attr("stroke-width", 0.7);

        g.selectAll("path.country")
          .data(geojson.features)
          .enter()
          .append("path")
          .attr("class", d => {
            const code = getAlpha2Code(d);
            const count = code ? (countryCounts[code] || 0) : 0;
            const isSelected = code && code === activeCountry;
            const isLensMember = code && (lensSet.has(code) || (isBricsMode && bricsSet.has(code)));

            const classes = ["country-polygon", getDensityClass(count)];

            if (isSelected) classes.push("selected-polygon");
            if (activeLens !== "world" && isLensMember) classes.push("lens-member-polygon");

            return classes.join(" ");
          })
          .attr("d", path)
          .attr("data-code", d => getAlpha2Code(d) || "")
          .on("mouseover", function (event, d) {
            const code = getAlpha2Code(d);
            const officialName = (code && countryNameMap[code]) || (d.properties && d.properties.name) || "Global Region";
            const count = code ? (countryCounts[code] || 0) : 0;

            let membershipBadges = [];
            if (code) {
              if (activeLens && activeLens !== "world" && lensSet.has(code)) {
                membershipBadges.push(activeLens.toUpperCase());
              } else if (bricsSet.has(code)) {
                membershipBadges.push("BRICS");
              }
            }
            const membershipStr = membershipBadges.length ? ` &bull; <span class="tooltip-lens" style="color: #D4A559; font-weight: 600;">${membershipBadges.join(" • ")}</span>` : "";

            d3.select(this).classed("hovered-polygon", true);

            tooltip.style("display", "block")
              .html(`
                <div class="tooltip-country-name">${officialName} ${code ? `(${code})` : ""}</div>
                <div class="tooltip-story-count">${count} ${count === 1 ? "story" : "stories"} today${membershipStr}</div>
              `);
          })
          .on("mousemove", function (event) {
            const bounds = container.getBoundingClientRect();
            const mouseX = event.clientX - bounds.left;
            const mouseY = event.clientY - bounds.top;

            tooltip
              .style("left", (mouseX + 15) + "px")
              .style("top", (mouseY - 10) + "px");
          })
          .on("mouseout", function () {
            d3.select(this).classed("hovered-polygon", false);
            tooltip.style("display", "none");
          })
          .on("click", function (event, d) {
            const code = getAlpha2Code(d);
            if (!code) return;

            let url = `/world?country=${code}`;
            if (activeLens && activeLens !== "world") url += `&lens=${encodeURIComponent(activeLens)}`;
            if (activeCategory) url += `&category=${encodeURIComponent(activeCategory)}`;

            window.location.href = url;
          });
      })
      .catch(err => {
        console.error("Failed to render D3 World Map:", err);
      });
  }

  function renderIndiaStateMap() {
    fetch("/static/data/india-states.json")
      .then(res => res.json())
      .then(indiaData => {
        const width = 960;
        const height = 480;

        const projection = d3.geoMercator()
          .center([78.96, 22.50])
          .scale(850)
          .translate([width / 2, height / 2]);

        const path = d3.geoPath().projection(projection);

        svg.selectAll("*").remove();

        svg.append("rect")
          .attr("width", width)
          .attr("height", height)
          .attr("fill", "#0f172a")
          .attr("rx", 12);

        const g = svg.append("g");

        const indiaTotalCount = countryCounts["IN"] || 0;

        g.selectAll("path.state")
          .data(indiaData.features)
          .enter()
          .append("path")
          .attr("class", "country-polygon density-1-4")
          .attr("d", path)
          .attr("stroke", "#2D6143")
          .attr("stroke-width", 1)
          .on("mouseover", function (event, d) {
            const stateName = d.properties.shapeName || "State/UT";

            d3.select(this).classed("hovered-polygon", true);

            tooltip.style("display", "block")
              .html(`
                <div class="tooltip-country-name">${stateName}, India (IN)</div>
                <div class="tooltip-story-count">${indiaTotalCount} India stories today</div>
              `);
          })
          .on("mousemove", function (event) {
            const bounds = container.getBoundingClientRect();
            const mouseX = event.clientX - bounds.left;
            const mouseY = event.clientY - bounds.top;

            tooltip
              .style("left", (mouseX + 15) + "px")
              .style("top", (mouseY - 10) + "px");
          })
          .on("mouseout", function () {
            d3.select(this).classed("hovered-polygon", false);
            tooltip.style("display", "none");
          })
          .on("click", function () {
            let url = `/world?country=IN`;
            if (isBricsMode) url += "&brics=1";
            if (activeCategory) url += `&category=${encodeURIComponent(activeCategory)}`;
            window.location.href = url;
          });

        // Add back-to-world map button overlay
        const backBtn = svg.append("g")
          .attr("transform", "translate(20, 20)")
          .style("cursor", "pointer")
          .on("click", () => { window.location.href = "/world"; });

        backBtn.append("rect")
          .attr("width", 150)
          .attr("height", 32)
          .attr("rx", 16)
          .attr("fill", "#2D6143")
          .attr("stroke", "#88A996");

        backBtn.append("text")
          .attr("x", 75)
          .attr("y", 20)
          .attr("text-anchor", "middle")
          .attr("fill", "#ffffff")
          .attr("font-size", "12")
          .attr("font-weight", "bold")
          .text("← Back to World Map");
      })
      .catch(err => {
        console.error("Failed to render D3 India State Map:", err);
      });
  }
});
