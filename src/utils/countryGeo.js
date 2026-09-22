import * as d3 from 'd3';
import * as topojson from 'topojson-client';
import { numericToAlpha3 } from './isoLookup';

// Countries whose d3.geoCentroid() is pulled far from their mainland
// by overseas territories — [longitude, latitude]
const CENTROID_OVERRIDES = {
  FRA: [2.35, 46.2],
  USA: [-98.0, 39.5],
  DNK: [10.0, 56.0],
  NOR: [15.5, 65.0],
  NLD: [5.3, 52.3],
  GBR: [-1.5, 52.5],
  PRT: [-8.2, 39.5],
  ESP: [-3.7, 40.4],
  RUS: [60.0, 61.0],
  AUS: [134.5, -25.5],
  CAN: [-96.0, 60.0],
  NZL: [172.5, -41.5],
};

// Parsed + geo-centroided once at module level (756KB TopoJSON) so every
// consumer (2D map, 3D globe) shares the same load instead of re-fetching.
let cache = null;
let inflight = null;

export function loadCountryGeo() {
  if (cache) return Promise.resolve(cache);
  if (inflight) return inflight;
  inflight = d3.json(`${import.meta.env.BASE_URL}data/countries-50m.json`).then((world) => {
    const geo = topojson.feature(world, world.objects.countries);
    const features = [];
    const lonLat = {};
    for (const feature of geo.features) {
      const numId = parseInt(feature.id, 10);
      const alpha3 = numericToAlpha3(numId);
      features.push({ numId, alpha3, feature });
      if (alpha3) {
        lonLat[alpha3] = CENTROID_OVERRIDES[alpha3] || d3.geoCentroid(feature);
      }
    }
    cache = { features, lonLat };
    return cache;
  });
  return inflight;
}

// Paints country polygons onto an equirectangular canvas for use as the 3D globe's
// baseTexture — this is what makes the globe a choropleth (countries filled by
// severity, like the 2D map) instead of a plain lit sphere. `fillForAlpha3(alpha3)`
// returns the fill color for one country; called synchronously per-render (not
// cached) since severity/selection/filters change what each country should show.
// `highlightAlpha3`, if given, gets the same bright/thick selection border the 2D
// map draws around the selected country — redrawn in a second pass so neighboring
// fills never cover it.
// 8192×4096 — the practical ceiling for a baked texture (the largest size virtually every
// WebGL-capable GPU from the last decade supports; beyond this risks failing on older
// hardware). The globe's baseTexture is a fixed-resolution raster, unlike the 2D map's
// vector SVG paths, so it will still blur past a certain zoom — GlobeView.jsx also caps
// how close the camera can get (viewControl.minDistance) to keep zoom inside a range this
// resolution can render crisply.
const TEXTURE_WIDTH = 8192;
const TEXTURE_HEIGHT = 4096;

export function renderCountryTexture(features, fillForAlpha3, highlightAlpha3) {
  const width = TEXTURE_WIDTH;
  const height = TEXTURE_HEIGHT;
  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext('2d');

  const projection = d3.geoEquirectangular().fitSize([width, height], { type: 'Sphere' });
  const path = d3.geoPath(projection, ctx);

  ctx.fillStyle = '#080c0e'; // ocean — matches --map-ocean
  ctx.fillRect(0, 0, width, height);

  ctx.strokeStyle = '#3d525c'; // coastline, brightened so it still reads once lit
  ctx.lineWidth = 1.5;
  for (const { alpha3, feature } of features) {
    ctx.fillStyle = (alpha3 && fillForAlpha3(alpha3)) || '#1b2328';
    ctx.beginPath();
    path(feature);
    ctx.fill();
    ctx.stroke();
  }

  if (highlightAlpha3) {
    const selected = features.find((f) => f.alpha3 === highlightAlpha3);
    if (selected) {
      ctx.strokeStyle = '#7fd1c4'; // matches WorldMap's selected-country stroke
      ctx.lineWidth = 4;
      ctx.beginPath();
      path(selected.feature);
      ctx.stroke();
    }
  }

  return canvas;
}
