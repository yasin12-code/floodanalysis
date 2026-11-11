/* Leaflet map: basemaps, layer groups, popups, legend, click analysis drawing.
   All geometry arrives as GeoJSON from /api/layers endpoints (PostGIS). */

import * as api from './api.js';

export const RISK_COLORS = { 1: '#FFEDA0', 2: '#FEB24C', 3: '#F03B20', 4: '#BD0026' };
const RISK_LABELS = { 1: 'Low', 2: 'Medium', 3: 'High', 4: 'Very high' };
const SHELTER_COLORS = { open: '#2e8b57', full: '#f28500', closed: '#808080' };
const SHELTER_LABELS = { open: 'Open', full: 'Full', closed: 'Closed' };
const ROAD_STYLES = {
  open: { color: '#9e9e9e', weight: 3, dashArray: null },
  flooded: { color: '#d7191c', weight: 4, dashArray: null },
  blocked: { color: '#1a1a1a', weight: 3.5, dashArray: '8 6' },
  at_risk_open: { color: '#f28500', weight: 4, dashArray: null },
};

let map;
let config;
let currentArea = null;   // active study area (from /api/areas)
let renderResult = () => {};
let renderCounts = () => {};
let lastAnalysis = null; // { lat, lng, radius_m }
let lastFilters = {};
let pickMode = null;     // 'shelter' | 'report' | null
let onPick = () => {};

const layers = {};
const shelterLayersById = new Map();

export function initMap(cfg) {
  config = cfg;
  map = L.map('map', { zoomControl: false }).setView(
    [cfg.map_center_lat, cfg.map_center_lng], cfg.map_zoom);

  L.control.zoom({ position: 'topleft' }).addTo(map);
  L.control.scale({ imperial: false, position: 'bottomleft' }).addTo(map);

  const osm = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
  });
  const carto = L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
    maxZoom: 19,
    attribution: '&copy; OpenStreetMap contributors &copy; CARTO',
    subdomains: 'abcd',
  });
  osm.addTo(map);

  layers.zones = L.geoJSON(null).addTo(map);
  layers.shelters = L.layerGroup().addTo(map);
  layers.roads = L.geoJSON(null).addTo(map);
  layers.caution = L.geoJSON(null, {
    style: { color: '#BD0026', weight: 1.5, dashArray: '6 4', fillColor: '#F03B20', fillOpacity: 0.08 },
  });
  layers.reports = L.layerGroup();
  layers.analysis = L.layerGroup().addTo(map);
  layers.pick = L.layerGroup().addTo(map);

  const overlays = {
    'Flood zones': layers.zones,
    'Caution band (500 m)': layers.caution,
    Shelters: layers.shelters,
    Roads: layers.roads,
    'Flood reports': layers.reports,
    Analysis: layers.analysis,
  };
  L.control.layers({ 'OpenStreetMap': osm, 'CARTO Positron': carto }, overlays,
    { position: 'topright', collapsed: false }).addTo(map);

  map.on('overlayadd', (e) => {
    if (e.layer === layers.caution) loadCautionBand();
    if (e.layer === layers.reports) loadReports();
  });

  map.on('click', (e) => {
    if (pickMode) {
      setPickLocation(e.latlng);
    } else {
      runAnalysis(e.latlng.lat, e.latlng.lng, currentRadius());
    }
  });

  // FR-14: reload layers for the visible area on moveend.
  map.on('moveend', () => {
    refreshLayers(lastFilters, currentBboxParams());
    if (map.hasLayer(layers.reports)) loadReports();
    if (map.hasLayer(layers.caution)) loadCautionBand();
  });

  addLegend();
  loadReports(); // fetch once so the toggle has data immediately
  return publicApi;
}

function currentRadius() {
  const el = document.getElementById('radius-slider');
  return el ? Number(el.value) : config.default_radius_m;
}

export function currentBboxParams() {
  const b = map.getBounds();
  // A 0-sized map (hidden tab, first paint) collapses bounds to a single
  // point; skip bbox then rather than sending a degenerate envelope.
  if (b.getWest() === b.getEast() || b.getSouth() === b.getNorth()) return null;
  return `${b.getWest()},${b.getSouth()},${b.getEast()},${b.getNorth()}`;
}

export function setArea(areaCfg) {
  currentArea = areaCfg;
  // The analysis belongs to the previous area; drop it.
  layers.analysis.clearLayers();
  lastAnalysis = null;
  // moveend reloads every layer with the new area + bbox.
  map.setView([areaCfg.center_lat, areaCfg.center_lng], areaCfg.zoom);
}

export function getCurrentArea() {
  return currentArea;
}

function areaSlug() {
  return currentArea ? currentArea.slug : 'nowshera';
}

function addLegend() {
  const rows = [
    '<div class="legend-head">Legend</div>',
    ...Object.entries(RISK_COLORS).map(([level, color]) =>
      `<div class="legend-row"><span class="swatch" style="background:${color}"></span>Flood risk ${level} · ${RISK_LABELS[level]}</div>`),
    ...Object.entries(SHELTER_COLORS).map(([status, color]) =>
      `<div class="legend-row"><span class="swatch dot" style="background:${color}"></span>Shelter · ${SHELTER_LABELS[status]}</div>`),
    '<div class="legend-row"><span class="swatch ring"></span>Shelter inside a flood zone</div>',
    '<div class="legend-row"><span class="swatch line" style="background:#9e9e9e"></span>Road · open</div>',
    '<div class="legend-row"><span class="swatch line" style="background:#d7191c"></span>Road · flooded</div>',
    '<div class="legend-row"><span class="swatch line" style="background:#1a1a1a;background-image:repeating-linear-gradient(90deg,#1a1a1a 0 6px,transparent 6px 12px)"></span>Road · blocked</div>',
    '<div class="legend-row"><span class="swatch line" style="background:#f28500"></span>Road · open but at risk</div>',
    '<div class="legend-row"><span class="swatch line" style="background:#377eb8;background-image:repeating-linear-gradient(90deg,#377eb8 0 6px,transparent 6px 12px)"></span>Search buffer (dashed)</div>',
  ].join('');
  const control = L.control({ position: 'bottomright' });
  control.onAdd = () => {
    const div = L.DomUtil.create('div', 'legend');
    div.innerHTML = rows;
    return div;
  };
  control.addTo(map);
}

function zoneStyle(feature) {
  const level = feature.properties.risk_level;
  return {
    color: RISK_COLORS[level],
    weight: 1.5,
    fillColor: RISK_COLORS[level],
    fillOpacity: 0.45,
  };
}

function buildZonePopup(props) {
  return `
    <div class="popup">
      <strong>${api.escapeHtml(props.name)}</strong>
      <dl>
        <dt>Risk</dt><dd>${RISK_LABELS[props.risk_level] ?? '—'} (level ${props.risk_level})</dd>
        <dt>Return period</dt><dd>${props.return_period_years ? `${props.return_period_years} years` : '—'}</dd>
        <dt>Source</dt><dd>${api.escapeHtml(props.source ?? '—')}</dd>
      </dl>
    </div>`;
}

function buildShelterPopup(props) {
  const occupancyPct = props.capacity > 0
    ? Math.min(100, Math.round((props.current_occupancy / props.capacity) * 100)) : 0;
  const verified = props.is_verified
    ? '<span class="badge verified">Verified</span>'
    : '<span class="badge unverified">Unverified</span>';
  const warning = props.max_risk_level !== null && props.max_risk_level !== undefined
    ? `<div class="warning">In a flood zone (risk level ${props.max_risk_level})</div>` : '';
  return `
    <div class="popup">
      <strong>${api.escapeHtml(props.name)}</strong> ${verified}
      ${warning}
      <dl>
        <dt>Type</dt><dd>${api.escapeHtml((props.shelter_type ?? '').replaceAll('_', ' '))}</dd>
        <dt>Status</dt><dd>${SHELTER_LABELS[props.status] ?? props.status}</dd>
        <dt>Capacity</dt>
        <dd>
          <div class="occupancy" role="img" aria-label="${props.current_occupancy} of ${props.capacity} occupied">
            <div class="occupancy-fill" style="width:${occupancyPct}%"></div>
          </div>
          ${props.current_occupancy} / ${props.capacity} occupied
        </dd>
        <dt>Phone</dt><dd>${api.escapeHtml(props.contact_phone ?? '—')}</dd>
        <dt>Address</dt><dd>${api.escapeHtml(props.address ?? '—')}</dd>
      </dl>
    </div>`;
}

function buildRoadPopup(props) {
  const atRisk = props.max_risk_level !== null && props.max_risk_level !== undefined;
  return `
    <div class="popup">
      <strong>${api.escapeHtml(props.name ?? 'Unnamed road')}</strong>
      <dl>
        <dt>Type</dt><dd>${api.escapeHtml((props.road_type ?? '').replaceAll('_', ' '))}</dd>
        <dt>Status</dt><dd>${api.escapeHtml(props.status)}</dd>
        <dt>Flood risk</dt><dd>${atRisk ? `Crosses a flood zone (level ${props.max_risk_level})` : 'None'}</dd>
      </dl>
    </div>`;
}

function buildReportPopup(props) {
  const types = { water_level: 'Rising water level', road_blocked: 'Road blocked', people_stranded: 'People stranded' };
  return `
    <div class="popup">
      <strong>${types[props.report_type] ?? api.escapeHtml(props.report_type)}</strong>
      <dl>
        <dt>Severity</dt><dd>${props.severity} of 3</dd>
        <dt>Reported</dt><dd>${api.escapeHtml(String(props.created_at).replace('T', ' ').slice(0, 16))}</dd>
        <dt>Details</dt><dd>${api.escapeHtml(props.description ?? '—')}</dd>
      </dl>
    </div>`;
}

export async function refreshLayers(filters = {}, bbox = null) {
  lastFilters = filters ?? {};
  const area = areaSlug();
  const zoneParams = { bbox, area };
  if (filters.risk && filters.risk.length) zoneParams.risk_min = filters.risk;
  const shelterParams = {
    bbox,
    area,
    include_unverified: Boolean(filters.include_unverified),
  };
  if (filters.shelter_type && filters.shelter_type.length) shelterParams.type = filters.shelter_type;
  if (filters.shelter_status) shelterParams.status = filters.shelter_status;
  if (filters.min_capacity !== null && filters.min_capacity !== undefined && filters.min_capacity !== '')
    shelterParams.min_capacity = filters.min_capacity;
  const roadParams = { bbox, area, at_risk: Boolean(filters.at_risk_roads) };
  if (filters.road_status) roadParams.status = filters.road_status;

  setMapLoading(true);
  try {
    const [zones, shelters, roads] = await Promise.all([
      api.fetchZones(zoneParams),
      api.fetchShelters(shelterParams),
      api.fetchRoads(roadParams),
    ]);
    renderZones(zones);
    renderShelters(shelters);
    renderRoads(roads);
    const counts = {
      zones: zones.features.length,
      shelters: shelters.features.length,
      roads: roads.features.length,
    };
    renderCounts(counts);
    return counts;
  } finally {
    setMapLoading(false);
  }
}

function renderZones(fc) {
  layers.zones.clearLayers();
  layers.zones.addData(fc);
  layers.zones.eachLayer((layer) => {
    layer.setStyle(zoneStyle(layer.feature));
    layer.bindPopup(buildZonePopup(layer.feature.properties));
  });
}

function renderShelters(fc) {
  layers.shelters.clearLayers();
  shelterLayersById.clear();
  for (const feature of fc.features) {
    const props = feature.properties;
    const [lng, lat] = feature.geometry.coordinates;
    const inZone = props.max_risk_level !== null && props.max_risk_level !== undefined;
    const group = L.layerGroup();
    if (inZone) {
      // Warning ring so colour is never the only signal (FR-3, NFR-5).
      const ring = L.circle([lat, lng], {
        radius: 55,
        color: '#BD0026',
        weight: 2.5,
        dashArray: '4 3',
        fill: false,
      });
      ring.bindTooltip('In a flood zone', { direction: 'top' });
      group.addLayer(ring);
    }
    const marker = L.circleMarker([lat, lng], {
      radius: 8,
      color: '#ffffff',
      weight: 1.5,
      fillColor: SHELTER_COLORS[props.status] ?? '#808080',
      fillOpacity: 0.95,
    });
    marker.bindPopup(buildShelterPopup(props));
    shelterLayersById.set(props.id, marker);
    group.addLayer(marker);
    layers.shelters.addLayer(group);
  }
}

function renderRoads(fc) {
  layers.roads.clearLayers();
  layers.roads.addData(fc);
  layers.roads.eachLayer((layer) => {
    const props = layer.feature.properties;
    const atRisk = props.max_risk_level !== null && props.max_risk_level !== undefined;
    const key = props.status === 'open' && atRisk ? 'at_risk_open' : props.status;
    layer.setStyle(ROAD_STYLES[key] ?? ROAD_STYLES.open);
    layer.bindPopup(buildRoadPopup(props));
  });
}

async function loadReports() {
  try {
    const fc = await api.fetchReports({ area: areaSlug() });
    layers.reports.clearLayers();
    for (const feature of fc.features) {
      const [lng, lat] = feature.geometry.coordinates;
      const marker = L.circleMarker([lat, lng], {
        radius: 7,
        color: '#1a1a1a',
        weight: 1.5,
        fillColor: '#ff7800',
        fillOpacity: 0.9,
      });
      marker.bindPopup(buildReportPopup(feature.properties));
      layers.reports.addLayer(marker);
    }
  } catch (err) {
    showError(err.message);
  }
}

async function loadCautionBand() {
  try {
    const fc = await api.fetchZones({ area: areaSlug(), buffer_m: config.caution_radius_m });
    layers.caution.clearLayers();
    layers.caution.addData(fc);
  } catch (err) {
    showError(err.message);
  }
}

export async function runAnalysis(lat, lng, radiusM) {
  if (pickMode) return;
  setMapLoading(true);
  try {
    const result = await api.riskCheck({ lat, lng, radius_m: radiusM, area: areaSlug() });
    lastAnalysis = { lat, lng, radius_m: radiusM };
    drawAnalysis(result);
    renderResult(result);
  } catch (err) {
    showError(err.message);
  } finally {
    setMapLoading(false);
  }
}

function drawAnalysis(result) {
  layers.analysis.clearLayers();
  const { lat, lng } = result.location;
  const clickIcon = L.divIcon({
    className: 'click-pin',
    html: '<span class="click-pin-dot"></span>',
    iconSize: [22, 22],
    iconAnchor: [11, 11],
  });
  L.marker([lat, lng], { icon: clickIcon }).addTo(layers.analysis);

  if (result.search_buffer) {
    L.geoJSON(result.search_buffer, {
      style: { color: '#377eb8', weight: 2, dashArray: '6 5', fill: false },
      interactive: false,
    }).addTo(layers.analysis);
  }
  for (const shelter of result.shelters) {
    const line = L.polyline([[lat, lng], [shelter.lat, shelter.lng]], {
      color: '#377eb8', weight: 1.5, dashArray: '4 4', opacity: 0.8,
    });
    line.bindTooltip(`${shelter.name} — ${api.formatDistance(shelter.distance_m)}`, { sticky: true });
    line.addTo(layers.analysis);
  }
}

export function openShelterPopup(id) {
  const layer = shelterLayersById.get(id);
  if (!layer) return;
  map.panTo(layer.getLatLng());
  layer.openPopup();
}

export function startPick(kind, pickedCallback) {
  pickMode = kind;
  onPick = pickedCallback;
  map.getContainer().classList.add('picking');
}

export function stopPick() {
  pickMode = null;
  layers.pick.clearLayers();
  map.getContainer().classList.remove('picking');
}

function setPickLocation(latlng) {
  layers.pick.clearLayers();
  const icon = L.divIcon({
    className: 'pick-pin',
    html: '<span class="pick-pin-dot"></span>',
    iconSize: [18, 18],
    iconAnchor: [9, 9],
  });
  L.marker(latlng, { icon }).addTo(layers.pick);
  onPick(latlng.lat, latlng.lng);
  pickMode = null;
  map.getContainer().classList.remove('picking');
}

export function useMyLocation() {
  if (!navigator.geolocation) {
    showError('Geolocation is not supported by this browser.');
    return;
  }
  navigator.geolocation.getCurrentPosition(
    (pos) => runAnalysis(pos.coords.latitude, pos.coords.longitude, currentRadius()),
    () => showError('Could not get your location. Please allow geolocation access.'),
    { enableHighAccuracy: true, timeout: 10000 });
}

export function getLastAnalysis() {
  return lastAnalysis;
}

export function getConfig() {
  return config;
}

export function setResultRenderer(fn) {
  renderResult = fn;
}

export function setCountsRenderer(fn) {
  renderCounts = fn;
}

export function showError(message) {
  const banner = document.getElementById('error-banner');
  banner.textContent = message;
  banner.hidden = false;
  window.clearTimeout(banner._timeout);
  banner._timeout = window.setTimeout(() => { banner.hidden = true; }, 6000);
}

function setMapLoading(loading) {
  document.getElementById('map-loading').hidden = !loading;
}

export function refreshShelterLayer(filters = {}) {
  return api.fetchShelters({
    bbox: currentBboxParams(),
    area: areaSlug(),
    include_unverified: Boolean(filters.include_unverified),
  }).then(renderShelters);
}

export function refreshReportsLayer() {
  return loadReports();
}

const publicApi = {
  initMap, refreshLayers, runAnalysis, openShelterPopup, startPick, stopPick,
  useMyLocation, getLastAnalysis, getConfig, setResultRenderer, setCountsRenderer,
  showError, refreshShelterLayer, refreshReportsLayer, currentBboxParams,
  setArea, getCurrentArea,
};
