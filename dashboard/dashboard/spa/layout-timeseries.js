/* Copyright 2019 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import {measureText} from './utils.js';

const HEIGHT_PX = 200;
const ESTIMATED_WIDTH_PX = 1000;

const ICON_WIDTH_PX = 24;
const TEXT_HEIGHT_PX = 15;

export const MODE = {
  CENTER: 'CENTER',
  DELTA: 'DELTA',
  NORMALIZE_LINE: 'NORMALIZE_LINE',
  NORMALIZE_UNIT: 'NORMALIZE_UNIT',
};

export function layoutTimeseries(state) {
  let rawXs;
  if (state.fixedXAxis) {
    rawXs = fixLinesXInPlace(state.lines);
  }

  // Extend xRange in both directions for chartLayout, not minimapLayout in
  // order to make room for icons.
  const xExtension = state.yAxis.generateTicks ? (
    ICON_WIDTH_PX / 2 / ESTIMATED_WIDTH_PX) : 0;

  // Extend yRange in both directions to prevent clipping yAxis.ticks.
  const yExtension = state.yAxis.generateTicks ? (
    TEXT_HEIGHT_PX / 2 / HEIGHT_PX) : 0;

  const {xRange, yRangeForUnitName} = normalizeLinesInPlace(
      state.lines, {
        mode: state.mode,
        zeroYAxis: state.zeroYAxis,
        xExtension,
        yExtension,
      });

  state = {
    ...state,
    xAxis: {
      ...state.xAxis,
      range: getRevisionRange(state.lines, 0),
    },
    yAxis: {
      ...state.yAxis,
      rangeForUnitName: yRangeForUnitName,
    }
  };

  if (state.xAxis.generateTicks) {
    const ticks = computeXTicks(state.xAxis.range, xRange, rawXs);
    state = {...state, xAxis: {...state.xAxis, ticks}};
  }

  if (state.yAxis.generateTicks) {
    state = generateYTicksReducer(state, yRangeForUnitName, yExtension);
  }

  return state;
}

function fixLinesXInPlace(lines) {
  let rawXs = new Set();
  for (const line of lines) {
    for (const datum of line.data) {
      rawXs.add(datum.x);
    }
  }
  rawXs = Array.from(rawXs);
  rawXs.sort((x, y) => x - y);
  for (const line of lines) {
    for (const datum of line.data) {
      datum.xFixed = rawXs.indexOf(datum.x);
    }
  }
  return rawXs;
}

function getX(datum) {
  return (datum.xFixed !== undefined) ? datum.xFixed : datum.x;
}

const EPOCH_MS = new Date(2010, 0, 1).getTime();
const EPOCH_S = EPOCH_MS / 1000;

function revisionRangeAsDates(revisionRange, displayRange, rawXs) {
  const nowMs = new Date().getTime();
  if (revisionRange.min > EPOCH_MS && revisionRange.max < nowMs) {
    return {
      dateRange: {
        min: new Date(revisionRange.min),
        max: new Date(revisionRange.max),
      },
      displayMs: displayRange,
      rawMs: rawXs,
    };
  }

  const nowS = nowMs / 1000;
  if (revisionRange.min > EPOCH_S && revisionRange.max < nowS) {
    return {
      dateRange: {
        min: new Date(revisionRange.min * 1000),
        max: new Date(revisionRange.max * 1000),
      },
      displayMs: tr.b.math.Range.fromExplicitRange(
          displayRange.min * 1000,
          displayRange.max * 1000),
      rawMs: rawXs ? rawXs.map(x => x * 1000) : undefined,
    };
  }

  return {};
}

function getXPct(pct) {
  return tr.b.math.truncate(pct * 100, 1) + '%';
}

function computeXTicks(revisionRange, displayRange, rawXs) {
  // Timestamps can be in either seconds or milliseconds.
  const {dateRange, displayMs, rawMs} = revisionRangeAsDates(
      revisionRange, displayRange, rawXs);
  if (dateRange) {
    return calendarTicks(dateRange, displayMs, rawMs);
  }

  let formatTick;
  if (rawXs) {
    // fixedXAxis
    formatTick = text => {
      const x = tr.b.findLowIndexInSortedArray(rawXs, x => x, text);
      return {text, xPct: getXPct(displayRange.normalize(x))};
    };
  } else {
    formatTick = text => {
      return {text, xPct: getXPct(displayRange.normalize(text))};
    };
  }

  return computeTicks(revisionRange).map(formatTick);
}

let CHAR_SIZE_PX;

layoutTimeseries.isReady = false;
layoutTimeseries.readyPromise = (async() => {
  CHAR_SIZE_PX = await measureText('0');
  layoutTimeseries.isReady = true;
})();

function calendarTick(ms, text, xPct, anchor) {
  const width = Math.ceil(CHAR_SIZE_PX.width * text.length);
  let px = Math.round(ESTIMATED_WIDTH_PX * xPct);
  if (anchor === 'start') {
    px = tr.b.math.Range.fromExplicitRange(px, px + width);
  } else if (anchor === 'end') {
    px = tr.b.math.Range.fromExplicitRange(px - width, px);
  } else {
    const hw = Math.ceil(width / 2);
    px = tr.b.math.Range.fromExplicitRange(px - hw, px + hw);
  }
  return {ms, text, xPct: getXPct(xPct), anchor, px};
}

function formatEndDate(range) {
  let text = tr.b.formatDate(range.max);

  // strip year if same as start
  if (range.max.getFullYear() === range.min.getFullYear()) {
    text = text.slice(5);
    // strip month and date if same as start
    if (range.max.getMonth() === range.min.getMonth() &&
        range.max.getDate() === range.min.getDate()) {
      text = text.slice(6);
    }
  }
  return text;
}

function daysInMonth(y, m) {
  return new Date(y, m + 1, 0).getDate();
}

function calendarTickFromDate(date, text, displayRange, rawMs) {
  const ms = date.getTime();
  let x = ms;
  if (rawMs) {
    x = tr.b.findLowIndexInSortedArray(rawMs, x => x, x);
    if (ms < rawMs[x]) ++x;
  }
  const xPct = displayRange.normalize(x);
  return calendarTick(ms, text, xPct);
}

function generateMonths(
    ticks, year, minMonth, maxMonth, displayRange, rawMs) {
  for (let month = minMonth; month <= maxMonth; ++month) {
    const date = new Date(year, month, 1);
    const text = date.toLocaleString(navigator.language, {month: 'short'});
    const tick = calendarTickFromDate(date, text, displayRange, rawMs);
    if (maybeInsertTick(ticks, tick)) {
      generateDates(ticks, year, month - 1, 1, daysInMonth(year, month),
          displayRange, rawMs);
    }
  }
}

function generateDates(
    ticks, year, month, minDate, maxDate, displayRange, rawMs) {
  for (let day = minDate; day <= maxDate; ++day) {
    const date = new Date(year, month, day);
    const text = day.toString();
    const ms = date.getTime();
    const tick = calendarTickFromDate(date, text, displayRange, rawMs);
    if (maybeInsertTick(ticks, tick) && (day < maxDate)) {
      generateHours(ticks, year, month, day, 1, 60, displayRange, rawMs);
    }
  }
}

function generateHours(
    ticks, year, month, date, minHour, maxHour, displayRange, rawMs) {
}

function generateMinutes(ticks, year, month, date, hour, minMinutes,
    maxMinutes, displayRange, rawMs) {
}

function maybeInsertTick(ticks, tick) {
  // If tick does not overlap any ticks, then insert it and return true.
  const index = tr.b.findLowIndexInSortedArray(ticks, t => t.ms, tick.ms);

  if (tick.px.max < 0) return false;
  if (tick.px.min >= ESTIMATED_WIDTH_PX) return false;

  if (ticks[index] && tick.px.intersectsRangeExclusive(ticks[index].px)) {
    return false;
  }

  if (ticks[index - 1] &&
      tick.px.intersectsRangeExclusive(ticks[index - 1].px)) {
    return false;
  }

  if (ticks[index + 1] &&
      tick.px.intersectsRangeExclusive(ticks[index + 1].px)) {
    return false;
  }

  ticks.splice(index, 0, tick);
  return true;
}

function calendarTicks(dates, displayRange, rawMs) {
  // Always start with the full date of dates.min and end with dates.max.
  const ticks = [
    calendarTick(
        dates.min.getTime(),
        tr.b.formatDate(dates.min),
        displayRange.normalize(rawMs ? 0 : dates.min),
        'start'),
    calendarTick(
        dates.max.getTime(),
        formatEndDate(dates),
        displayRange.normalize(rawMs ? rawMs.length - 1 : dates.max),
        'end'),
  ];

  if (dates.max.getFullYear() !== dates.min.getFullYear()) {
    generateMonths(ticks, dates.min.getFullYear(),
        dates.min.getMonth() + 1, 11, displayRange, rawMs);
    for (let y = 1 + dates.min.getFullYear(); y <= dates.max.getFullYear();
      ++y) {
      const date = new Date(y, 0, 1);
      const text = y.toString();
      const tick = calendarTickFromDate(date, text, displayRange, rawMs);
      if (maybeInsertTick(ticks, tick) && (y < dates.max.getFullYear())) {
        generateMonths(ticks, dates.max.getFullYear(), 2, 11,
            displayRange, rawMs);
      }
    }
    generateMonths(ticks, dates.max.getFullYear(),
        2, dates.max.getMonth() + 1, displayRange, rawMs);
  } else if (dates.max.getMonth() !== dates.min.getMonth()) {
    generateMonths(ticks, dates.min.getFullYear(),
        dates.min.getMonth(), dates.max.getMonth(), displayRange, rawMs);
  } else if (dates.max.getDate() !== dates.min.getDate()) {
    generateDates(ticks, dates.min.getFullYear(),
        dates.min.getMonth(), dates.min.getDate(), dates.max.getDate(),
        displayRange, rawMs);
  } else if (dates.max.getHour() !== dates.min.getHour()) {
    generateHours(ticks, dates.min.getFullYear(),
        dates.min.getMonth(), dates.min.getDate(), dates.min.getHour(),
        dates.max.getHour(), displayRange, rawMs);
  } else if (dates.max.getMinutes() !== dates.min.getMinutes()) {
    generateMinutes(ticks, dates.min.getFullYear(),
        dates.min.getMonth(), dates.min.getDate(), dates.min.getHour(),
        dates.min.getMinutes(), dates.max.getMinutes(), displayRange, rawMs);
  }

  return ticks;
}

function getRevisionRange(lines, extension) {
  const range = new tr.b.math.Range();
  for (const line of lines) {
    if (line.data.length === 0) continue;
    range.addValue(line.data[0].x);
    range.addValue(line.data[line.data.length - 1].x);
  }
  range.min -= range.range * extension;
  range.max += range.range * extension;
  return range;
}

function normalizeLinesInPlace(lines, opt_options) {
  const options = opt_options || {};
  const mode = options.mode || MODE.NORMALIZE_UNIT;
  const zeroYAxis = options.zeroYAxis || false;
  const yExtension = options.yExtension || 0;
  const xExtension = options.xExtension || 0;

  const xRange = new tr.b.math.Range();
  const yRangeForUnitName = new Map();
  let maxLineLength = 0;
  const maxLineRangeForUnitName = new Map();
  for (const line of lines) {
    maxLineLength = Math.max(maxLineLength, line.data.length);
    line.yRange = new tr.b.math.Range();
    if (zeroYAxis) line.yRange.addValue(0);

    for (const datum of line.data) {
      const x = getX(datum);
      if (typeof(x) === 'number') xRange.addValue(x);
      if (typeof(datum.y) === 'number') line.yRange.addValue(datum.y);
    }

    // normalize count_biggerIsBetter together with count_smallerIsBetter for
    // pinpoint.success, for example.
    const unitName = line.unit.baseUnit.unitName;

    if (!yRangeForUnitName.has(unitName)) {
      yRangeForUnitName.set(unitName, new tr.b.math.Range());
    }

    line.yRange.min -= line.yRange.range * yExtension;
    line.yRange.max += line.yRange.range * yExtension;

    yRangeForUnitName.get(unitName).addRange(line.yRange);

    if (line.yRange.range > (maxLineRangeForUnitName.get(
        unitName) || 0)) {
      maxLineRangeForUnitName.set(unitName, line.yRange.range);
    }
  }

  if (mode === MODE.CENTER) {
    for (const line of lines) {
      const halfMaxLineRange = maxLineRangeForUnitName.get(
          line.unit.baseUnit.unitName) / 2;
      // Extend line.yRange to be as large as the largest range.
      line.yRange = tr.b.math.Range.fromExplicitRange(
          line.yRange.center - halfMaxLineRange,
          line.yRange.center + halfMaxLineRange);
    }
  }

  xRange.min -= xRange.range * xExtension;
  xRange.max += xRange.range * xExtension;

  // Round to tenth of a percent.
  const round = x => tr.b.math.truncate(x * 100, 1);

  const isNormalizeLine = (
    mode === MODE.NORMALIZE_LINE || mode === MODE.CENTER);
  for (const line of lines) {
    line.path = '';
    line.shadePoints = '';
    const yRange = isNormalizeLine ? line.yRange :
      yRangeForUnitName.get(line.unit.baseUnit.unitName);
    for (const datum of line.data) {
      datum.xPct = round(xRange.normalize(getX(datum)));
      // Y coordinates increase downwards.
      datum.yPct = round(1 - yRange.normalize(datum.y));
      if (isNaN(datum.xPct)) datum.xPct = 50;
      if (isNaN(datum.yPct)) datum.yPct = 50;
      const command = line.path ? ' L' : 'M';
      line.path += command + datum.xPct + ',' + datum.yPct;
      if (datum.shadeRange) {
        const shadeMax = round(1 - yRange.normalize(datum.shadeRange.max));
        line.shadePoints += ' ' + datum.xPct + ',' + shadeMax;
      }
    }
    for (let i = line.data.length - 1; i >= 0; --i) {
      const datum = line.data[i];
      if (datum.shadeRange) {
        const shadeMin = round(1 - yRange.normalize(datum.shadeRange.min));
        line.shadePoints += ' ' + datum.xPct + ',' + shadeMin;
      }
    }
  }
  return {xRange, yRangeForUnitName};
}

function generateYTicksReducer(state, yRangeForUnitName, yExtension) {
  let yAxis = state.yAxis;
  let ticks = [];
  if (state.mode === MODE.NORMALIZE_LINE || state.mode === MODE.CENTER) {
    for (const line of state.lines) {
      line.ticks = generateYTicks(line.yRange, line.unit, yExtension);
    }
    if (state.lines.length === 1) {
      ticks = state.lines[0].ticks;
    }
  } else {
    const ticksForUnitName = new Map();
    for (const [unitName, range] of yRangeForUnitName) {
      const unit = tr.b.Unit.byName[unitName];
      const ticks = generateYTicks(range, unit, yExtension);
      ticksForUnitName.set(unitName, ticks);
    }
    yAxis = {...yAxis, ticksForUnitName};
    if (ticksForUnitName.size === 1) {
      ticks = [...ticksForUnitName.values()][0];
    }
  }
  yAxis = {...yAxis, ticks};
  return {...state, yAxis};
}

function generateYTicks(displayRange, unit, yExtension) {
  const dataRange = tr.b.math.Range.fromExplicitRange(
      displayRange.min + (displayRange.range * yExtension),
      displayRange.max - (displayRange.range * yExtension));
  return computeTicks(dataRange).map(y => {
    return {
      text: unit.format(y),
      yPct: tr.b.math.truncate(
          100 * (1 - displayRange.normalize(y)), 1) + '%',
    };
  });
}

export function computeTicks(range, numTicks = 5) {
  const ticks = [];

  let tickPower = tr.b.math.lesserPower(range.range);
  if ((range.range / tickPower) < numTicks) tickPower /= 10;

  // Bump min up (and max down) to the next multiple of tickPower.
  const rounded = tr.b.math.Range.fromExplicitRange(
      range.min + tickPower - (range.min % tickPower),
      range.max - (range.max % tickPower));

  const delta = rounded.range / (numTicks - 1);
  if (range.min < 0 && range.max > 0) {
    for (let tick = 0; tick <= range.max; tick += delta) {
      ticks.push(tick);
    }
    for (let tick = -delta; tick >= range.min; tick -= delta) {
      ticks.unshift(tick);
    }
  } else {
    for (let tick = rounded.min; tick <= range.max; tick += delta) {
      ticks.push(tick);
    }
  }

  return ticks;
}
