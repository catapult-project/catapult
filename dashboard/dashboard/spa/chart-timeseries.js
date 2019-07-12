/* Copyright 2019 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import './place-holder.js';
import {BatchIterator} from '@chopsui/batch-iterator';
import {CHAIN, UPDATE} from './simple-redux.js';
import {CTRL_KEY_NAME, generateColors, measureText} from './utils.js';
import {ChartBase} from './chart-base.js';
import {ChartFetcher} from './chart-fetcher.js';
import {ElementBase, STORE} from './element-base.js';
import {LEVEL_OF_DETAIL, TimeseriesRequest} from './timeseries-request.js';
import {MODE, layoutTimeseries} from './layout-timeseries.js';
import {TimeseriesMerger} from './timeseries-merger.js';
import {get} from 'dot-prop-immutable';
import {html, css} from 'lit-element';

const SHADE_FILL_ALPHA = 0.2;

export class ChartTimeseries extends ElementBase {
  static get is() { return 'chart-timeseries'; }

  static get properties() {
    return {
      ...ChartBase.properties,
      placeholderHeight: String,
      errors: Array,
      lines: Array,
      lineDescriptors: Array,
      minRevision: Number,
      maxRevision: Number,
      brushRevisions: Array,
      isLoading: Boolean,
      zeroYAxis: Boolean,
      fixedXAxis: Boolean,
      mode: String,
      levelOfDetail: String,
    };
  }

  static buildState(options = {}) {
    const state = ChartBase.buildState(options);
    state.yAxis = {
      generateTicks: options.generateYTicks !== false,
      ...state.yAxis,
    };
    state.xAxis = {
      generateTicks: options.generateXTicks !== false,
      ...state.xAxis,
    };
    return {
      ...state,
      errors: new Set(),
      lineDescriptors: [],
      minRevision: undefined,
      maxRevision: undefined,
      brushRevisions: [],
      isLoading: false,
      zeroYAxis: false,
      fixedXAxis: false,
      mode: MODE.NORMALIZE_UNIT,
      levelOfDetail: options.levelOfDetail || LEVEL_OF_DETAIL.XY,
    };
  }

  static get styles() {
    return css`
      :host {
        display: block;
      }
    `;
  }

  render() {
    return (this.isLoading || (this.lines || []).length) ? html`
      <chart-base
          .statePath="${this.statePath}"
          @get-tooltip="${this.onGetTooltip_}"
          @mouse-leave-main="${this.onMouseLeaveMain_}">
      </chart-base>
    ` : html`
      <place-holder style="height: ${this.placeholderHeight};">
        <slot></slot>
      </place-holder>
    `;
  }

  stateChanged(rootState) {
    if (!this.statePath) return;

    const oldLineCount = this.lines ? this.lines.length : 0;
    const oldLineDescriptors = this.lineDescriptors;
    const oldMode = this.mode;
    const oldFixedXAxis = this.fixedXAxis;
    const oldZeroYAxis = this.zeroYAxis;
    const oldMinRevision = this.minRevision;
    const oldMaxRevision = this.maxRevision;

    Object.assign(this, get(rootState, this.statePath));

    const newLineCount = this.lines ? this.lines.length : 0;
    if (newLineCount !== oldLineCount) {
      this.dispatchEvent(new CustomEvent('line-count-change', {
        bubbles: true,
        composed: true,
      }));
    }

    if (this.lineDescriptors !== oldLineDescriptors ||
        this.mode !== oldMode ||
        this.fixedXAxis !== oldFixedXAxis ||
        this.zeroYAxis !== oldZeroYAxis ||
        this.minRevision !== oldMinRevision ||
        this.maxRevision !== oldMaxRevision) {
      this.debounce('load', () => {
        ChartTimeseries.load(this.statePath);
      });
    }
  }

  showPlaceholder(isLoading, lines) {
    return !isLoading && !lines.length;
  }

  onGetTooltip_(event) {
    // Warning: If this does not dispatch synchronously, then it is
    // possible for the tooltip to get stuck if hideTooltip is dispatched
    // while awaiting here.
    const mainRect = event.detail.mainRect;
    const line = event.detail.nearestLine;
    const lineIndex = this.lines.indexOf(event.detail.nearestLine);
    const datum = event.detail.nearestPoint;
    STORE.dispatch(CHAIN(
        {
          type: ChartTimeseries.reducers.getTooltip.name,
          statePath: this.statePath,
          mainRect,
          line,
          datum,
        },
        {
          type: ChartTimeseries.reducers.mouseYTicks.name,
          statePath: this.statePath,
          line,
        },
        {
          type: ChartBase.reducers.boldLine.name,
          statePath: this.statePath,
          lineIndex,
        }));
  }

  async onMouseLeaveMain_(event) {
    STORE.dispatch(CHAIN(
        UPDATE(this.statePath, {tooltip: undefined}),
        {
          type: ChartTimeseries.reducers.mouseYTicks.name,
          statePath: this.statePath,
        },
        {
          type: ChartBase.reducers.boldLine.name,
          statePath: this.statePath,
        }));
  }

  static async load(statePath) {
    let state = get(STORE.getState(), statePath);
    if (!state) return;

    STORE.dispatch(UPDATE(statePath, {
      isLoading: true,
      lines: [],
      errors: new Set(),
    }));

    await ChartTimeseries.loadLines(statePath);

    state = get(STORE.getState(), statePath);
    if (!state) {
      // User closed the chart before it could finish loading
      return;
    }

    STORE.dispatch(UPDATE(statePath, {isLoading: false}));
  }

  static async loadLines(statePath) {
    METRICS.startLoadChart();
    const started = performance.now();
    STORE.dispatch(UPDATE(statePath, {started}));
    const state = get(STORE.getState(), statePath);
    const fetcher = new ChartFetcher(
        state.lineDescriptors.slice(0, ChartTimeseries.MAX_LINES),
        {minRevision: state.minRevision, maxRevision: state.maxRevision},
        state.levelOfDetail);
    for await (const {timeseriesesByLine, errors} of fetcher) {
      if (!layoutTimeseries.isReady) await layoutTimeseries.readyPromise;

      const state = get(STORE.getState(), statePath);
      if (!state || state.started !== started) {
        // This chart is no longer in the redux store, or another load has
        // superseded this load.
        return;
      }

      STORE.dispatch({
        type: ChartTimeseries.reducers.layout.name,
        timeseriesesByLine,
        errors,
        statePath,
      });
      ChartTimeseries.measureYTicks(statePath);
      if (timeseriesesByLine.length) METRICS.endLoadChart();
    }
  }

  // Measure the yAxis tick labels on the screen and size the yAxis region
  // appropriately. Measuring elements is asynchronous, so this logic needs to
  // be an action creator.
  static async measureYTicks(statePath) {
    const ticks = ChartTimeseries.collectYAxisTicks(
        get(STORE.getState(), statePath));
    if (ticks.length === 0) return;
    STORE.dispatch({
      type: ChartTimeseries.reducers.yAxisWidth.name,
      statePath,
      rects: await Promise.all(ticks.map(tick => measureText(tick))),
    });
  }

  // Set line.color.
  static assignColors(lines) {
    const isTestLine = line => line.descriptor.buildType !== 'ref';
    const testLines = lines.filter(isTestLine);
    const colors = generateColors(testLines.length, {hueOffset: 0.64});
    const colorByDescriptor = new Map();
    for (const line of testLines) {
      const color = colors.shift();
      colorByDescriptor.set(ChartTimeseries.stringifyDescriptor(
          {...line.descriptor, buildType: undefined}), color);
      line.color = color.toString();
      line.shadeFill = color.withAlpha(SHADE_FILL_ALPHA).toString();
    }
    for (const line of lines) {
      if (isTestLine(line)) continue;
      if (lines.length === (1 + testLines.length)) {
        // There's only a single ref build line, so make it black for visual
        // simplicity. Chart-legend entries that aren't selected are grey, and
        // x-axis lines are grey, so disambiguate by avoiding grey here.
        line.color = 'rgba(0, 0, 0, 1)';
        line.shadeFill = `rgba(0, 0, 0, ${SHADE_FILL_ALPHA})`;
        break;
      }
      const color = colorByDescriptor.get(ChartTimeseries.stringifyDescriptor(
          {...line.descriptor, buildType: undefined}));
      if (color) {
        const hsl = color.toHSL();
        const adjusted = tr.b.Color.fromHSL({
          h: hsl.h,
          s: 1,
          l: 0.9,
        });
        line.color = adjusted.toString();
        line.shadeFill = adjusted.withAlpha(SHADE_FILL_ALPHA).toString();
      } else {
        line.color = 'white';
        line.shadeFill = 'white';
      }
    }
  }

  static aggregateTimeserieses(
      lineDescriptor, timeserieses, levelOfDetail, range) {
    const isXY = (levelOfDetail === LEVEL_OF_DETAIL.XY);
    const lineData = [];
    const iter = new TimeseriesMerger(timeserieses, range);
    for (const [x, datum] of iter) {
      const icon = isXY ? {} : ChartTimeseries.getIcon(datum);
      lineData.push({
        datum, x, y: datum[lineDescriptor.statistic || 'avg'], ...icon,
      });
    }

    lineData.sort((a, b) => a.x - b.x);
    return lineData;
  }

  static revisionRanges(brushRevisions) {
    const revisionRanges = [];
    for (let i = 0; i < brushRevisions.length; i += 2) {
      revisionRanges.push(tr.b.math.Range.fromExplicitRange(
          brushRevisions[i], brushRevisions[i + 1]));
    }
    return revisionRanges;
  }

  static revisionLink(revisionInfo, rName, r1, r2) {
    if (!revisionInfo) return {name: rName};
    const info = revisionInfo[rName];
    if (!info) return {name: rName};
    const url = info.url.replace('{{R1}}', r1 || r2).replace('{{R2}}', r2);
    return {name: info.name, url};
  }

  static brushRevisions(state) {
    const brushes = state.brushRevisions.map(x => {
      const xPctRange = tr.b.math.Range.fromExplicitRange(0, 100);
      for (const line of state.lines) {
        const index = tr.b.findLowIndexInSortedArray(
            line.data, d => d.x, x);
        if (!line.data[index]) continue;
        // Now, line.data[index].x >= x

        const thisMax = line.data[index].xPct;
        const thisMin = (index > 0) ? line.data[index - 1].xPct : thisMax;

        if (thisMax === x) return {x, xPct: line.data[index].xPct + '%'};

        xPctRange.min = Math.max(xPctRange.min, thisMin);
        xPctRange.max = Math.min(xPctRange.max, thisMax);
      }
      if (xPctRange.isEmpty) return {x: 0, xPct: '0%'};
      return {x, xPct: xPctRange.center + '%'};
    });
    return {...state, xAxis: {...state.xAxis, brushes}};
  }

  // Strip out min/maxRevision/Timestamp and ensure a consistent key order.
  static stringifyDescriptor(lineDescriptor) {
    return JSON.stringify([
      lineDescriptor.suites,
      lineDescriptor.measurement,
      lineDescriptor.bots,
      lineDescriptor.cases,
      lineDescriptor.statistic,
      lineDescriptor.buildType,
    ]);
  }

  // If an icon should be displayed in a main chart for this datum, return
  // {icon, iconColor}.
  static getIcon(datum) {
    // See ./cp-icon.js for available icons.

    if (datum.alert) {
      if (datum.alert.improvement) {
        // Improvement alerts display thumbup icons.
        return {
          icon: 'thumbup',
          iconColor: 'var(--improvement-color, green)',
        };
      }

      // Regression alerts display error icons.
      return {
        icon: 'error',
        iconColor: datum.alert.bugId ?
          'var(--neutral-color-dark, grey)' : 'var(--error-color, red)',
      };
    }

    if (datum.diagnostics &&
        datum.diagnostics.has(tr.v.d.RESERVED_NAMES.OS_VERSIONS)) {
      // Whitelisted diagnostics display feedback icons.
      return {
        icon: 'feedback',
        iconColor: 'var(--primary-color-dark, blue)',
      };
    }

    return {};
  }

  static collectYAxisTicks(state) {
    const ticks = new Set();
    if (state.yAxis.ticksForUnitName) {
      for (const unitTicks of state.yAxis.ticksForUnitName.values()) {
        for (const tick of unitTicks) {
          ticks.add(tick.text);
        }
      }
    }
    for (const line of state.lines) {
      if (!line.ticks) continue;
      for (const tick of line.ticks) {
        ticks.add(tick.text);
      }
    }
    return [...ticks];
  }
}

ChartTimeseries.MAX_LINES = 10;

ChartTimeseries.reducers = {
  // Aggregate timeserieses, assign colors, layout chart data, snap revisions.
  layout: (state, {timeseriesesByLine, errors}, rootState) => {
    errors = errors.map(e => e.message);
    errors = new Set([...state.errors, ...errors]);
    state = {...state, errors};

    const lines = [];
    for (const {lineDescriptor, timeserieses} of timeseriesesByLine) {
      const data = ChartTimeseries.aggregateTimeserieses(
          lineDescriptor, timeserieses, state.levelOfDetail, {
            minRevision: state.minRevision,
            maxRevision: state.maxRevision,
          });
      if (data.length === 0) continue;

      let unit = timeserieses[0][0].unit;
      if (lineDescriptor.statistic === 'count' ||
          lineDescriptor.statistic === 'nans') {
        // See tr.v.Histogram.getStatisticScalar().
        unit = tr.b.Unit.byName.count;
      }
      if (state.mode === MODE.DELTA) {
        unit = unit.correspondingDeltaUnit;
        const offset = data[0].y;
        for (const datum of data) datum.y -= offset;
      }

      lines.push({descriptor: lineDescriptor, unit, data, strokeWidth: 1});
    }

    state = {...state, lines};
    ChartTimeseries.assignColors(state.lines);
    state = layoutTimeseries(state);
    state = ChartTimeseries.brushRevisions(state);
    return state;
  },

  // Size the yAxis region according to max tick width.
  yAxisWidth: (state, {rects}, rootState) => {
    const width = tr.b.math.Statistics.max(rects, rect => rect.width);
    return {...state, yAxis: {...state.yAxis, width}};
  },

  // Depending on mode and lines, there may be multiple y-axes. When the user
  // hovers near a line, the y-axis for that line is displayed via
  // state.yAxis.ticks.
  mouseYTicks: (state, {line}, rootState) => {
    if (!state || !state.yAxis || !state.yAxis.generateTicks) return state;
    const isNormalizeLine = (
      state.mode === MODE.NORMALIZE_LINE || state.mode === MODE.CENTER);
    if (!isNormalizeLine && state.yAxis && state.yAxis.ticksForUnitName &&
        (state.yAxis.ticksForUnitName.size === 1)) {
      return state;
    }
    let ticks = [];
    if (line) {
      if (isNormalizeLine) {
        ticks = line.ticks;
      } else {
        ticks = state.yAxis.ticksForUnitName.get(
            line.unit.baseUnit.unitName);
      }
    }
    return {...state, yAxis: {...state.yAxis, ticks}};
  },

  // When the user hovers near a data point, display a table containing
  // information about the data point.
  getTooltip: (state, {mainRect, line, datum}, rootState) => {
    if (!line || !datum) {
      return {...state, tooltip: null};
    }

    const rows = [];

    if (state.brushRevisions.length === 0) {
      rows.push({
        colspan: 2, color: 'var(--primary-color-dark, blue)',
        name: 'Click for details'
      });
    } else {
      let isBrushed = false;
      for (const range of ChartTimeseries.revisionRanges(
          state.brushRevisions)) {
        isBrushed = range.min < datum.x && datum.x < range.max;
        if (isBrushed) break;
      }
      if (isBrushed) {
        rows.push({
          colspan: 2, color: 'var(--primary-color-dark, blue)',
          name: 'Click to reset details'
        });
      } else {
        rows.push({
          colspan: 2, color: 'var(--primary-color-dark, blue)',
          name: CTRL_KEY_NAME + '+click to compare details'
        });
      }
    }

    if (datum.icon === 'clock') {
      const days = Math.floor(tr.b.convertUnit(
          new Date() - datum.datum.timestamp,
          tr.b.UnitScale.TIME.MILLI_SEC, tr.b.UnitScale.TIME.DAY));
      rows.push({
        colspan: 2, color: datum.iconColor,
        name: `No data uploaded in ${days} day${days === 1 ? '' : 's'}`,
      });
    }

    if (datum.datum.alert) {
      if (datum.datum.alert.bugId) {
        rows.push({name: 'bug', value: datum.datum.alert.bugId});
      }
      const deltaScalar = datum.datum.alert.deltaUnit.format(
          datum.datum.alert.deltaValue);
      const percentDeltaScalar = datum.datum.alert.percentDeltaUnit.format(
          datum.datum.alert.percentDeltaValue);
      rows.push({
        name: datum.datum.alert.improvement ? 'improvement' : 'regression',
        color: datum.iconColor,
        value: deltaScalar + ' ' + percentDeltaScalar,
      });
    }

    const value = (typeof(datum.y) === 'number') ? line.unit.format(datum.y) :
      ('' + datum.y);
    rows.push({name: 'value', value});

    let foundRevision = false;
    for (const [rName, value] of Object.entries(
        datum.datum.revisions || {})) {
      const {name} = ChartTimeseries.revisionLink(
          rootState.revisionInfo, rName);
      rows.push({name, value});

      if (!foundRevision) {
        foundRevision = (parseInt(datum.datum.revision) === value);
      }
    }
    if (!foundRevision) {
      rows.push({name: 'revision', value: datum.datum.revision});
    }

    if (datum.datum.timestamp) {
      rows.push({
        name: 'Upload timestamp',
        value: tr.b.formatDate(datum.datum.timestamp),
      });
    }

    rows.push({name: 'build type', value: line.descriptor.buildType});

    if (line.descriptor.suites.length === 1) {
      rows.push({
        name: 'test suite',
        value: line.descriptor.suites[0],
      });
    }

    rows.push({name: 'measurement', value: line.descriptor.measurement});

    if (line.descriptor.bots.length === 1) {
      rows.push({name: 'bot', value: line.descriptor.bots[0]});
    }

    if (line.descriptor.cases.length === 1) {
      rows.push({
        name: 'test case',
        value: line.descriptor.cases[0],
      });
    }

    if (datum.datum.diagnostics) {
      const value = [...datum.datum.diagnostics.keys()].join(', ');
      rows.push({
        name: 'changed',
        value,
        color: 'var(--primary-color-dark, blue)',
      });
    }

    state = {
      ...state,
      tooltip: {
        color: line.color,
        isVisible: true,
        rows,
      },
    };
    if (datum.xPct < 50) {
      state.tooltip.left = datum.xPct + '%';
    } else {
      state.tooltip.right = (100 - datum.xPct) + '%';
    }
    if (mainRect.top > (window.innerHeight - mainRect.bottom)) {
      // More space above chart than below.
      state.tooltip.bottom = '100%';
    } else {
      // More space below chart than above.
      state.tooltip.top = '100%';
    }

    return state;
  },
};

ElementBase.register(ChartTimeseries);
