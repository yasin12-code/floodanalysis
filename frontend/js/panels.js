/* Sidebar panels: click-analysis result, filters, shelter/report forms, stats,
   tab switching and responsive behaviour. */

import * as api from './api.js';

const SHELTER_TYPE_LABELS = {
  school: 'School', hospital: 'Hospital', community_center: 'Community centre',
  mosque: 'Mosque', government_building: 'Govt. building', camp: 'Camp', other: 'Other',
};

let mapApi;

export function initPanels(mapApiRef, areasList = []) {
  mapApi = mapApiRef;
  const config = mapApi.getConfig();

  initTabs();
  initRadiusSlider(config);
  initAreaSelect(areasList);
  initFilters();
  initShelterForm();
  initReportForm();
  initLocateButton();
  initStatsTab();
}

function initAreaSelect(areasList) {
  const select = document.getElementById('area-select');
  if (!select || !areasList.length) return;
  for (const area of areasList) {
    const option = document.createElement('option');
    option.value = area.slug;
    option.textContent = `${area.name} — ${area.river_name}`;
    select.appendChild(option);
  }
  select.value = mapApi.getCurrentArea()?.slug ?? areasList[0].slug;
  const initial = mapApi.getCurrentArea() ?? areasList[0];
  document.getElementById('app-subtitle').textContent =
    `${initial.name} study area · ${initial.river_name} · data served from PostGIS`;
  select.addEventListener('change', () => {
    const area = areasList.find((a) => a.slug === select.value);
    if (!area) return;
    // The radius slider follows the area's default search radius.
    const slider = document.getElementById('radius-slider');
    slider.value = area.default_radius_m;
    document.getElementById('radius-value').textContent = `${area.default_radius_m} m`;
    document.getElementById('app-subtitle').textContent =
      `${area.name} study area · ${area.river_name} · data served from PostGIS`;
    const resultPanel = document.getElementById('result-panel');
    resultPanel.className = 'result-placeholder';
    resultPanel.textContent = 'No analysis yet — click the map.';
    mapApi.setArea(area);
    if (!document.getElementById('panel-stats').hidden) loadStats();
  });
}

function initTabs() {
  const tabs = Array.from(document.querySelectorAll('#tabs .tab'));
  const panels = {
    'tab-check': 'panel-check', 'tab-filters': 'panel-filters',
    'tab-add': 'panel-add', 'tab-stats': 'panel-stats',
  };
  tabs.forEach((tab) => {
    tab.addEventListener('click', () => {
      tabs.forEach((t) => {
        t.classList.toggle('active', t === tab);
        t.setAttribute('aria-selected', t === tab ? 'true' : 'false');
      });
      Object.entries(panels).forEach(([tabId, panelId]) => {
        document.getElementById(panelId).hidden = tabId !== tab.id;
      });
      if (tab.id === 'tab-stats') loadStats();
    });
  });
}

function initRadiusSlider(config) {
  const slider = document.getElementById('radius-slider');
  const valueEl = document.getElementById('radius-value');
  slider.value = config.default_radius_m;
  valueEl.textContent = `${config.default_radius_m} m`;
  slider.addEventListener('input', () => {
    valueEl.textContent = `${slider.value} m`;
    const last = mapApi.getLastAnalysis();
    if (last) {
      // FR-9: changing the radius re-runs the analysis for the last clicked point.
      mapApi.runAnalysis(last.lat, last.lng, Number(slider.value));
    }
  });
}

function initLocateButton() {
  document.getElementById('btn-locate').addEventListener('click', () => mapApi.useMyLocation());
}

export function renderResult(result) {
  const panel = document.getElementById('result-panel');
  const bannerClass = result.status === 'in_zone' ? 'in_zone'
    : result.status === 'near_zone' ? 'near_zone' : 'outside';

  const zoneList = result.zones.length
    ? `<ul class="zone-list">${result.zones.map((z) =>
        `<li>${api.escapeHtml(z.name)} (level ${z.risk_level}${z.return_period_years ? `, ${z.return_period_years}-year` : ''})</li>`).join('')}</ul>`
    : '';

  const shelterRows = result.shelters.map((s) => {
    const recommended = s.id === result.recommended_shelter_id;
    const unsafeTag = s.in_flood_zone ? '<span class="tag unsafe">Unsafe: in flood zone</span>' : '';
    const recommendedBadge = recommended ? '<span class="tag recommended">Recommended</span>' : '';
    return `
      <li class="shelter-row${recommended ? ' is-recommended' : ''}" role="button" tabindex="0" data-shelter-id="${s.id}">
        <div class="shelter-row-main">
          <strong>${api.escapeHtml(s.name)}</strong>
          ${recommendedBadge}${unsafeTag}
        </div>
        <div class="shelter-row-meta">
          ${api.escapeHtml(SHELTER_TYPE_LABELS[s.shelter_type] ?? s.shelter_type)} ·
          ${api.formatDistance(s.distance_m)} ·
          ${s.available} of ${s.capacity} places free ·
          ${api.escapeHtml(s.status)}
        </div>
      </li>`;
  }).join('');

  const noRecommendationHint = result.recommended_shelter_id === null && result.status !== 'outside'
    ? '<p class="hint">No safe open shelter found — try increasing the search radius.</p>' : '';

  const zoneDistance = result.nearest_zone_distance_m === null ? '—'
    : api.formatDistance(result.nearest_zone_distance_m);

  panel.innerHTML = `
    <div class="banner ${bannerClass}">${api.escapeHtml(result.risk_label)}</div>
    <dl class="result-summary">
      <dt>Status</dt><dd>${result.status.replace('_', ' ')}</dd>
      <dt>Distance to nearest zone</dt><dd>${zoneDistance}</dd>
      <dt>Flooded/blocked roads in radius</dt><dd>${result.flooded_roads_in_radius}</dd>
    </dl>
    ${zoneList}
    <h3>Nearby shelters (${result.shelters.length})</h3>
    <p class="hint">Distances are straight-line, not routes.</p>
    ${shelterRows ? `<ul class="shelter-list">${shelterRows}</ul>` : '<p class="hint">No verified shelters in this radius.</p>'}
    ${noRecommendationHint}`;

  panel.querySelectorAll('.shelter-row').forEach((row) => {
    const open = () => mapApi.openShelterPopup(Number(row.dataset.shelterId));
    row.addEventListener('click', open);
    row.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); open(); }
    });
  });
}

function initFilters() {
  const form = document.getElementById('filter-form');
  const resetBtn = document.getElementById('btn-reset-filters');

  form.addEventListener('submit', (e) => {
    e.preventDefault();
    applyFilters();
  });
  resetBtn.addEventListener('click', () => {
    form.reset();
    applyFilters();
  });
  mapApi.setCountsRenderer((counts) => {
    document.getElementById('layer-counts').textContent =
      `Visible features — zones: ${counts.zones}, shelters: ${counts.shelters}, roads: ${counts.roads}`;
  });
}

function collectFilters() {
  const form = document.getElementById('filter-form');
  const checked = (name) => Array.from(form.querySelectorAll(`input[name="${name}"]:checked`))
    .map((el) => el.value);
  return {
    risk: checked('risk').map(Number),
    shelter_type: checked('shelter-type'),
    shelter_status: document.getElementById('filter-shelter-status').value || null,
    min_capacity: document.getElementById('filter-min-capacity').value || null,
    include_unverified: document.getElementById('filter-unverified').checked,
    road_status: document.getElementById('filter-road-status').value || null,
    at_risk_roads: document.getElementById('filter-at-risk-roads').checked,
  };
}

function applyFilters() {
  const filters = collectFilters();
  mapApi.refreshLayers(filters, mapApi.currentBboxParams())
    .catch((err) => mapApi.showError(err.message));
}

function initShelterForm() {
  const form = document.getElementById('shelter-form');
  const pickBtn = document.getElementById('btn-pick-shelter');
  const coordsEl = document.getElementById('shelter-coords');

  pickBtn.addEventListener('click', () => {
    if (pickBtn.dataset.picking) {
      mapApi.stopPick();
      pickBtn.dataset.picking = '';
      pickBtn.textContent = 'Pick location on map';
      return;
    }
    pickBtn.dataset.picking = '1';
    pickBtn.textContent = 'Click the map to set the location…';
    mapApi.startPick('shelter', (lat, lng) => {
      document.getElementById('shelter-lat').value = lat;
      document.getElementById('shelter-lng').value = lng;
      coordsEl.textContent = `Set: ${lat.toFixed(5)}, ${lng.toFixed(5)}`;
      pickBtn.dataset.picking = '';
      pickBtn.textContent = 'Pick location on map';
    });
  });

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const status = document.getElementById('shelter-form-status');
    status.textContent = '';
    status.className = 'form-status';
    const name = document.getElementById('shelter-name').value.trim();
    const capacity = document.getElementById('shelter-capacity').value;
    const lat = document.getElementById('shelter-lat').value;
    const lng = document.getElementById('shelter-lng').value;
    const phone = document.getElementById('shelter-phone').value.trim();
    const phonePattern = /^[0-9+\-\s]+$/;

    if (!name || name.length > 120) return fail(status, 'Name is required (1–120 characters).');
    if (!form.elements['shelter-type'].value) return fail(status, 'Please choose a shelter type.');
    if (capacity === '' || Number(capacity) < 0 || Number(capacity) > 100000)
      return fail(status, 'Capacity must be between 0 and 100000.');
    if (phone && !phonePattern.test(phone))
      return fail(status, 'Phone may contain digits, spaces, plus and dashes only.');
    if (!lat || !lng) return fail(status, 'Pick a location on the map first.');

    try {
      await api.submitShelter({
        name,
        area: mapApi.getCurrentArea()?.slug ?? 'nowshera',
        shelter_type: form.elements['shelter-type'].value,
        capacity: Number(capacity),
        contact_phone: phone || null,
        address: document.getElementById('shelter-address').value.trim() || null,
        lat: Number(lat),
        lng: Number(lng),
      });
      status.className = 'form-status success';
      status.textContent = 'Shelter suggested — thank you! It is unverified and appears on the map when "Include unverified shelters" is on.';
      form.reset();
      document.getElementById('shelter-coords').textContent = 'Not set — click the map';
      mapApi.refreshShelterLayer(collectFilters());
    } catch (err) {
      fail(status, err.message);
    }
  });
}

function initReportForm() {
  const form = document.getElementById('report-form');
  const pickBtn = document.getElementById('btn-pick-report');
  const coordsEl = document.getElementById('report-coords');

  pickBtn.addEventListener('click', () => {
    if (pickBtn.dataset.picking) {
      mapApi.stopPick();
      pickBtn.dataset.picking = '';
      pickBtn.textContent = 'Pick location on map';
      return;
    }
    pickBtn.dataset.picking = '1';
    pickBtn.textContent = 'Click the map to set the location…';
    mapApi.startPick('report', (lat, lng) => {
      document.getElementById('report-lat').value = lat;
      document.getElementById('report-lng').value = lng;
      coordsEl.textContent = `Set: ${lat.toFixed(5)}, ${lng.toFixed(5)}`;
      pickBtn.dataset.picking = '';
      pickBtn.textContent = 'Pick location on map';
    });
  });

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const status = document.getElementById('report-form-status');
    status.textContent = '';
    status.className = 'form-status';
    const lat = document.getElementById('report-lat').value;
    const lng = document.getElementById('report-lng').value;
    if (!form.elements['report-type'].value) return fail(status, 'Please choose a report type.');
    if (!lat || !lng) return fail(status, 'Pick a location on the map first.');
    try {
      await api.submitFloodReport({
        report_type: form.elements['report-type'].value,
        severity: Number(form.elements['report-severity'].value),
        description: document.getElementById('report-description').value.trim() || null,
        area: mapApi.getCurrentArea()?.slug ?? 'nowshera',
        lat: Number(lat),
        lng: Number(lng),
      });
      status.className = 'form-status success';
      status.textContent = 'Report submitted — thank you!';
      form.reset();
      document.getElementById('report-coords').textContent = 'Not set — click the map';
      mapApi.refreshReportsLayer();
    } catch (err) {
      fail(status, err.message);
    }
  });
}

function fail(statusEl, message) {
  statusEl.className = 'form-status error';
  statusEl.textContent = message;
  return false;
}

function initStatsTab() {
  loadStats();
}

async function loadStats() {
  const container = document.getElementById('stats-container');
  try {
    const stats = await api.fetchStats({ area: mapApi.getCurrentArea()?.slug ?? 'nowshera' });
    const areas = Object.entries(stats.area_km2_by_risk_level)
      .map(([level, km2]) => `<li>Level ${level}: <strong>${km2} km²</strong></li>`)
      .join('');
    const shelterInside = stats.shelters.inside_flood_zone;
    const shelterOutside = stats.shelters.outside_flood_zone;
    container.innerHTML = `
      <div class="stat-card">
        <h3>Flood zone area by risk level</h3>
        ${areas ? `<ul class="stat-list">${areas}</ul>` : '<p class="hint">No zones loaded.</p>'}
      </div>
      <div class="stat-card">
        <h3>Shelters inside flood zones</h3>
        <p><strong>${shelterInside.count}</strong> shelters · <strong>${shelterInside.total_capacity}</strong> total capacity</p>
        <h3>Shelters outside flood zones</h3>
        <p><strong>${shelterOutside.count}</strong> shelters · <strong>${shelterOutside.total_capacity}</strong> total capacity</p>
      </div>
      <div class="stat-card">
        <h3>Open shelter capacity</h3>
        <p><strong>${stats.open_available_capacity}</strong> places currently available</p>
      </div>
      <div class="stat-card">
        <h3>Roads at risk</h3>
        <p><strong>${stats.roads_at_risk_km} km</strong> of road intersects a flood zone</p>
      </div>`;
  } catch (err) {
    container.innerHTML = `<p class="form-status error">${api.escapeHtml(err.message)}</p>`;
  }
}
