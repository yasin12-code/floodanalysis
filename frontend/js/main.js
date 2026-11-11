/* Entry point: load /api/config + /api/areas, initialise the map and panels,
   load layers for the default (Nowshera) study area. */

import * as api from './api.js';
import { initMap, setResultRenderer } from './map.js';
import { initPanels, renderResult } from './panels.js';

async function boot() {
  let config;
  let areas;
  try {
    [config, areas] = await Promise.all([api.fetchConfig(), api.fetchAreas()]);
  } catch (err) {
    document.getElementById('error-banner').textContent =
      `Could not reach the API: ${err.message}`;
    document.getElementById('error-banner').hidden = false;
    return;
  }

  setResultRenderer(renderResult);
  const mapApi = initMap(config);
  const areasList = areas.areas ?? [];
  if (areasList.length) mapApi.setArea(areasList[0]);
  initPanels(mapApi, areasList);

  try {
    await mapApi.refreshLayers({}, mapApi.currentBboxParams());
  } catch (err) {
    mapApi.showError(err.message);
  }
}

boot();
