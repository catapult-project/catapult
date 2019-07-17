/* Copyright 2019 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import './cp-flex.js';
import './cp-icon.js';
import './error-set.js';
import '@chopsui/chops-radio';
import '@chopsui/chops-radio-group';
import '@chopsui/chops-switch';
import * as PolymerAsync from '@polymer/polymer/lib/utils/async.js';
import {BatchIterator} from '@chopsui/batch-iterator';
import {CHAIN, TOGGLE, UPDATE} from './simple-redux.js';
import {ChartTimeseries} from './chart-timeseries.js';
import {DetailsTable} from './details-table.js';
import {ElementBase, STORE} from './element-base.js';
import {MAX_POINTS} from './timeseries-merger.js';
import {MODE} from './layout-timeseries.js';
import {get, set} from 'dot-prop-immutable';
import {html, css} from 'lit-element';
import {isElementChildOf, isDebug} from './utils.js';

import {
  LEVEL_OF_DETAIL,
  TimeseriesRequest,
  createFetchDescriptors,
} from './timeseries-request.js';

/**
  * ChartCompound synchronizes revision ranges and axis properties between a
  * minimap and a main chart, and among any number of other linked charts.
  */
export class ChartCompound extends ElementBase {
  static get is() { return 'chart-compound'; }

  static get properties() {
    return {
      linkedStatePath: String,
      linkedCursorRevision: Number,
      linkedCursorScalar: Object,
      linkedMinRevision: Number,
      linkedMaxRevision: Number,
      linkedMode: String,
      linkedZeroYAxis: Boolean,
      linkedFixedXAxis: Boolean,

      statePath: String,
      lineDescriptors: Array,
      isExpanded: Boolean,
      minimapLayout: Object,
      chartLayout: Object,
      details: Object,
      isShowingOptions: Boolean,
      isLinked: Boolean,
      cursorRevision: Number,
      cursorScalar: Object,
      minRevision: Number,
      maxRevision: Number,
      mode: String,
      zeroYAxis: Boolean,
      fixedXAxis: Boolean,
    };
  }

  static buildState(options = {}) {
    const minimapLayout = {
      ...ChartTimeseries.buildState({
        levelOfDetail: LEVEL_OF_DETAIL.XY,
      }),
      graphHeight: 40,
    };
    minimapLayout.xAxis.height = 15;
    minimapLayout.yAxis.width = 50;
    minimapLayout.yAxis.generateTicks = false;

    const chartLayout = ChartTimeseries.buildState({
      levelOfDetail: LEVEL_OF_DETAIL.ANNOTATIONS,
      showTooltip: true,
    });
    chartLayout.xAxis.height = 15;
    chartLayout.xAxis.showTickLines = true;
    chartLayout.yAxis.width = 50;
    chartLayout.yAxis.showTickLines = true;
    chartLayout.brushRevisions = options.brushRevisions || [];

    return {
      lineDescriptors: [],
      isExpanded: options.isExpanded !== false,
      minimapLayout,
      chartLayout,
      details: DetailsTable.buildState(),
      isShowingOptions: options.isShowingOptions !== false,
      isLinked: options.isLinked !== false,
      cursorRevision: 0,
      cursorScalar: undefined,
      minRevision: options.minRevision,
      maxRevision: options.maxRevision,
      mode: options.mode || MODE.NORMALIZE_UNIT,
      zeroYAxis: options.zeroYAxis || false,
      fixedXAxis: options.fixedXAxis !== false,
    };
  }

  static buildLinkedState(options = {}) {
    return {
      linkedCursorRevision: undefined,
      linkedCursorScalar: undefined,
      linkedMinRevision: options.minRevision,
      linkedMaxRevision: options.maxRevision,
      linkedMode: options.mode || MODE.NORMALIZE_UNIT,
      linkedZeroYAxis: options.zeroYAxis || false,
      linkedFixedXAxis: options.fixedXAxis !== false,
    };
  }

  static get styles() {
    return css`
      #minimap,
      #chart {
        width: 100%;
      }

      #minimap {
        max-height: 75px;
      }

      :host {
        flex-grow: 1;
        margin-right: 8px;
        min-width: 500px;
      }

      #options {
        color: var(--primary-color-dark, blue);
        cursor: pointer;
      }

      #options-menu {
        border: 1px solid var(--primary-color-dark, blue);
        padding: 8px;
        margin: 4px 0;
      }

      #options-menu::after {
        background: var(--background-color, white);
        border-bottom: 1px solid var(--primary-color-dark, blue);
        border-left: 1px solid var(--primary-color-dark, blue);
        content: '';
        display: block;
        height: 16px;
        margin-left: -4px;
        position: absolute;
        transform: rotate(-45deg);
        width: 16px;
      }

      #options-menu cp-flex {
        align-items: center;
      }

      #options-menu div b {
        margin-right: 8px;
      }

      chops-radio-group {
        flex-direction: row;
      }

      #options {
        position: absolute;
        margin-top: 20px;
      }
    `;
  }

  render() {
    const linkedTitle = this.isLinked ?
      'Now synchronizing options with other linked charts. Click to switch ' +
      'to unlink.' :
      'Now unlinked from other charts. Click to switch to synchronizing ' +
      'options with other linked charts.';
    const zeroYTitle = this.zeroYAxis ?
      'Now zeroing y-axis. Click to switch to floating y-axis.' :
      'Now floating y-axis. Click to switch to zero y-axis.';
    const fixedXTitle = this.fixedXAxis ?
      'Now fixing x-axis distance between points. Click to switch to scale ' +
      'x-axis distance between points.' :
      'Now scaling x-axis distance between points. Click to switch to fix ' +
      'x-axis distance between points.';
    const hideOptions = !this.minimapLayout || !this.minimapLayout.lines ||
      (!this.minimapLayout.isLoading &&
       (this.minimapLayout.lines.length === 0));
    const errors = new Set();
    if (this.minimapLayout && this.minimapLayout.errors) {
      for (const err of this.minimapLayout.errors) {
        errors.add(err);
      }
    }
    if (this.chartLayout && this.chartLayout.errors) {
      for (const err of this.chartLayout.errors) {
        errors.add(err);
      }
    }

    return html`
      <div ?hidden="${!this.isExpanded}">
        <div ?hidden="${!this.lineDescriptors ||
            (this.lineDescriptors.length < ChartTimeseries.MAX_LINES)}">
          Displaying the first 10 lines. Select other items in order to
          display them.
        </div>

        <error-set .errors="${[...errors]}"></error-set>

        <div
            id="options-menu"
            ?hidden="${hideOptions || !this.isShowingOptions}">
          <cp-flex>
            <b>Options</b>
            <chops-switch
                ?checked="${this.isLinked}"
                title="${linkedTitle}"
                @change="${this.onToggleLinked_}">
              Linked to other charts
            </chops-switch>
            <chops-switch
                ?checked="${this.zeroYAxis}"
                title="${zeroYTitle}"
                @change="${this.onToggleZeroYAxis_}">
              Zero Y-Axis
            </chops-switch>
            <chops-switch
                ?checked="${this.fixedXAxis}"
                title="${fixedXTitle}"
                @change="${this.onToggleFixedXAxis_}">
              Fixed X-Axis
            </chops-switch>
          </cp-flex>
          <cp-flex>
            <b>Mode</b>
            <chops-radio-group
                selected="${this.mode}"
                @selected-changed="${this.onModeChange_}">
              <chops-radio name="NORMALIZE_UNIT">
                Normalize per unit
              </chops-radio>
              <chops-radio name="NORMALIZE_LINE">
                Normalize per line
              </chops-radio>
              <chops-radio name="CENTER">
                Center
              </chops-radio>
              <chops-radio name="DELTA">
                Delta
              </chops-radio>
            </chops-radio-group>
          </cp-flex>
        </div>

        <cp-icon
            id="options"
            icon="settings"
            ?hidden="${hideOptions}"
            style="width: calc(${
  this.chartLayout ? this.chartLayout.yAxisWidth : 8}px - 8px);"
            tabindex="0"
            @click="${this.onOptionsToggle_}">
        </cp-icon>

        <chart-timeseries
            id="minimap"
            .statePath="${this.statePath}.minimapLayout"
            placeholderHeight="0"
            @brush-end="${this.onMinimapBrush_}">
        </chart-timeseries>
      </div>

      <chart-timeseries
          id="chart"
          .statePath="${this.statePath}.chartLayout"
          placeholderHeight="310px"
          @get-tooltip="${this.onGetTooltip_}"
          @brush-end="${this.onChartBrush_}"
          @line-count-change="${this.onLineCountChange_}"
          @chart-click="${this.onChartClick_}">
        <slot></slot>
      </chart-timeseries>

      <div ?hidden="${!this.isExpanded}">
        <details-table
            id="details"
            .statePath="${this.statePath}.details"
            @reload-chart="${this.onReload_}">
        </details-table>
      </div>
    `;
  }

  stateChanged(rootState) {
    if (!this.statePath || !this.linkedStatePath) return;

    const oldChartLoading = this.chartLayout && this.chartLayout.isLoading;
    const oldCursorRevision = this.cursorRevision;
    const oldCursorScalar = this.cursorScalar;
    const oldFixedXAxis = this.fixedXAxis;
    const oldLineDescriptors = this.lineDescriptors;
    const oldLinkedCursorRevision = this.linkedCursorRevision;
    const oldLinkedCursorScalar = this.linkedCursorScalar;
    const oldLinkedFixedXAxis = this.linkedFixedXAxis;
    const oldLinkedMaxRevision = this.linkedMaxRevision;
    const oldLinkedMinRevision = this.linkedMinRevision;
    const oldLinkedMode = this.linkedMode;
    const oldLinkedZeroYAxis = this.linkedZeroYAxis;
    const oldMinRevision = this.minRevision;
    const oldMaxRevision = this.maxRevision;
    const oldMode = this.mode;
    const oldZeroYAxis = this.zeroYAxis;

    Object.assign(this, get(rootState, this.linkedStatePath));
    Object.assign(this, get(rootState, this.statePath));

    if (oldChartLoading && !this.chartLayout.isLoading) {
      STORE.dispatch({
        type: ChartCompound.reducers.updateStale.name,
        statePath: this.statePath,
      });
    }

    if (this.lineDescriptors !== oldLineDescriptors ||
        this.minRevision !== oldMinRevision ||
        this.maxRevision !== oldMaxRevision ||
        this.mode !== oldMode ||
        this.fixedXAxis !== oldFixedXAxis ||
        this.zeroYAxis !== oldZeroYAxis) {
      this.debounce('load', () => ChartCompound.load(this.statePath));
    }

    if (this.cursorRevision !== oldCursorRevision ||
        this.cursorScalar !== oldCursorScalar) {
      // The `cursorRevision` and `cursorScalar` properties are set either from
      // onGetTooltip_ as the user mouses around this main chart, or from
      // linkedCursor as the user mouses around the main chart in a different
      // chart-compound.
      STORE.dispatch({
        type: ChartCompound.reducers.setCursors.name,
        statePath: this.statePath,
      });
    }

    if (this.isLinked) {
      let delta = {};
      if (this.linkedCursorRevision !== oldLinkedCursorRevision) {
        delta.cursorRevision = this.linkedCursorRevision;
      }
      if (this.linkedCursorScalar !== oldLinkedCursorScalar) {
        delta.cursorScalar = this.linkedCursorScalar;
      }
      if (this.linkedMinRevision !== oldLinkedMinRevision) {
        delta.minRevision = this.linkedMinRevision;
      }
      if (this.linkedMaxRevision !== oldLinkedMaxRevision) {
        delta.maxRevision = this.linkedMaxRevision;
      }
      if (this.linkedMode !== oldLinkedMode) {
        delta.mode = this.linkedMode;
      }
      if (this.linkedZeroYAxis !== oldLinkedZeroYAxis) {
        delta.zeroYAxis = this.linkedZeroYAxis;
      }
      if (this.linkedFixedXAxis !== oldLinkedFixedXAxis) {
        delta.fixedXAxis = this.linkedFixedXAxis;
      }
      if (Object.keys(delta).length > 0) {
        STORE.dispatch(UPDATE(this.statePath, delta));
      }

      delta = {};
      if (this.cursorRevision !== oldCursorRevision) {
        delta.linkedCursorRevision = this.cursorRevision;
      }
      if (this.cursorScalar !== oldCursorScalar) {
        delta.linkedCursorScalar = this.cursorScalar;
      }
      if (this.minRevision !== oldMinRevision) {
        delta.linkedMinRevision = this.minRevision;
      }
      if (this.maxRevision !== oldMaxRevision) {
        delta.linkedMaxRevision = this.maxRevision;
      }
      if (this.mode !== oldMode) delta.linkedMode = this.mode;
      if (this.zeroYAxis !== oldZeroYAxis) {
        delta.linkedZeroYAxis = this.zeroYAxis;
      }
      if (this.fixedXAxis !== oldFixedXAxis) {
        delta.linkedFixedXAxis = this.fixedXAxis;
      }
      if (Object.keys(delta).length > 0) {
        STORE.dispatch(UPDATE(this.linkedStatePath, delta));
      }
    }
  }

  // This doesn't really load any data for display, that's handled by the
  // chart-timeseries components, whose states are in minimapLayout and
  // chartLayout.
  // This method basically copies lineDescriptors and other configuration to
  // minimapLayout and chartLayout. chart-timeseries observes their
  // lineDescriptors and then actually loads the data. However, this method
  // handles a few gotchas that require coordination between the minimap and
  // the main chart.
  //  * Only the first non-empty lineDescriptor is copied to minimapLayout.
  //    The minimap is not very tall, so there's only room for one timeseries.
  //    This method doesn't know ahead of time which lineDescriptors will
  //    contain data, so this method fetches data for each lineDescriptor
  //    until it finds some data, and selects that line for the minimap.
  //  * If the URL or session state didn't specify min/maxRevision, they are
  //    computed from the data for the first non-empty lineDescriptor
  //  * A lineDescriptor for the ref build is added to chartLayout if there's
  //    only one lineDescriptor.
  static async load(statePath) {
    const state = get(STORE.getState(), statePath);
    if (!state || !state.lineDescriptors ||
        state.lineDescriptors.length === 0) {
      STORE.dispatch(CHAIN(
          UPDATE(`${statePath}.minimapLayout`, {lineDescriptors: []}),
          UPDATE(`${statePath}.chartLayout`, {lineDescriptors: []}),
      ));
      return;
    }

    STORE.dispatch(UPDATE(statePath, {isLoading: true}));
    const {firstNonEmptyLineDescriptor, timeserieses} =
      await ChartCompound.findFirstNonEmptyLineDescriptor(
          state.lineDescriptors);

    const firstRevision = ChartCompound.findFirstRevision(timeserieses);
    const lastRevision = ChartCompound.findLastRevision(timeserieses);
    const maxRevision = ChartCompound.computeMaxRevision(
        state.maxRevision, firstRevision, lastRevision);
    const minRevision = ChartCompound.computeMinRevision(
        firstNonEmptyLineDescriptor, state.minRevision, timeserieses,
        firstRevision, maxRevision);

    const minimapLineDescriptors = [];
    if (firstNonEmptyLineDescriptor) {
      minimapLineDescriptors.push({...firstNonEmptyLineDescriptor});
    }

    // Never set zeroYAxis on the minimap. It's too short to waste space.
    STORE.dispatch(UPDATE(`${statePath}.minimapLayout`, {
      lineDescriptors: minimapLineDescriptors,
      brushRevisions: [minRevision, maxRevision],
      fixedXAxis: state.fixedXAxis,
    }));

    let lineDescriptors = state.lineDescriptors;
    if (lineDescriptors.length === 1) {
      lineDescriptors = [
        lineDescriptors[0],
        {...lineDescriptors[0], buildType: 'ref'},
      ];
    }

    STORE.dispatch(CHAIN(
        UPDATE(`${statePath}.chartLayout`, {
          lineDescriptors,
          minRevision,
          maxRevision,
          fixedXAxis: state.fixedXAxis,
          mode: state.mode,
          zeroYAxis: state.zeroYAxis,
        }),
        UPDATE(`${statePath}.details`, {
          lineDescriptors,
          minRevision,
          maxRevision,
          revisionRanges: ChartTimeseries.revisionRanges(
              state.chartLayout.brushRevisions),
        }),
        UPDATE(statePath, {isLoading: false})));
  }

  async onGetTooltip_(event) {
    const p = event.detail.nearestPoint;
    let cursorScalar;
    if (p.datum &&
        (p.datum.unit instanceof tr.b.Unit) &&
        (typeof(p.y) === 'number')) {
      cursorScalar = new tr.b.Scalar(p.datum.unit, p.y);
    }
    STORE.dispatch(UPDATE(this.statePath, {
      cursorRevision: p.x,
      cursorScalar,
    }));
    // Don't reset cursor on mouseLeave. Allow users to scroll through
    // sparklines.
  }

  async onLineCountChange_() {
    STORE.dispatch({
      type: ChartCompound.reducers.detailsColorByLine.name,
      statePath: this.statePath,
    });
  }

  async onChartBrush_(event) {
    await STORE.dispatch({
      type: ChartCompound.reducers.updateChartBrush.name,
      statePath: this.statePath,
    });
  }

  async onChartClick_(event) {
    STORE.dispatch({
      type: ChartCompound.reducers.brushChart.name,
      statePath: this.statePath,
      nearestLine: event.detail.nearestLine,
      nearestPoint: event.detail.nearestPoint,
      addBrush: event.detail.ctrlKey,
    });
  }

  firstUpdated() {
    this.minimap = this.shadowRoot.querySelector('#minimap');
  }

  async onOptionsToggle_(event) {
    await STORE.dispatch(TOGGLE(this.statePath + '.isShowingOptions'));
  }

  async onMinimapBrush_(event) {
    await STORE.dispatch({
      type: ChartCompound.reducers.brushMinimap.name,
      statePath: this.statePath,
    });
  }

  async onToggleLinked_(event) {
    await STORE.dispatch({
      type: ChartCompound.reducers.toggleLinked.name,
      statePath: this.statePath,
      linkedStatePath: this.linkedStatePath,
    });
    ChartCompound.load(statePath);
  }

  async onToggleZeroYAxis_(event) {
    await STORE.dispatch(TOGGLE(this.statePath + '.zeroYAxis'));
  }

  async onToggleFixedXAxis_(event) {
    await STORE.dispatch(TOGGLE(this.statePath + '.fixedXAxis'));
  }

  async onModeChange_(event) {
    await STORE.dispatch(UPDATE(this.statePath, {mode: event.detail.value}));
  }

  async onReload_(event) {
    await ChartCompound.load(this.statePath);
  }

  // Fetch data for lineDescriptors in order until the first non-empty line is
  // found.
  static async findFirstNonEmptyLineDescriptor(lineDescriptors) {
    for (const lineDescriptor of lineDescriptors) {
      const fetchDescriptors = createFetchDescriptors(
          lineDescriptor, LEVEL_OF_DETAIL.XY);
      const batches = new BatchIterator();
      for (const fetchDescriptor of fetchDescriptors) {
        batches.add(new TimeseriesRequest(fetchDescriptor).reader());
      }

      for await (const {results, errors} of batches) {
        for (const timeseries of results) {
          if (!timeseries || !timeseries.length) continue;
          return {
            firstNonEmptyLineDescriptor: lineDescriptor,
            timeserieses: [timeseries],
          };
        }
      }
    }
    return {timeserieses: []};
  }

  static findFirstRevision(timeserieses) {
    const firstRevision = tr.b.math.Statistics.min(timeserieses.map(ts => {
      if (!ts) return Infinity;
      const datum = ts[0];
      if (datum === undefined) return Infinity;
      return datum.revision;
    }));
    if (firstRevision === Infinity) return undefined;
    return firstRevision;
  }

  static findLastRevision(timeserieses) {
    const lastRevision = tr.b.math.Statistics.max(timeserieses.map(ts => {
      if (!ts) return -Infinity;
      const datum = ts[ts.length - 1];
      if (datum === undefined) return -Infinity;
      return datum.revision;
    }));
    if (lastRevision === -Infinity) return undefined;
    return lastRevision;
  }

  static computeMinRevision(
      lineDescriptor, minRevision, timeserieses, firstRevision, lastRevision) {
    if (minRevision &&
        minRevision >= firstRevision &&
        minRevision < lastRevision) {
      return minRevision;
    }

    timeserieses = timeserieses.filter(ts => ts && ts.length);
    if (timeserieses.length === 0) return minRevision;

    if (lineDescriptor.bots.length === 1) {
      // Display the last MAX_POINTS points in the main chart.
      const timeseries = timeserieses[0];
      const lastIndex = tr.b.findLowIndexInSortedArray(
          timeseries, d => d.revision, lastRevision);
      const i = Math.max(0, lastIndex - MAX_POINTS);
      return timeseries[i].revision;
    }

    // There are timeseries from multiple bots, so their revisions don't line
    // up. Find minRevision such that TimeseriesMerger will produce
    // MAX_POINTS points in the main chart.

    const iters = timeserieses.map(timeseries => {
      return {
        timeseries,
        index: tr.b.findLowIndexInSortedArray(
            timeseries, d => d.revision, lastRevision),
        get currentRevision() {
          return this.timeseries[this.index].revision;
        }
      };
    });
    for (let p = 0; p < MAX_POINTS; ++p) {
      // Decrement all of the indexes whose revisions are equal to the max
      // currentRevision. See TimeseriesMerger for more about this algorithm.
      const maxCurrent = tr.b.math.Statistics.max(
          iters, iter => iter.currentRevision);
      for (const iter of iters) {
        if (iter.currentRevision === maxCurrent && iter.index > 0) --iter.index;
      }
    }
    return tr.b.math.Statistics.max(iters, iter => iter.currentRevision);
  }

  static computeMaxRevision(maxRevision, firstRevision, lastRevision) {
    if (!maxRevision || maxRevision <= firstRevision) {
      return lastRevision;
    }
    return maxRevision;
  }
}

ChartCompound.reducers = {
  detailsColorByLine: (state, action, rootState) => {
    const colorByLine = state.chartLayout.lines.map(line => {
      return {
        descriptor: ChartTimeseries.stringifyDescriptor(line.descriptor),
        color: line.color,
      };
    });
    const details = {...state.details, colorByLine};
    return {...state, details};
  },

  updateChartBrush: (state, action, rootState) => {
    // ChartBase updated its xAxis.brushes[*].xPct. Compute brushRevisions
    // from xPct, then update chartLayout.brushRevisions and
    // details.revisionRanges.
    const brushRevisions = [];
    for (const brush of state.chartLayout.xAxis.brushes) {
      const xPct = parseFloat(brush.xPct);
      const revRange = tr.b.math.Range.fromExplicitRange(
          state.chartLayout.minRevision, state.chartLayout.maxRevision);
      for (const line of state.chartLayout.lines) {
        const index = Math.min(
            line.data.length - 1,
            tr.b.findLowIndexInSortedArray(
                line.data, d => d.xPct, xPct));
        // Now, line.data[index].xPct >= xPct
        const thisMax = line.data[index].x;
        const thisMin = (index > 0) ? line.data[index - 1].x : thisMax;
        revRange.min = Math.max(revRange.min, thisMin);
        revRange.max = Math.min(revRange.max, thisMax);
      }
      brushRevisions.push(parseInt(revRange.center));
    }
    const chartLayout = {...state.chartLayout, brushRevisions};
    const revisionRanges = ChartTimeseries.revisionRanges(brushRevisions);
    const details = {...state.details, revisionRanges};
    return {...state, chartLayout, details};
  },

  brushChart: (state, {nearestLine, nearestPoint, addBrush}, rootState) => {
    // Set chartLayout.brushRevisions and xAxis.brushes to surround
    // nearestPoint, not to the revisions that will be displayed in the
    // details-table.
    const datumIndex = nearestLine.data.indexOf(nearestPoint);
    if (datumIndex < 0) return state;

    // If nearestPoint is in revisionRanges, reset brushes.
    for (const range of ChartTimeseries.revisionRanges(
        state.chartLayout.brushRevisions)) {
      if (range.min < nearestPoint.x && nearestPoint.x < range.max) {
        const xAxis = {...state.chartLayout.xAxis, brushes: []};
        const chartLayout = {...state.chartLayout, brushRevisions: [], xAxis};
        const details = {...state.details, revisionRanges: []};
        return {...state, chartLayout, details};
      }
    }

    const brushes = addBrush ? [...state.chartLayout.xAxis.brushes] : [];

    let x = nearestPoint.x - 1;
    let xPct = nearestPoint.xPct;
    if (datumIndex > 0) {
      const prevPoint = nearestLine.data[datumIndex - 1];
      x = (nearestPoint.x + prevPoint.x) / 2;
      xPct = ((parseFloat(nearestPoint.xPct) +
                parseFloat(prevPoint.xPct)) / 2) + '%';
    }
    brushes.push({x, xPct});

    x = nearestPoint.x + 1;
    xPct = nearestPoint.xPct;
    if (datumIndex < nearestLine.data.length - 1) {
      const nextPoint = nearestLine.data[datumIndex + 1];
      x = (nearestPoint.x + nextPoint.x) / 2;
      xPct = ((parseFloat(nearestPoint.xPct) +
                parseFloat(nextPoint.xPct)) / 2) + '%';
    }
    brushes.push({x, xPct});

    brushes.sort((x, y) => x.x - y.x);  // ascending
    const brushRevisions = brushes.map(brush => parseInt(brush.x));
    const xAxis = {...state.chartLayout.xAxis, brushes};
    const chartLayout = {...state.chartLayout, brushRevisions, xAxis};

    const revisionRanges = ChartTimeseries.revisionRanges(brushRevisions);
    const details = {...state.details, revisionRanges};
    return {...state, chartLayout, details};
  },

  // Translate cursorRevision and cursorScalar to x/y pct in the minimap and
  // chartlayout. Don't draw yAxis.cursor in the minimap, it's too short.
  setCursors: (state, action, rootState) => {
    let minimapXPct;
    let chartXPct;
    let color;
    let chartYPct;

    if (state.cursorRevision && state.chartLayout &&
        state.chartLayout.xAxis && !state.chartLayout.xAxis.range.isEmpty) {
      if (state.fixedXAxis) {
        // Bisect to find point nearest to cursorRevision.
        if (state.minimapLayout.lines.length) {
          minimapXPct = tr.b.findClosestElementInSortedArray(
              state.minimapLayout.lines[0].data,
              d => d.x,
              state.cursorRevision).xPct + '%';
        }

        let nearestDatum;
        for (const line of state.chartLayout.lines) {
          const datum = tr.b.findClosestElementInSortedArray(
              line.data, d => d.x, state.cursorRevision);
          if (!nearestDatum ||
              (Math.abs(state.cursorRevision - datum.x) <
                Math.abs(state.cursorRevision - nearestDatum.x))) {
            nearestDatum = datum;
          }
        }
        chartXPct = nearestDatum.xPct + '%';
      } else {
        minimapXPct = state.minimapLayout.xAxis.range.normalize(
            state.cursorRevision) * 100 + '%';
        chartXPct = state.chartLayout.xAxis.range.normalize(
            state.cursorRevision) * 100 + '%';
      }

      if (state.chartLayout.tooltip &&
          state.chartLayout.tooltip.isVisible) {
        color = tr.b.Color.fromString(state.chartLayout.tooltip.color);
        color.a = 0.8;
      }
    }

    if (state.cursorScalar && state.chartLayout && state.chartLayout.yAxis) {
      let yRange;
      if (state.mode === MODE.NORMALIZE_UNIT) {
        if (state.chartLayout.yAxis.rangeForUnitName) {
          yRange = state.chartLayout.yAxis.rangeForUnitName.get(
              state.cursorScalar.unit.baseUnit.unitName);
        }
      } else if (state.chartLayout.lines.length === 1) {
        yRange = state.chartLayout.lines[0].yRange;
      }
      if (yRange) {
        chartYPct = tr.b.math.truncate((1 - yRange.normalize(
            state.cursorScalar.value)) * 100, 1) + '%';
      }
    }

    return {
      ...state,
      minimapLayout: {
        ...state.minimapLayout,
        xAxis: {
          ...state.minimapLayout.xAxis,
          cursor: {
            pct: minimapXPct,
          },
        },
      },
      chartLayout: {
        ...state.chartLayout,
        xAxis: {
          ...state.chartLayout.xAxis,
          cursor: {
            pct: chartXPct,
            color,
          },
        },
        yAxis: {
          ...state.chartLayout.yAxis,
          cursor: {
            color,
            pct: chartYPct,
          },
        },
      },
    };
  },

  // Maybe copy linkedState to state.
  toggleLinked: (state, {linkedStatePath}, rootState) => {
    state = {...state, isLinked: !state.isLinked};
    if (state.isLinked) {
      const linkedState = get(rootState, linkedStatePath);
      state = {
        ...state,
        cursorRevision: linkedState.linkedCursorRevision,
        minRevision: linkedState.linkedMinRevision,
        maxRevision: linkedState.linkedMaxRevision,
        mode: linkedState.linkedMode,
        zeroYAxis: linkedState.linkedZeroYAxis,
        fixedXAxis: linkedState.linkedFixedXAxis,
      };
    }
    return state;
  },

  // Manage revision ranges as the user brushes the minimap.
  brushMinimap: (state, action, rootState) => {
    if (state.minimapLayout.lines.length === 0) return state;
    const range = new tr.b.math.Range();
    for (const brush of state.minimapLayout.xAxis.brushes) {
      const index = Math.min(
          state.minimapLayout.lines[0].data.length - 1,
          tr.b.findLowIndexInSortedArray(
              state.minimapLayout.lines[0].data,
              datum => datum.xPct,
              parseFloat(brush.xPct)));
      const datum = state.minimapLayout.lines[0].data[index];
      if (!datum) continue;
      range.addValue(datum.x);
    }
    const minRevision = range.min;
    let maxRevision = range.max;

    const minimapLayout = {
      ...state.minimapLayout,
      brushRevisions: [minRevision, maxRevision],
    };
    const chartLayout = {
      ...state.chartLayout,
      minRevision,
      maxRevision,
    };

    // Set state.maxRevision = undefined if maxRevision === last revision in
    // minimapLayout.lines[0].data so ChartSection.getRouteParams leaves it
    // unspecified.
    if (maxRevision === state.minimapLayout.xAxis.range.max) {
      maxRevision = undefined;
    }
    // Don't set minRevision to undefined because it defaults to 1 month ago,
    // not the beginning of time.

    return {...state, minimapLayout, chartLayout, minRevision, maxRevision};
  },

  // Add an icon to the last datum of a line if it's stale.
  updateStale: (state, action, rootState) => {
    if (!state || !state.minimapLayout || !state.minimapLayout.lines ||
        (state.minimapLayout.lines.length === 0) ||
        (state.minimapLayout.brushRevisions[1] <
          state.minimapLayout.lines[0].data[
              state.minimapLayout.lines[0].data.length - 1].x)) {
      return state;
    }

    const MS_PER_DAY = tr.b.convertUnit(
        1, tr.b.UnitScale.TIME.DAY, tr.b.UnitScale.TIME.MILLI_SEC);
    const now = new Date();
    const staleMs = isDebug() ? 1 : MS_PER_DAY;
    const staleTimestamp = now - staleMs;
    let anyStale = false;
    const lines = state.chartLayout.lines.map(line => {
      const minDate = line.data[line.data.length - 1].datum.timestamp;
      if (!minDate) return line;
      if (minDate >= staleTimestamp) return line;
      anyStale = true;
      let hue;
      if (minDate < (now - (28 * staleMs))) {
        hue = 0;  // red
      } else if (minDate < (now - (7 * staleMs))) {
        hue = 20;  // red-orange
      } else if (minDate < (now - staleMs)) {
        hue = 40;  // orange
      }
      const iconColor = `hsl(${hue}, 90%, 60%)`;
      return set(line, `data.${line.data.length - 1}`, datum => {
        return {...datum, icon: 'clock', iconColor};
      });
    });
    if (!anyStale) return state;
    return {...state, chartLayout: {...state.chartLayout, lines}};
  },
};

ElementBase.register(ChartCompound);
