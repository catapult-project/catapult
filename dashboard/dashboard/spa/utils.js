/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import {afterNextRender} from '@polymer/polymer/lib/utils/render-status.js';

let isDebugForTesting;
export function isDebug() {
  if (isDebugForTesting !== undefined) return isDebugForTesting;
  return window.location.hostname === 'localhost';
}
export function setDebugForTesting(d) {
  isDebugForTesting = d;
}

export const PRODUCTION_HOSTNAME = 'v2spa-dot-chromeperf.appspot.com';
let isProductionForTesting;
export function isProduction() {
  if (isProductionForTesting !== undefined) return isProductionForTesting;
  return window.location.hostname === PRODUCTION_HOSTNAME;
}
export function setProductionForTesting(d) {
  isProductionForTesting = d;
}

export function deepFreeze(o) {
  if (!o) return o;
  Object.freeze(o);
  for (const [name, value] of Object.entries(o)) {
    if (typeof(value) !== 'object') continue;
    if (Object.isFrozen(value)) continue;
    if (value.__proto__ !== Object.prototype &&
        value.__proto__ !== Array.prototype) {
      continue;
    }
    deepFreeze(value);
  }
}

export function isElementChildOf(el, potentialParent) {
  if (!el) return false;
  if (el === potentialParent) return false;
  while (el) {
    if (el === potentialParent) return true;
    if (el.parentNode) {
      el = el.parentNode;
    } else if (el.host) {
      el = el.host;
    } else {
      return false;
    }
  }
  return false;
}

export function getActiveElement() {
  let element = document.activeElement;
  while (element !== null && element.shadowRoot) {
    element = element.shadowRoot.activeElement;
  }
  return element;
}

export function afterRender() {
  return new Promise(resolve => afterNextRender({}, resolve));
}

export function timeout(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

export function animationFrame() {
  return new Promise(resolve => requestAnimationFrame(resolve));
}

export function idle() {
  new Promise(resolve => requestIdleCallback(resolve));
}

const DOCUMENT_READY = (async() => {
  while (document.readyState !== 'complete') {
    await animationFrame();
  }
})();

/*
  * Returns the bounding rect of the given element.
  */
export async function measureElement(element) {
  await DOCUMENT_READY;
  return element.getBoundingClientRect();
}

// measureText() below takes a string and optional style options, renders the
// text in this div, and returns the size of the text. This div helps
// measureText() render its arguments invisibly.
const MEASURE_TEXT_HOST = document.createElement('div');
MEASURE_TEXT_HOST.style.position = 'fixed';
MEASURE_TEXT_HOST.style.visibility = 'hidden';
MEASURE_TEXT_HOST.style.zIndex = -1000;
MEASURE_TEXT_HOST.readyPromise = (async() => {
  await DOCUMENT_READY;
  document.body.appendChild(MEASURE_TEXT_HOST);
})();

// Assuming the computed style of MEASURE_TEXT_HOST doesn't change, measuring
// a string with the same options should always return the same size, so the
// measurements can be memoized. Also, measuring text is asynchronous, so this
// cache can store promises in case callers try to measure the same text twice
// in the same frame.
const MEASURE_TEXT_CACHE = new Map();
const MAX_MEASURE_TEXT_CACHE_SIZE = 1000;

/*
  * Returns the bounding rect of the given textContent after applying the given
  * opt_options to a <span> containing textContent.
  */
export async function measureText(textContent, opt_options) {
  await MEASURE_TEXT_HOST.readyPromise;

  let cacheKey = {textContent, ...opt_options};
  cacheKey = JSON.stringify(cacheKey, Object.keys(cacheKey).sort());
  if (MEASURE_TEXT_CACHE.has(cacheKey)) {
    return await MEASURE_TEXT_CACHE.get(cacheKey);
  }

  const span = document.createElement('span');
  span.style.whiteSpace = 'nowrap';
  span.style.display = 'inline-block';
  span.textContent = textContent;
  Object.assign(span.style, opt_options);
  MEASURE_TEXT_HOST.appendChild(span);

  const promise = measureElement(span).then(({width, height}) => {
    return {width, height};
  });
  while (MEASURE_TEXT_CACHE.size > MAX_MEASURE_TEXT_CACHE_SIZE) {
    MEASURE_TEXT_CACHE.delete(MEASURE_TEXT_CACHE.keys().next().value);
  }
  MEASURE_TEXT_CACHE.set(cacheKey, promise);
  const rect = await promise;
  MEASURE_TEXT_CACHE.set(cacheKey, rect);
  MEASURE_TEXT_HOST.removeChild(span);
  return rect;
}

export function measureTrace() {
  const events = [];
  const loadTimes = Object.entries(performance.timing.toJSON()).filter(p =>
    p[1] > 0);
  loadTimes.sort((a, b) => a[1] - b[1]);
  const start = loadTimes.shift()[1];
  for (const [name, timeStamp] of loadTimes) {
    events.push({
      name: 'load:' + name,
      start,
      end: timeStamp,
      duration: timeStamp - start,
    });
  }
  for (const measure of performance.getEntriesByType('measure')) {
    const name = measure.name.replace(/[ \.]/g, ':').replace(
        ':reducers:', ':').replace(':actions:', ':');
    events.push({
      name,
      start: measure.startTime,
      duration: measure.duration,
      end: measure.startTime + measure.duration,
    });
  }
  return events;
}

export function measureHistograms() {
  const histograms = new tr.v.HistogramSet();
  const unit = tr.b.Unit.byName.timeDurationInMs_smallerIsBetter;
  for (const event of measureTrace()) {
    let hist = histograms.getHistogramNamed(event.name);
    if (!hist) {
      hist = histograms.createHistogram(event.name, unit, []);
    }
    hist.addSample(event.duration);
  }
  return histograms;
}

export function measureTable() {
  const table = [];
  for (const hist of measureHistograms()) {
    table.push([hist.average, hist.name]);
  }
  table.sort((a, b) => (b[0] - a[0]));
  return table.map(p =>
    parseInt(p[0]).toString().padEnd(6) + p[1]).join('\n');
}

export function normalize(columns, cells) {
  const dict = {};
  for (let i = 0; i < columns.length; ++i) {
    dict[columns[i]] = cells[i];
  }
  return dict;
}

export function denormalize(objects, columnNames) {
  return objects.map(obj => columnNames.map(col => obj[col]));
}

async function* asGenerator(promise) {
  yield await promise;
}

export const ZERO_WIDTH_SPACE = String.fromCharCode(0x200b);
export const NON_BREAKING_SPACE = String.fromCharCode(0xA0);

export function breakWords(str) {
  if (!str) return NON_BREAKING_SPACE;

  // Insert spaces before underscores.
  str = str.replace(/_/g, ZERO_WIDTH_SPACE + '_');

  // Insert spaces after colons and dots.
  str = str.replace(/\./g, '.' + ZERO_WIDTH_SPACE);
  str = str.replace(/:/g, ':' + ZERO_WIDTH_SPACE);

  // Insert spaces before camel-case words.
  str = str.split(/([a-z][A-Z])/g);
  str = str.map((s, i) => {
    if ((i % 2) === 0) return s;
    return s[0] + ZERO_WIDTH_SPACE + s[1];
  });
  str = str.join('');
  return str;
}

export function plural(count, pluralSuffix = 's', singularSuffix = '') {
  if (count === 1) return singularSuffix;
  return pluralSuffix;
}

/**
  * Compute a given number of colors by evenly spreading them around the
  * sinebow hue circle, or, if a Range of brightnesses is given, the hue x
  * brightness cylinder.
  *
  * @param {Number} numColors
  * @param {!Range} opt_options.brightnessRange
  * @param {Number} opt_options.brightnessPct
  * @param {Number} opt_options.hueOffset
  * @return {!Array.<!tr.b.Color>}
  */
export function generateColors(numColors, opt_options) {
  const options = opt_options || {};
  const brightnessRange = options.brightnessRange;
  const hueOffset = options.hueOffset || 0;
  const colors = [];
  if (numColors > 15 && brightnessRange) {
    // Evenly spread numColors around the surface of the hue x brightness
    // cylinder. Maximize distance between (huePct, brightnessPct) vectors.
    const numCycles = Math.round(numColors / 15);
    for (let i = 0; i < numCycles; ++i) {
      colors.push.apply(colors, generateColors(15, {
        brightnessPct: brightnessRange.lerp(i / (numCycles - 1)),
      }));
    }
  } else {
    // Evenly spread numColors throughout the sinebow hue circle.
    const brightnessPct = (options.brightnessPct === undefined) ? 0.5 :
      options.brightnessPct;
    for (let i = 0; i < numColors; ++i) {
      const huePct = hueOffset + (i / numColors);
      const [r, g, b] = tr.b.SinebowColorGenerator.sinebow(huePct);
      const rgba = tr.b.SinebowColorGenerator.calculateColor(
          r, g, b, 1, brightnessPct * 2);
      colors.push(tr.b.Color.fromString(rgba));
    }
  }
  return colors;
}

let nextGUID = 0;
export function simpleGUID() {
  return ++nextGUID;
}

export function* enumerate(iter) {
  let i = -1;
  for (const value of iter) {
    yield [++i, value];
  }
}

const IS_MAC = navigator.platform.startsWith('Mac');
export const CTRL_KEY_NAME = IS_MAC ? 'command' : 'Ctrl';

export function hasCtrlKey(event) {
  return IS_MAC ? event.metaKey : event.ctrlKey;
}

export function transformAlert(alert) {
  let deltaValue = alert.median_after_anomaly -
    alert.median_before_anomaly;
  const percentDeltaValue = deltaValue / alert.median_before_anomaly;

  let improvementDirection = tr.b.ImprovementDirection.BIGGER_IS_BETTER;
  if (alert.improvement === (deltaValue < 0)) {
    improvementDirection = tr.b.ImprovementDirection.SMALLER_IS_BETTER;
  }
  const unitSuffix = tr.b.Unit.nameSuffixForImprovementDirection(
      improvementDirection);

  let baseUnit = tr.b.Unit.byName[alert.units];
  if (!baseUnit ||
      baseUnit.improvementDirection !== improvementDirection) {
    let unitName = 'unitlessNumber';
    if (tr.b.Unit.byName[alert.units + unitSuffix]) {
      unitName = alert.units;
    } else {
      const info = tr.v.LEGACY_UNIT_INFO.get(alert.units);
      if (info) {
        unitName = info.name;
        deltaValue *= info.conversionFactor || 1;
      }
    }
    baseUnit = tr.b.Unit.byName[unitName + unitSuffix];
  }
  const [master, bot] = alert.descriptor.bot.split(':');

  return {
    baseUnit,
    bot,
    bugComponents: alert.bug_components,
    bugId: alert.bug_id === undefined ? '' : alert.bug_id,
    bugLabels: alert.bug_labels,
    deltaUnit: baseUnit.correspondingDeltaUnit,
    deltaValue,
    key: alert.key,
    improvement: alert.improvement,
    isSelected: false,
    master,
    measurement: alert.descriptor.measurement,
    statistic: alert.descriptor.statistic,
    percentDeltaUnit: tr.b.Unit.byName[
        'normalizedPercentageDelta' + unitSuffix],
    percentDeltaValue,
    startRevision: alert.start_revision,
    endRevision: alert.end_revision,
    case: alert.descriptor.testCase,
    suite: alert.descriptor.testSuite,
    v1ReportLink: alert.dashboard_link,
    pinpointJobs: alert.pinpoint_bisects,
  };
}

export function crbug(bugId) {
  return `http://crbug.com/${bugId}`;
}

export function pinpointJob(jobId) {
  return 'https://pinpoint-dot-chromeperf.appspot.com/job/' + jobId;
}
