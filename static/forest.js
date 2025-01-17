/**********************************************
  1) Configuration
**********************************************/
const DATE_STR = "2024_02_01";
const GEOJSON_URL = `http://localhost:5000/data/features/${DATE_STR}.geojson`;
const IMAGE_URL   = `http://localhost:5000/data/jpegimage/2024-02-01.tif`;

// The bounding box corners in [lat, lng] format
const BOUNDS = [
  [9.150763278513326, -79.85548361133965], // southWest
  [9.155968997616267, -79.84585943888108]  // northEast
];

// Default fill opacity
const DEFAULT_FILL_OPACITY = 0.5;

// Status color dictionary
let statusColors = {
  leaves:    "#00FF00",
  fallen:    "#FF0000",
  flowering: "#FF00FF",
  other:     "#FFFF00",
  unlabeled: "#FFAAAA"
};

// Keep track of toggles for each status category
let statusVisibility = {
  leaves: true,
  fallen: true,
  flowering: true,
  other: true,
  unlabeled: true
};

/**********************************************
  2) Globals
**********************************************/
let map, geojsonLayer;
let selectedFeature = null;
let selectedRowEl   = null;   // Track which row is highlighted
let forestData      = [];     // Array of { GlobalID, area, latin, status }

// Dictionary to retrieve the Leaflet layer from a GlobalID
let featureMap      = {};

let inputLatin, inputStatus;
let mouseInfo;              // #coords element
let isHoveringFeature = false; // Track if mouse is over a polygon
// For table sorting
let currentSortKey = null;
let currentSortDir = 1; // 1 = ascending, -1 = descending

/**********************************************
  3) Setup
**********************************************/
window.addEventListener("DOMContentLoaded", () => {
  // Create map
  const midLat = (BOUNDS[0][0] + BOUNDS[1][0]) / 2;
  const midLng = (BOUNDS[0][1] + BOUNDS[1][1]) / 2;

  map = L.map("map", {
    center: [midLat, midLng],
    zoom: 16
  });

  // Base tile layer
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "&copy; OpenStreetMap",
    maxZoom: 19,
  }).addTo(map);

  // Image overlay
  L.imageOverlay(IMAGE_URL, BOUNDS, { opacity: 0.7 }).addTo(map);

  // Fetch GeoJSON
  fetch(GEOJSON_URL)
    .then(resp => resp.json())
    .then(data => {
      // Build geoJSON layer
      geojsonLayer = L.geoJSON(data, {
        style: feature => {
          const st = normalizeStatus(feature.properties?.status);
          return {
            color: "#555",
            weight: 1,
            fillColor: getStatusColor(st),
            fillOpacity: DEFAULT_FILL_OPACITY,
            opacity: 1
          };
        },
        onEachFeature: onEachFeature
      }).addTo(map);

      // Build table data
      forestData = (data.features || []).map(feat => {
        const p = feat.properties || {};
        return {
          GlobalID: p.GlobalID || "",
          // Show area as a number, but we'll limit decimal places when rendering
          area: p.area || "",
          latin: p.latin || "",
          status: p.status || ""
        };
      });

      // At the end of fetch, we render the table
      renderForestTable();
    })
    .catch(err => console.error("Error loading GeoJSON:", err));

  // Mouse panel
  mouseInfo = document.getElementById("coords");

  // Track the mouse position on the map - (no polygon feature here)
  // We do the polygon's "mouseover" for the ID/Name/Status
  map.on("mousemove", e => {
    // Only update the mouse panel if not hovering over a polygon
    if (!isHoveringFeature) {
      updateMousePanel(e.latlng?.lat, e.latlng?.lng, null);
    }
  });

  // Build status menu
  buildStatusMenu();

  // Edit fields
  inputLatin = document.getElementById("editLatin");
  inputStatus = document.getElementById("editStatus");
  document.getElementById("saveStatusBtn").addEventListener("click", submitTreeEdit);

  [inputLatin, inputStatus].forEach(el => {
    el.addEventListener("keypress", e => {
      if(e.key === "Enter") {
        submitTreeEdit();
      }
    });
  });

  // Set up column-sort triggers
  const headers = document.querySelectorAll("#forest-table thead th");
  headers.forEach(th => {
    th.addEventListener("click", () => {
      const key = th.getAttribute("data-key");
      if(!key) return;
      // If clicking same column, toggle asc/desc
      if(currentSortKey === key) {
        currentSortDir *= -1;
      } else {
        currentSortKey = key;
        currentSortDir = 1; // reset to ascending
      }
      sortForestData(currentSortKey, currentSortDir);
      renderForestTable();
    });
  });
});

/**********************************************
  4) onEachFeature
**********************************************/
function onEachFeature(feature, layer){
  // Store ref in featureMap for easy highlight
  const gid = feature.properties?.GlobalID;
  if(gid) {
    featureMap[gid] = layer;
  }

  // Click to select/unselect
  layer.on("click", () => {
    // Unselect the old
    if(selectedFeature && selectedFeature !== layer) {
      unselectFeature(selectedFeature);
    }
    selectedFeature = layer;

    // Apply selected style
    layer.setStyle({
      fillOpacity: 0.08,
      color: "blue",
      weight: 2,
      opacity: 1
    });

    // Fill edit fields
    const props = feature.properties || {};
    inputLatin.value = props.latin || "";
    inputStatus.value = props.status || "";

    // Also highlight & scroll to the corresponding row in the table
    highlightRow(gid, /*scroll*/true);
  });

  // Hover highlight (only if visible and not selected)
  layer.on("mouseover", (e) => {
    isHoveringFeature = true; // Set flag to true
    if (selectedFeature === layer) return; // skip if selected
    const st = normalizeStatus(feature.properties?.status);
    if (statusVisibility[st]) {
      layer.setStyle({ color: "yellow", weight: 2, opacity: 1 });
    }
    // Update the mouse panel with the polygon's properties + actual mouse lat/lng
    updateMousePanel(e.latlng?.lat, e.latlng?.lng, feature);
  });

  // Mouseout revert
  layer.on("mouseout", () => {
    isHoveringFeature = false; // Reset flag when leaving the polygon
    if (selectedFeature === layer) return; // skip if selected
    resetFeatureStyle(layer);
    // Revert to just showing mouse position with no polygon data
    updateMousePanel(undefined, undefined, null);
  });
}

/**********************************************
  5) unselectFeature
**********************************************/
function unselectFeature(layer){
  resetFeatureStyle(layer);
  if(selectedFeature === layer) {
    selectedFeature = null;
  }
}

/**********************************************
  6) resetFeatureStyle
**********************************************/
function resetFeatureStyle(layer){
  if(!layer || !layer.feature) return;
  const st = normalizeStatus(layer.feature.properties?.status);
  if(!statusVisibility[st]) {
    layer.setStyle({ opacity: 0, fillOpacity: 0 });
  } else {
    layer.setStyle({
      color: "#555",
      weight: 1,
      fillColor: getStatusColor(st),
      fillOpacity: DEFAULT_FILL_OPACITY,
      opacity: 1
    });
  }
}

/**********************************************
  7) buildStatusMenu
**********************************************/
function buildStatusMenu(){
  const container = document.getElementById("status-colors");
  const statuses = ["leaves", "fallen", "flowering", "other", "unlabeled"];

  statuses.forEach(st => {
    const div = document.createElement("div");
    div.className = "status-item";

    // Checkbox toggle
    const chk = document.createElement("input");
    chk.type = "checkbox";
    chk.checked = statusVisibility[st];
    chk.style.marginRight = "4px";
    chk.addEventListener("change", () => {
      statusVisibility[st] = chk.checked;
      refreshVisibility();
    });

    // Color swatch
    const swatch = document.createElement("span");
    swatch.className = "color-swatch";
    swatch.style.backgroundColor = statusColors[st];

    // Label
    const label = document.createElement("span");
    label.textContent = st;

    // Submenu for color picking
    const submenu = document.createElement("div");
    submenu.className = "submenu";

    const colorPicker = document.createElement("input");
    colorPicker.type = "color";
    colorPicker.value = statusColors[st];
    colorPicker.addEventListener("change", e => {
      statusColors[st] = e.target.value;
      swatch.style.backgroundColor = e.target.value;
      refreshAllPolygons();
    });
    submenu.appendChild(colorPicker);

    div.addEventListener("click", (evt) => {
      // Avoid toggling if clicking the checkbox itself
      if(evt.target !== chk) {
        submenu.classList.toggle("open");
      }
    });

    div.appendChild(chk);
    div.appendChild(swatch);
    div.appendChild(label);
    div.appendChild(submenu);
    container.appendChild(div);
  });
}

/**********************************************
  8) refreshVisibility
**********************************************/
function refreshVisibility(){
  if(!geojsonLayer) return;
  geojsonLayer.eachLayer(layer => {
    const st = normalizeStatus(layer.feature.properties?.status);
    if(statusVisibility[st]) {
      if(layer === selectedFeature) {
        layer.setStyle({ fillOpacity: 0.08, color:"blue", weight:2, opacity:1 });
      } else {
        resetFeatureStyle(layer);
      }
    } else {
      layer.setStyle({ opacity:0, fillOpacity:0 });
    }
  });
}

/**********************************************
  9) refreshAllPolygons
**********************************************/
function refreshAllPolygons(){
  if(!geojsonLayer) return;
  geojsonLayer.eachLayer(layer => {
    const st = normalizeStatus(layer.feature.properties?.status);
    if(!statusVisibility[st]) {
      layer.setStyle({ opacity:0, fillOpacity:0 });
    } else {
      if(layer === selectedFeature) {
        layer.setStyle({ fillOpacity: 0.08, color: "blue", weight: 2, opacity:1 });
      } else {
        layer.setStyle({
          color: "#555",
          weight: 1,
          fillColor: getStatusColor(st),
          fillOpacity: DEFAULT_FILL_OPACITY,
          opacity: 1
        });
      }
    }
  });
}

/**********************************************
  10) getStatusColor
**********************************************/
function getStatusColor(status){
  if(statusColors[status]) {
    return statusColors[status];
  }
  return statusColors["unlabeled"];
}

/**********************************************
  11) normalizeStatus
**********************************************/
function normalizeStatus(st){
  if(!st || !st.trim()) return "unlabeled";
  return st.trim().toLowerCase();
}

/**********************************************
  12) submitTreeEdit
**********************************************/
function submitTreeEdit(){
  if(!selectedFeature) {
    alert("No polygon selected.");
    return;
  }
  const feat = selectedFeature.feature;
  const props = feat.properties;

  props.latin  = inputLatin.value.trim();
  props.status = inputStatus.value.trim();

  // Re-style
  resetFeatureStyle(selectedFeature);
  // Unselect
  unselectFeature(selectedFeature);

  // Update forestData
  const row = forestData.find(r => r.GlobalID === props.GlobalID);
  if(row) {
    row.latin  = props.latin;
    row.status = props.status;
  }

  // If there's an existing sort, re-sort the data with the last known sort key/dir
  if(currentSortKey !== null) {
    sortForestData(currentSortKey, currentSortDir);
  }

  // Re-render the table with updated data
  renderForestTable();
}

/**********************************************
  13) renderForestTable
**********************************************/
function renderForestTable(){
  const tbody = document.querySelector("#forest-table tbody");
  if(!tbody) return;

  // Clear existing
  tbody.innerHTML = "";

  // Re-render (with column order: latin, status, area, GlobalID)
  forestData.forEach(item => {
    const tr = document.createElement("tr");
    tr.dataset.gid = item.GlobalID; // store the ID so we can highlight from row click

    // Limit area to 1 decimal place
    let areaVal = parseFloat(item.area);
    if(isNaN(areaVal)) areaVal = 0; // fallback if not numeric
    const displayArea = areaVal.toFixed(1);

    tr.innerHTML = `
      <td>${item.latin}</td>
      <td>${item.status}</td>
      <td>${displayArea}</td>
      <td>${item.GlobalID}</td>
    `;

    // Row click -> highlight the corresponding polygon
    tr.addEventListener("click", () => {
      highlightFeatureByGlobalID(item.GlobalID);
    });

    tbody.appendChild(tr);
  });
}

/**********************************************
  14) updateMousePanel
**********************************************/
function updateMousePanel(lat, lng, feature){
  if(!mouseInfo) return;

  let text = "Mouse: ";
  if(typeof lat === "number" && typeof lng === "number") {
    text += `(${lat.toFixed(6)}, ${lng.toFixed(6)})`;
  } else {
    text += "(?, ?)";
  }

  let treeID = "unknown", treeName = "unknown", treeStatus = "unknown";

  // If we actually have a polygon feature under the mouse
  if(feature && feature.properties) {
    const p = feature.properties;
    if(p.GlobalID && p.GlobalID.trim()) treeID = p.GlobalID;
    if(p.latin   && p.latin.trim())     treeName = p.latin;
    if(p.status  && p.status.trim())    treeStatus = p.status;
  }

  text += `\nID: ${treeID}\nName: ${treeName}\nStatus: ${treeStatus}`;
  mouseInfo.textContent = text;
}

/**********************************************
  15) Sorting array by key
**********************************************/
function sortForestData(key, dir){
  forestData.sort((a,b) => {
    let vA = a[key] || "";
    let vB = b[key] || "";

    // If numeric (area), parse as float
    if(key === "area") {
      vA = parseFloat(vA) || 0;
      vB = parseFloat(vB) || 0;
    }
    // Simple string compare for others
    if(vA < vB) return -1 * dir;
    if(vA > vB) return  1 * dir;
    return 0;
  });
}

/**********************************************
  16) highlightRow
     - highlight the row in the table
     - optionally scroll to that row
**********************************************/
function highlightRow(gid, scroll=false){
  // Unhighlight old row
  if(selectedRowEl) {
    selectedRowEl.classList.remove("selected");
  }
  // Find new row
  const newRow = document.querySelector(`tr[data-gid="${gid}"]`);
  if(newRow) {
    newRow.classList.add("selected");
    selectedRowEl = newRow;
    // Scroll to the row if requested
    if(scroll) {
      newRow.scrollIntoView({
        behavior: "smooth",
        block: "center"
      });
    }
  }
}

/**********************************************
  17) highlightFeatureByGlobalID
     - highlight the polygon on the map from row
**********************************************/
function highlightFeatureByGlobalID(gid){
  // Unselect old
  if(selectedFeature) {
    unselectFeature(selectedFeature);
  }

  // highlight new
  const layer = featureMap[gid];
  if(layer) {
    selectedFeature = layer;
    layer.setStyle({
      fillOpacity: 0.08,
      color: "blue",
      weight: 2,
      opacity: 1
    });
    // also highlight that row (and scroll to it)
    highlightRow(gid, /*scroll*/true);
  }
}
