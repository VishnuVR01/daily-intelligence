document.addEventListener("DOMContentLoaded", function () {
  const container = document.getElementById("world-map-svg-container");
  if (!container) return;

  const svg = d3.select("#world-map-svg");
  const tooltip = d3.select("#map-tooltip");
  const config = window.WORLD_MAP_CONFIG || {};

  const activeCountry = (config.activeCountry || "").toUpperCase();
  const isBricsMode = !!config.isBrics;
  const activeCategory = config.activeCategory || "";
  const countryCounts = config.countryCounts || {};
  const countriesList = config.countriesList || [];

  const bricsSet = new Set(
    countriesList.filter(c => c.is_brics).map(c => c.code.toUpperCase())
  );

  const countryNameMap = {};
  countriesList.forEach(c => {
    countryNameMap[c.code.toUpperCase()] = c.name;
  });

  const ISO_MAP = {
    "840": "US", "156": "CN", "826": "GB", "276": "DE", "250": "FR",
    "356": "IN", "076": "BR", "643": "RU", "710": "ZA", "392": "JP",
    "124": "CA", "036": "AU", "410": "KR", "484": "MX", "360": "ID",
    "792": "TR", "032": "AR", "756": "CH", "702": "SG", "818": "EG",
    "231": "ET", "364": "IR", "784": "AE", "682": "SA", "566": "NG"
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
    "nigeria": "NG"
  };

  function getAlpha2Code(feature) {
    const numId = String(feature.id || "");
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
          .attr("fill", "#0f172a")
          .attr("rx", 12);

        const g = svg.append("g");

        const graticule = d3.geoGraticule10();
        g.append("path")
          .datum(graticule)
          .attr("class", "graticule")
          .attr("d", path)
          .attr("fill", "none")
          .attr("stroke", "#1e293b")
          .attr("stroke-width", 0.7);

        g.selectAll("path.country")
          .data(geojson.features)
          .enter()
          .append("path")
          .attr("class", d => {
            const code = getAlpha2Code(d);
            const count = code ? (countryCounts[code] || 0) : 0;
            const isSelected = code && code === activeCountry;
            const isBrics = code && bricsSet.has(code);

            const classes = ["country-polygon", getDensityClass(count)];

            if (isSelected) classes.push("selected-polygon");
            if (isBricsMode && isBrics) classes.push("brics-polygon");

            return classes.join(" ");
          })
          .attr("d", path)
          .attr("data-code", d => getAlpha2Code(d) || "")
          .on("mouseover", function (event, d) {
            const code = getAlpha2Code(d);
            const officialName = (code && countryNameMap[code]) || (d.properties && d.properties.name) || "Global Region";
            const count = code ? (countryCounts[code] || 0) : 0;

            d3.select(this).classed("hovered-polygon", true);

            tooltip.style("display", "block")
              .html(`
                <div class="tooltip-country-name">${officialName} ${code ? `(${code})` : ""}</div>
                <div class="tooltip-story-count">${count} ${count === 1 ? "story" : "stories"} today</div>
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
            if (isBricsMode) url += "&brics=1";
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
