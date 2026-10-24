'use strict';

const $ = id => document.getElementById(id);
const PLACES = {andorra: [42.5063, 1.5218], seu: [42.3576, 1.456], arfa: [42.34, 1.426]};
const PLACE_NAMES = {andorra: 'Andorra la Vella', seu: 'La Seu d’Urgell', arfa: 'Arfa'};
const HIGHLIGHTS = {22: '#277f5b', 13: '#b78935', 10: '#735593', 6: '#bf7953', 3: '#758899', 31: '#368bb1', 60: '#bcdce7'};
const state = {enabled: new Set(), explain: false, night: false, summary: null};
const cache = new Map();
let map, grid, places, boundary, demoCourse, userCourse;

function showError(message) { $('error').textContent = message; $('error').hidden = false; }
function levelForZoom(zoom) { return zoom >= 14 ? 0 : zoom >= 12 ? 1 : zoom >= 10 ? 2 : 3; }
function pattern(layer) { return layer.pattern ? layer.pattern.match(/a+|\.+/g).map(run => run.length) : []; }
function colour(code) { return state.explain ? HIGHLIGHTS[code] : state.summary.layers[code][state.night ? 'night' : 'day']; }

async function sourceTile(level, x, y) {
  const id = `${level}/${x}/${y}`;
  if (!state.summary.levels[level].available.has(`${x}/${y}`)) return [];
  if (!cache.has(id)) {
    cache.set(id, fetch(`data/${id}.json`).then(response => {
      if (!response.ok) throw new Error('Map data could not be loaded. Reload this page to retry.');
      return response.json();
    }).catch(error => { cache.delete(id); throw error; }));
  }
  return cache.get(id);
}

function drawFeature(context, feature, coords) {
  const [code, points] = feature;
  if (!state.enabled.has(code)) return;
  const layer = state.summary.layers[code];
  context.beginPath();
  points.forEach(([lon, lat], index) => {
    const p = L.CRS.EPSG3857.latLngToPoint(L.latLng(lat, lon), coords.z);
    const x = p.x - coords.x * 256, y = p.y - coords.y * 256;
    if (index) context.lineTo(x, y); else context.moveTo(x, y);
  });
  if (layer.polygon) {
    context.closePath(); context.fillStyle = colour(code); context.fill();
  } else {
    context.strokeStyle = colour(code);
    context.lineWidth = state.explain ? 2 : 1;
    context.setLineDash(pattern(layer));
    context.lineCap = 'butt'; context.lineJoin = 'round'; context.stroke();
  }
}

function updateLegend() {
  const level = levelForZoom(map.getZoom());
  const counts = state.summary.levels[level].counts;
  document.querySelectorAll('.layer-row').forEach(row => {
    const code = Number(row.dataset.code), n = counts[code] || 0;
    row.classList.toggle('absent', n === 0);
    row.querySelector('.layer-count').textContent = n ? n.toLocaleString() : 'zoom in';
    const canvas = row.querySelector('canvas'), context = canvas.getContext('2d');
    context.clearRect(0, 0, 64, 28);
    context.fillStyle = colour(code); context.strokeStyle = colour(code);
    context.lineWidth = state.explain ? 4 : 2;
    context.setLineDash(pattern(state.summary.layers[code]).map(n => n * 2));
    if (code === 60) context.fillRect(5, 7, 52, 14);
    else { context.beginPath(); context.moveTo(0, 14); context.lineTo(64, 14); context.stroke(); }
  });
  const resolution = [24, 22, 20, 18][level];
  $('detail-status').textContent = `IMG detail ${level} · ${resolution}-bit geometry · zoom ${map.getZoom()}`;
  $('toggle-all').textContent = state.enabled.size ? 'Hide all' : 'Show all';
}

function redraw() { updateLegend(); grid.redraw(); }

function courseLayer(segments) {
  return L.polyline(segments.map(points => points.map(([lon, lat]) => [lat, lon])), {
    color: '#c22382', weight: 4, opacity: 1, lineCap: 'round', lineJoin: 'round', interactive: false,
  });
}

function fitCourse(layer) { map.fitBounds(layer.getBounds(), {padding: [65, 70], maxZoom: 15, animate: false}); }

async function identify(event) {
  const level = levelForZoom(map.getZoom()), meta = state.summary.levels[level];
  const p = L.CRS.EPSG3857.latLngToPoint(event.latlng, meta.tileZoom);
  const features = await sourceTile(level, Math.floor(p.x / 256), Math.floor(p.y / 256));
  const click = map.latLngToContainerPoint(event.latlng);
  let nearest = null, distance = 9;
  for (const [code, points] of features) {
    if (!state.enabled.has(code) || code === 60) continue;
    for (let i = 1; i < points.length; i++) {
      const a = map.latLngToContainerPoint([points[i-1][1], points[i-1][0]]);
      const b = map.latLngToContainerPoint([points[i][1], points[i][0]]);
      const d = L.LineUtil.pointToSegmentDistance(click, a, b);
      if (d < distance) { nearest = code; distance = d; }
    }
  }
  if (nearest !== null) {
    const layer = state.summary.layers[nearest];
    L.popup().setLatLng(event.latlng).setContent(`<b>${layer.name}</b><br>${layer.description}<small>Present in your Garmin map · one-pixel base line.<br>Names and difficulty labels are not stored.</small>`).openOn(map);
  }
}

async function openGPX(file) {
  if (!file) return;
  try {
    if (file.size > 10_000_000) throw new Error('Choose a GPX smaller than 10 MB.');
    const xml = new DOMParser().parseFromString(await file.text(), 'application/xml');
    if (xml.querySelector('parsererror')) throw new Error('This file is not valid GPX XML.');
    let groups = [...xml.getElementsByTagNameNS('*', 'trkseg')];
    if (!groups.length) groups = [...xml.getElementsByTagNameNS('*', 'rte')];
    const segments = groups.map(group => [...group.children]
      .filter(node => ['trkpt', 'rtept'].includes(node.localName))
      .map(node => [Number(node.getAttribute('lon') ?? NaN), Number(node.getAttribute('lat') ?? NaN)]));
    const total = segments.reduce((n, points) => n + points.length, 0);
    if (!total || total > 200_000 || segments.some(points => points.length < 2)) throw new Error('Choose a GPX track or route with 2–200,000 points.');
    if (segments.flat().some(([lon, lat]) => !Number.isFinite(lon) || !Number.isFinite(lat) || Math.abs(lon) > 180 || Math.abs(lat) > 85)) throw new Error('This GPX contains invalid map coordinates.');
    if (userCourse) map.removeLayer(userCourse);
    userCourse = courseLayer(segments).addTo(map);
    fitCourse(userCourse);
    $('course-status').textContent = `${file.name} · ${total.toLocaleString()} points · browser only`;
    $('clear-course').hidden = false;
    if (demoCourse) map.removeLayer(demoCourse);
    $('demo').checked = false;
    $('error').hidden = true;
  } catch (error) { showError(error.message); }
}

async function init() {
  const response = await fetch('summary.json');
  if (!response.ok) throw new Error('The map export is missing. Run preview/export.py and reload.');
  state.summary = await response.json();
  Object.values(state.summary.levels).forEach(meta => { meta.available = new Set(meta.tiles); });
  state.enabled = new Set(Object.keys(state.summary.layers).map(Number));
  $('map-size').textContent = `${(state.summary.imageBytes / 1_000_000).toFixed(1)} MB · quiet preview`;
  map = L.map('map', {zoomControl: false, minZoom: 7, maxZoom: 18, zoomAnimation: false, fadeAnimation: false}).setView([42.356, 1.445], 13);
  window.previewMap = map;
  L.control.zoom({position: 'topright'}).addTo(map);
  L.control.scale({imperial: false, maxWidth: 110}).addTo(map);
  map.attributionControl.setPrefix(false).addAttribution('Map data © <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>');

  const GarminGrid = L.GridLayer.extend({
    createTile(coords, done) {
      const canvas = document.createElement('canvas'), ratio = window.devicePixelRatio || 1;
      canvas.width = canvas.height = 256 * ratio;
      const context = canvas.getContext('2d'); context.scale(ratio, ratio);
      const level = levelForZoom(coords.z), meta = state.summary.levels[level];
      const scale = 2 ** (coords.z - meta.tileZoom), jobs = [];
      for (let x = Math.floor(coords.x / scale); x < Math.ceil((coords.x + 1) / scale); x++) {
        for (let y = Math.floor(coords.y / scale); y < Math.ceil((coords.y + 1) / scale); y++) jobs.push(sourceTile(level, x, y));
      }
      Promise.all(jobs).then(tiles => {
        // Water is drawn beneath lines, including when a display tile crosses data tiles.
        const features = tiles.flat();
        for (const feature of features) if (feature[0] === 60) drawFeature(context, feature, coords);
        for (const feature of features) if (feature[0] !== 60) drawFeature(context, feature, coords);
        done(null, canvas);
      }).catch(error => { showError(error.message); done(error, canvas); });
      return canvas;
    },
  });
  grid = new GarminGrid({tileSize: 256, keepBuffer: 1, noWrap: true, updateWhenIdle: true}).addTo(map);

  for (const code of [22, 13, 10, 6, 3, 31, 60]) {
    const layer = state.summary.layers[code];
    const row = document.createElement('label');
    row.className = 'layer-row'; row.dataset.code = code; row.title = layer.description;
    row.innerHTML = `<input type="checkbox" checked aria-label="${layer.name}"><canvas width="64" height="28" aria-hidden="true"></canvas><span>${layer.name}</span><span class="layer-count"></span>`;
    row.querySelector('input').addEventListener('change', event => {
      if (event.target.checked) state.enabled.add(code); else state.enabled.delete(code);
      redraw();
    });
    $('layer-list').append(row);
  }
  map.on('zoomend', updateLegend);
  map.on('click', event => identify(event).catch(error => showError(error.message)));
  map.on('mousemove', event => { $('cursor-position').textContent = `${event.latlng.lat.toFixed(4)}° N · ${event.latlng.lng.toFixed(4)}° E`; });
  $('toggle-all').addEventListener('click', () => {
    const enable = state.enabled.size === 0;
    state.enabled = new Set(enable ? Object.keys(state.summary.layers).map(Number) : []);
    document.querySelectorAll('.layer-row input').forEach(input => { input.checked = enable; });
    redraw();
  });
  for (const [id, explain] of [['quiet-mode', false], ['explain-mode', true]]) $(id).addEventListener('click', () => {
    state.explain = explain;
    $('quiet-mode').classList.toggle('selected', !explain); $('explain-mode').classList.toggle('selected', explain);
    $('quiet-mode').setAttribute('aria-pressed', String(!explain)); $('explain-mode').setAttribute('aria-pressed', String(explain));
    $('mode-description').textContent = explain ? 'Distinct colours help identify each layer. These colours are preview-only.' : 'The muted colours and line patterns stored in your map.';
    $('explain-badge').hidden = !explain; redraw();
  });
  $('night').addEventListener('change', event => { state.night = event.target.checked; document.body.classList.toggle('night', state.night); redraw(); });
  document.querySelectorAll('[data-place]').forEach(button => button.addEventListener('click', () => {
    map.setView(PLACES[button.dataset.place], 14, {animate: false});
    document.querySelectorAll('[data-place]').forEach(b => b.classList.toggle('active', b === button));
  }));
  places = L.layerGroup(Object.entries(PLACES).map(([id, ll]) => L.marker(ll, {interactive: false, keyboard: false,
    icon: L.divIcon({className: 'place-label', html: PLACE_NAMES[id], iconSize: [150, 18], iconAnchor: [0, 0]})})));
  $('places').addEventListener('change', event => { if (event.target.checked) places.addTo(map); else map.removeLayer(places); });
  const region = await fetch('region.geojson').then(r => { if (!r.ok) throw new Error('The extraction boundary is missing.'); return r.json(); });
  boundary = L.geoJSON(region, {style: {color: '#658fa9', weight: 1, dashArray: '5 6', fill: false}, interactive: false});
  $('boundary').addEventListener('change', event => { if (event.target.checked) boundary.addTo(map); else map.removeLayer(boundary); });
  $('full-area').addEventListener('click', () => { map.fitBounds(boundary.getBounds(), {padding: [40, 45], animate: false}); });
  $('device-frame').addEventListener('change', event => { $('screen-frame').hidden = !event.target.checked; });
  $('demo').addEventListener('change', async event => {
    if (event.target.checked) {
      try {
        if (!demoCourse) demoCourse = courseLayer([await fetch('demo-course.json').then(r => { if (!r.ok) throw new Error('The example overlay is missing.'); return r.json(); })]);
        demoCourse.addTo(map); fitCourse(demoCourse);
      } catch (error) { event.target.checked = false; showError(error.message); }
    } else if (demoCourse) map.removeLayer(demoCourse);
  });
  $('gpx-file').addEventListener('change', event => openGPX(event.target.files[0]));
  $('clear-course').addEventListener('click', () => {
    if (userCourse) map.removeLayer(userCourse); userCourse = null;
    $('gpx-file').value = ''; $('clear-course').hidden = true; $('course-status').textContent = 'Your GPX stays in this browser.';
    $('error').hidden = true;
  });
  updateLegend();
  document.body.dataset.ready = 'true';
}

init().catch(error => { showError(error.message); $('detail-status').textContent = 'Map could not be loaded'; });
