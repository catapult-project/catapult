/* Copyright 2019 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';
tr.exportTo('cp', () => {
  class ChartTimeseries extends cp.ElementBase {
    static get template() {
      return Polymer.html`
        <style>
          :host {
            display: block;
          }
          place-holder {
            @apply --chart-placeholder;
          }
        </style>

        <template is="dom-if" if="[[showPlaceholder(isLoading, lines)]]">
          <place-holder>
            <slot></slot>
          </place-holder>
        </template>

        <template is="dom-if" if="[[!showPlaceholder(isLoading, lines)]]">
          <chart-base
              state-path="[[statePath]]"
              on-get-tooltip="onGetTooltip_"
              on-mouse-leave-main="onMouseLeaveMain_">
          </chart-base>
        </template>
      `;
    }

    showPlaceholder(isLoading, lines) {
      return !isLoading && this.isEmpty_(lines);
    }

    async onGetTooltip_(event) {
      await this.dispatch('getTooltip', this.statePath,
          event.detail.mainRect,
          event.detail.nearestLine,
          this.lines.indexOf(event.detail.nearestLine),
          event.detail.nearestPoint);
    }

    async onMouseLeaveMain_(event) {
      await this.dispatch('hideTooltip', this.statePath);
    }

    observeLineDescriptors_() {
      // Changing any of these properties causes Polymer to call this method.
      // Changing all at once causes Polymer to call it many times within the
      // same task, so use debounce to only call load() once.
      this.debounce('load', () => {
        this.dispatch('load', this.statePath);
      }, Polymer.Async.microTask);
    }

    observeLines_(newLines, oldLines) {
      const newLength = newLines ? newLines.length : 0;
      const oldLength = oldLines ? oldLines.length : 0;
      if (newLength === oldLength) return;
      this.dispatchEvent(new CustomEvent('line-count-change', {
        bubbles: true,
        composed: true,
      }));
    }
  }

  ChartTimeseries.MAX_LINES = 10;

  ChartTimeseries.State = {
    ...cp.ChartBase.State,
    lines: options => cp.ChartBase.State.lines(options),
    lineDescriptors: options => [],
    minRevision: options => undefined,
    maxRevision: options => undefined,
    brushRevisions: options => [],
    isLoading: options => false,
    xAxis: options => {
      return {...cp.ChartBase.State.xAxis(options), generateTicks: true};
    },
    yAxis: options => {
      return {...cp.ChartBase.State.yAxis(options), generateTicks: true};
    },
    zeroYAxis: options => false,
    fixedXAxis: options => false,
    mode: options => cp.MODE.NORMALIZE_UNIT,
    levelOfDetail: options => options.levelOfDetail || cp.LEVEL_OF_DETAIL.XY,
  };

  ChartTimeseries.properties = cp.buildProperties(
      'state', ChartTimeseries.State);
  ChartTimeseries.buildState = options => cp.buildState(
      ChartTimeseries.State, options);

  ChartTimeseries.properties.lines.observer = 'observeLines_';
  ChartTimeseries.observers = [
    'observeLineDescriptors_(lineDescriptors, mode, fixedXAxis, zeroYAxis, ' +
        'maxRevision, minRevision)',
  ];

  function arraySetEqual(a, b) {
    if (a.length !== b.length) return false;
    for (const e of a) {
      if (!b.includes(e)) return false;
    }
    return true;
  }

  ChartTimeseries.lineDescriptorEqual = (a, b) => {
    if (a === b) return true;
    if (!arraySetEqual(a.suites, b.suites)) return false;
    if (!arraySetEqual(a.bots, b.bots)) return false;
    if (!arraySetEqual(a.cases, b.cases)) return false;
    if (a.measurement !== b.measurement) return false;
    if (a.statistic !== b.statistic) return false;
    if (a.buildType !== b.buildType) return false;
    if (a.minRevision !== b.minRevision) return false;
    if (a.maxRevision !== b.maxRevision) return false;
    return true;
  };

  ChartTimeseries.actions = {
    load: statePath => async(dispatch, getState) => {
      let state = Polymer.Path.get(getState(), statePath);
      if (!state) return;

      dispatch(Redux.UPDATE(statePath, {isLoading: true, lines: []}));

      await ChartTimeseries.loadLines(statePath)(dispatch, getState);

      state = Polymer.Path.get(getState(), statePath);
      if (!state) {
        // User closed the chart before it could finish loading
        return;
      }

      dispatch(Redux.UPDATE(statePath, {isLoading: false}));
    },

    getTooltip: (statePath, mainRect, line, lineIndex, datum) =>
      async(dispatch, getState) => {
        dispatch(Redux.CHAIN(
            {
              type: ChartTimeseries.reducers.getTooltip.name,
              statePath,
              mainRect,
              line,
              datum,
            },
            {
              type: ChartTimeseries.reducers.mouseYTicks.name,
              statePath,
              line,
            },
            {
              type: cp.ChartBase.reducers.boldLine.name,
              statePath,
              lineIndex,
            },
        ));
      },

    hideTooltip: statePath => async(dispatch, getState) => {
      dispatch(Redux.CHAIN(
          Redux.UPDATE(statePath, {tooltip: undefined}),
          {
            type: ChartTimeseries.reducers.mouseYTicks.name,
            statePath,
          },
          {
            type: cp.ChartBase.reducers.boldLine.name,
            statePath,
          },
      ));
    },

    // Measure the yAxis tick labels on the screen and size the yAxis region
    // appropriately. Measuring elements is asynchronous, so this logic needs to
    // be an action creator.
    measureYTicks: statePath => async(dispatch, getState) => {
      const ticks = collectYAxisTicks(Polymer.Path.get(getState(), statePath));
      if (ticks.length === 0) return;
      dispatch({
        type: ChartTimeseries.reducers.yAxisWidth.name,
        statePath,
        rects: await Promise.all(ticks.map(tick => cp.measureText(tick))),
      });
    },
  };

  function collectYAxisTicks(state) {
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

  const SHADE_FILL_ALPHA = 0.2;

  // Set line.color.
  ChartTimeseries.assignColors = lines => {
    const isTestLine = line => line.descriptor.buildType !== 'ref';
    const testLines = lines.filter(isTestLine);
    const colors = cp.generateColors(testLines.length, {hueOffset: 0.64});
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
  };

  ChartTimeseries.reducers = {
    // Aggregate timeserieses, assign colors, layout chart data, snap revisions.
    layout: (state, {timeseriesesByLine}, rootState) => {
      const lines = [];
      for (const {lineDescriptor, timeserieses} of timeseriesesByLine) {
        const data = ChartTimeseries.aggregateTimeserieses(
            lineDescriptor, timeserieses, state.levelOfDetail, {
              minRevision: state.minRevision,
              maxRevision: state.maxRevision,
            });
        if (data.length === 0) continue;

        let unit = timeserieses[0][0].unit;
        if (state.mode === cp.MODE.DELTA) {
          unit = unit.correspondingDeltaUnit;
          const offset = data[0].y;
          for (const datum of data) datum.y -= offset;
        }

        lines.push({descriptor: lineDescriptor, unit, data, strokeWidth: 1});
      }

      state = {...state, lines};
      ChartTimeseries.assignColors(state.lines);
      state = cp.layoutTimeseries(state);
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
      if (!state.yAxis.generateTicks) return state;
      const isNormalizeLine = (
        state.mode === cp.MODE.NORMALIZE_LINE || state.mode === cp.MODE.CENTER);
      if (!isNormalizeLine &&
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

      if (datum.icon === 'cp:clock') {
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

      rows.push({name: 'value', value: line.unit.format(datum.y)});

      rows.push({name: 'revision', value: datum.datum.revision});
      for (const [name, value] of Object.entries(datum.datum.revisions || {})) {
        rows.push({name, value});
      }

      rows.push({
        name: 'uploaded',
        value: datum.datum.timestamp.toString(),
      });

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

  // Snap to nearest existing revision
  ChartTimeseries.brushRevisions = state => {
    const brushes = state.brushRevisions.map(x => {
      let closestDatum;
      for (const line of state.lines) {
        const datum = tr.b.findClosestElementInSortedArray(
            line.data, d => d.x, x);
        if (closestDatum === undefined ||
            (Math.abs(closestDatum.x - x) > Math.abs(datum.x - x))) {
          closestDatum = datum;
        }
      }
      return {x, xPct: closestDatum.xPct + '%'};
    });
    return {...state, xAxis: {...state.xAxis, brushes}};
  };

  // Strip out min/maxRevision/Timestamp and ensure a consistent key order.
  ChartTimeseries.stringifyDescriptor = lineDescriptor => JSON.stringify([
    lineDescriptor.suites,
    lineDescriptor.measurement,
    lineDescriptor.bots,
    lineDescriptor.cases,
    lineDescriptor.statistic,
    lineDescriptor.buildType,
  ]);

  // Remove empty elements.
  function filterTimeseriesesByLine(timeseriesesByLine) {
    const result = [];
    for (const {lineDescriptor, timeserieses} of timeseriesesByLine) {
      const filteredTimeserieses = timeserieses.filter(ts => ts);
      if (filteredTimeserieses.length === 0) continue;
      result.push({lineDescriptor, timeserieses: filteredTimeserieses});
    }
    return result;
  }

  // Each lineDescriptor may require data from one or more fetchDescriptors.
  // Fetch one or more fetchDescriptors per line, batch the readers, collate the
  // data.
  // Yields {timeseriesesByLine: [{lineDescriptor, timeserieses}], errors}.
  async function* generateTimeseries(
      lineDescriptors, revisions, levelOfDetail) {
    const readers = [];
    const timeseriesesByLine = [];

    for (const lineDescriptor of lineDescriptors) {
      const fetchDescriptors = ChartTimeseries.createFetchDescriptors(
          lineDescriptor, levelOfDetail);
      const timeserieses = new Array(fetchDescriptors.length);
      timeseriesesByLine.push({lineDescriptor, timeserieses});

      for (let fetchIndex = 0; fetchIndex < fetchDescriptors.length;
        ++fetchIndex) {
        readers.push((async function* () {
          const request = new cp.TimeseriesRequest({
            ...fetchDescriptors[fetchIndex],
            ...revisions,
          });

          for await (const timeseries of request.reader()) {
            // Replace any previous timeseries from this reader.
            // TimeseriesCacheRequest merges results progressively.
            timeserieses[fetchIndex] = timeseries;
            yield {/* Pump BatchIterator. See timeseriesesByLine. */};
          }
        })());
      }
    }

    // Use BatchIterator only to batch result *events*, not the results
    // themselves. Manually collate results above to keep track of which line
    // and request go with each timeseries.

    for await (const {results, errors} of new cp.BatchIterator(readers)) {
      const filtered = filterTimeseriesesByLine(timeseriesesByLine);
      yield {timeseriesesByLine: filtered, errors};
    }
  }

  ChartTimeseries.loadLines = statePath => async(dispatch, getState) => {
    const state = Polymer.Path.get(getState(), statePath);
    const generator = generateTimeseries(
        state.lineDescriptors.slice(0, ChartTimeseries.MAX_LINES),
        {minRevision: state.minRevision, maxRevision: state.maxRevision},
        state.levelOfDetail);
    for await (const {timeseriesesByLine, errors} of generator) {
      if (!cp.layoutTimeseries.isReady) await cp.layoutTimeseries.readyPromise;

      const state = Polymer.Path.get(getState(), statePath);
      if (!state) {
        // This chart is no longer in the redux store.
        return;
      }

      dispatch({
        type: ChartTimeseries.reducers.layout.name,
        timeseriesesByLine,
        statePath,
      });
      ChartTimeseries.actions.measureYTicks(statePath)(dispatch, getState);
    }
  };

  // A lineDescriptor may require data from multiple timeseries.
  // A lineDescriptor may specify multiple suites, bots, and cases.
  // A fetchDescriptor may specify exactly one suite, one bot, and zero or one
  // case.
  ChartTimeseries.createFetchDescriptors = (lineDescriptor, levelOfDetail) => {
    let cases = lineDescriptor.cases;
    if (cases.length === 0) cases = [undefined];
    const fetchDescriptors = [];
    for (const suite of lineDescriptor.suites) {
      for (const bot of lineDescriptor.bots) {
        for (const cas of cases) {
          fetchDescriptors.push({
            suite,
            bot,
            measurement: lineDescriptor.measurement,
            case: cas,
            statistic: lineDescriptor.statistic,
            buildType: lineDescriptor.buildType,
            levelOfDetail,
          });
        }
      }
    }
    return fetchDescriptors;
  };

  // Improvement alerts display thumbs-up icons. Regression alerts display error
  // icons.
  function getIcon(datum) {
    if (!datum.alert) return {};
    if (datum.alert.improvement) {
      return {
        icon: 'cp:thumb-up',
        iconColor: 'var(--improvement-color, green)',
      };
    }
    return {
      icon: 'cp:error',
      iconColor: datum.alert.bugId ?
        'var(--neutral-color-dark, grey)' : 'var(--error-color, red)',
    };
  }

  ChartTimeseries.aggregateTimeserieses = (
      lineDescriptor, timeserieses, levelOfDetail, range) => {
    const isXY = (levelOfDetail === cp.LEVEL_OF_DETAIL.XY);
    const lineData = [];
    const iter = new cp.TimeseriesMerger(timeserieses, range);
    for (const [x, datum] of iter) {
      const icon = isXY ? {} : getIcon(datum);
      lineData.push({
        datum, x, y: datum[lineDescriptor.statistic], ...icon,
      });
    }

    lineData.sort((a, b) => a.x - b.x);
    return lineData;
  };

  cp.ElementBase.register(ChartTimeseries);

  return {ChartTimeseries};
});
