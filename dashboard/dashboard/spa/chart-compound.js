/* Copyright 2019 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';
tr.exportTo('cp', () => {
  const MS_PER_DAY = tr.b.convertUnit(
      1, tr.b.UnitScale.TIME.DAY, tr.b.UnitScale.TIME.MILLI_SEC);
  const MS_PER_MONTH = tr.b.convertUnit(
      1, tr.b.UnitScale.TIME.MONTH, tr.b.UnitScale.TIME.MILLI_SEC);

  /**
   * ChartCompound synchronizes revision ranges and axis properties between a
   * minimap and a main chart, and among any number of other linked charts.
   */
  class ChartCompound extends cp.ElementBase {
    hideOptions_(minimapLayout) {
      return this.$.minimap.showPlaceholder(
          (minimapLayout && minimapLayout.isLoading),
          (minimapLayout ? minimapLayout.lines : []));
    }

    fewEnoughLines_(lineDescriptors) {
      return lineDescriptors &&
          lineDescriptors.length < cp.ChartTimeseries.MAX_LINES;
    }

    async onGetTooltip_(event) {
      const p = event.detail.nearestPoint;
      this.dispatch(Redux.UPDATE(this.statePath, {
        cursorRevision: p.x,
        cursorScalar: new tr.b.Scalar(p.datum.unit, p.y),
      }));
      // Don't reset cursor on mouseLeave. Allow users to scroll through
      // sparklines.
    }

    async onMenuKeyup_(event) {
      if (event.key === 'Escape') {
        await this.dispatch(Redux.UPDATE(this.statePath, {
          isShowingOptions: false,
        }));
      }
    }

    async onMenuBlur_(event) {
      if (cp.isElementChildOf(event.relatedTarget, this.$.options_container)) {
        return;
      }
      await this.dispatch(Redux.UPDATE(this.statePath, {
        isShowingOptions: false,
      }));
    }

    async onOptionsToggle_(event) {
      await this.dispatch(Redux.TOGGLE(this.statePath + '.isShowingOptions'));
    }

    async onMinimapBrush_(event) {
      if (event.detail.sourceEvent.detail.state !== 'end') return;
      await this.dispatch({
        type: ChartCompound.reducers.brushMinimap.name,
        statePath: this.statePath,
      });
      if (this.isLinked) {
        await this.dispatch('updateLinkedRevisions', this.linkedStatePath,
            this.minRevision, this.maxRevision);
      }
    }

    async onToggleLinked_(event) {
      await this.dispatch('toggleLinked', this.statePath, this.linkedStatePath);
    }

    async onToggleZeroYAxis_(event) {
      await this.dispatch(Redux.TOGGLE(this.statePath + '.zeroYAxis'));
      await this.dispatch('load', this.statePath);
      if (this.isLinked) {
        await this.dispatch(Redux.TOGGLE(
            this.linkedStatePath + '.linkedZeroYAxis'));
      }
    }

    async onToggleFixedXAxis_(event) {
      await this.dispatch(Redux.TOGGLE(this.statePath + '.fixedXAxis'));
      if (this.isLinked) {
        await this.dispatch(Redux.TOGGLE(
            this.linkedStatePath + '.linkedFixedXAxis'));
      }
      await this.dispatch('load', this.statePath);
    }

    observeLineDescriptors_(newLineDescriptors, oldLineDescriptors) {
      // Sometimes polymer calls some observers even when nothing changed.
      // Ignore them.
      if (newLineDescriptors === oldLineDescriptors) return;
      this.dispatch('load', this.statePath);
    }

    observeLinkedCursor_() {
      if (!this.isLinked) return;
      this.dispatch(Redux.UPDATE(this.statePath, {
        cursorRevision: this.linkedCursorRevision,
        cursorScalar: this.linkedCursorScalar,
      }));
    }

    observeLinkedRevisions_() {
      if (!this.isLinked) return;
      if (this.linkedMinRevision === this.minRevision &&
          this.linkedMaxRevision === this.maxRevision) {
        return;
      }
      this.dispatch(Redux.UPDATE(this.statePath, {
        minRevision: this.linkedMinRevision,
        maxRevision: this.linkedMaxRevision,
      }));
      this.dispatch('load', this.statePath);
    }

    observeLinkedMode_() {
      if (!this.isLinked) return;
      if (this.mode === this.linkedMode) return;
      this.dispatch(Redux.UPDATE(this.statePath, {mode: this.linkedMode}));
      this.dispatch('load', this.statePath);
    }

    observeLinkedZeroYAxis_() {
      if (!this.isLinked) return;
      if (this.zeroYAxis === this.linkedZeroYAxis) return;
      this.dispatch(Redux.TOGGLE(this.statePath + '.zeroYAxis'));
      this.dispatch('load', this.statePath);
    }

    observeLinkedFixedXAxis_() {
      if (!this.isLinked) return;
      if (this.fixedXAxis === this.linkedFixedXAxis) return;
      this.dispatch(Redux.TOGGLE(this.statePath + '.fixedXAxis'));
      this.dispatch('load', this.statePath);
    }

    onModeChange_(event) {
      this.dispatch(Redux.UPDATE(this.statePath, {mode: event.detail.value}));
      this.dispatch('load', this.statePath);

      if (this.isLinked) {
        this.dispatch(Redux.UPDATE(this.linkedStatePath, {
          linkedMode: event.detail.value,
        }));
      }
    }

    observeChartLoading_(newLoading, oldLoading) {
      if (oldLoading && !newLoading) {
        this.dispatch({
          type: ChartCompound.reducers.updateStale.name,
          statePath: this.statePath,
        });
      }
    }

    // The `cursorRevision` and `cursorScalar` properties are set either from
    // onGetTooltip_ as the user mouses around this main chart, or from
    // observeLinkedCursor_ as the user mouses around the main chart in a
    // different chart-compound.
    observeCursor_(cursorRevision, cursorScalar) {
      this.dispatch({
        type: ChartCompound.reducers.setCursors.name,
        statePath: this.statePath,
      });
      if (this.isLinked &&
          (this.cursorRevision !== this.linkedCursorRevision ||
           this.cursorScalar !== this.linkedCursorScalar)) {
        this.dispatch(Redux.UPDATE(this.linkedStatePath, {
          linkedCursorRevision: this.cursorRevision,
          linkedCursorScalar: this.cursorScalar,
        }));
      }
    }
  }

  ChartCompound.State = {
    lineDescriptors: options => [],
    isExpanded: options => options.isExpanded !== false,
    minimapLayout: options => {
      const minimapLayout = {
        ...cp.ChartTimeseries.buildState({
          levelOfDetail: cp.LEVEL_OF_DETAIL.XY,
        }),
        graphHeight: 40,
      };
      minimapLayout.xAxis.height = 15;
      minimapLayout.yAxis.width = 50;
      minimapLayout.yAxis.generateTicks = false;
      return minimapLayout;
    },
    chartLayout: options => {
      const chartLayout = cp.ChartTimeseries.buildState({
        levelOfDetail: cp.LEVEL_OF_DETAIL.ANNOTATIONS,
        showTooltip: true,
      });
      chartLayout.xAxis.height = 15;
      chartLayout.xAxis.showTickLines = true;
      chartLayout.yAxis.width = 50;
      chartLayout.yAxis.showTickLines = true;
      return chartLayout;
    },
    isShowingOptions: options => false,
    isLinked: options => options.isLinked !== false,
    cursorRevision: options => 0,
    cursorScalar: options => undefined,
    minRevision: options => options.minRevision,
    maxRevision: options => options.maxRevision,
    mode: options => options.mode || cp.MODE.NORMALIZE_UNIT,
    zeroYAxis: options => options.zeroYAxis || false,
    fixedXAxis: options => options.fixedXAxis !== false,
  };

  ChartCompound.buildState = options =>
    cp.buildState(ChartCompound.State, options);

  ChartCompound.observers = [
    'observeLinkedCursor_(linkedCursorRevision, linkedCursorScalar)',
    'observeLinkedRevisions_(linkedMinRevision, linkedMaxRevision)',
    'observeLinkedMode_(linkedMode)',
    'observeLinkedZeroYAxis_(linkedZeroYAxis)',
    'observeLinkedFixedXAxis_(linkedFixedXAxis)',
    'observeCursor_(cursorRevision, cursorScalar)',
  ];

  ChartCompound.LinkedState = {
    linkedCursorRevision: options => undefined,
    linkedCursorScalar: options => undefined,
    linkedMinRevision: options => options.minRevision,
    linkedMaxRevision: options => options.maxRevision,
    linkedMode: options => options.mode || cp.MODE.NORMALIZE_UNIT,
    linkedZeroYAxis: options => options.zeroYAxis || false,
    linkedFixedXAxis: options => options.fixedXAxis !== false,
  };

  ChartCompound.properties = {
    ...cp.buildProperties('state', ChartCompound.State),
    ...cp.buildProperties('linkedState', ChartCompound.LinkedState),
    isChartLoading: {
      computed: 'identity_(chartLayout.isLoading)',
      observer: 'observeChartLoading_',
    },
  };

  ChartCompound.properties.lineDescriptors.observer = 'observeLineDescriptors_';

  ChartCompound.actions = {
    updateLinkedRevisions: (
        linkedStatePath, linkedMinRevision, linkedMaxRevision) =>
      async(dispatch, getState) => {
        const state = Polymer.Path.get(getState(), linkedStatePath);
        if (linkedMinRevision === state.linkedMinRevision &&
            linkedMaxRevision === state.linkedMaxRevision) {
          return;
        }
        dispatch(Redux.UPDATE(linkedStatePath, {
          linkedMinRevision, linkedMaxRevision,
        }));
      },

    toggleLinked: (statePath, linkedStatePath) => async(dispatch, getState) => {
      dispatch({
        type: ChartCompound.reducers.toggleLinked.name,
        statePath,
        linkedStatePath,
      });
      ChartCompound.actions.load(statePath)(dispatch, getState);
    },

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
    load: statePath => async(dispatch, getState) => {
      const state = Polymer.Path.get(getState(), statePath);
      if (!state || !state.lineDescriptors ||
          state.lineDescriptors.length === 0) {
        dispatch(Redux.CHAIN(
            Redux.UPDATE(`${statePath}.minimapLayout`, {lineDescriptors: []}),
            Redux.UPDATE(`${statePath}.chartLayout`, {lineDescriptors: []}),
        ));
        return;
      }

      const {firstNonEmptyLineDescriptor, timeserieses} =
        await ChartCompound.findFirstNonEmptyLineDescriptor(
            state.lineDescriptors, `${statePath}.minimapLayout`, dispatch,
            getState);

      const firstRevision = ChartCompound.findFirstRevision(timeserieses);
      const lastRevision = ChartCompound.findLastRevision(timeserieses);
      const minRevision = ChartCompound.computeMinRevision(
          state.minRevision, timeserieses, firstRevision, lastRevision);
      const maxRevision = ChartCompound.computeMaxRevision(
          state.maxRevision, firstRevision, lastRevision);

      const minimapLineDescriptors = [];
      if (firstNonEmptyLineDescriptor) {
        minimapLineDescriptors.push({...firstNonEmptyLineDescriptor});
      }

      // Never set zeroYAxis on the minimap. It's too short to waste space.
      dispatch(Redux.UPDATE(`${statePath}.minimapLayout`, {
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

      dispatch(Redux.UPDATE(`${statePath}.chartLayout`, {
        lineDescriptors,
        minRevision,
        maxRevision,
        brushRevisions: [],
        fixedXAxis: state.fixedXAxis,
        mode: state.mode,
        zeroYAxis: state.zeroYAxis,
      }));
    },
  };

  ChartCompound.reducers = {
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
          minimapXPct = tr.b.findClosestElementInSortedArray(
              state.minimapLayout.lines[0].data,
              d => d.x,
              state.cursorRevision).xPct + '%';

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
        if (state.mode === cp.MODE.NORMALIZE_UNIT) {
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
        const linkedState = Polymer.Path.get(rootState, linkedStatePath);
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
        const index = tr.b.findLowIndexInSortedArray(
            state.minimapLayout.lines[0].data,
            datum => datum.xPct,
            parseFloat(brush.xPct));
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

      const now = new Date();
      const staleMs = window.IS_DEBUG ? 1 : MS_PER_DAY;
      const staleTimestamp = now - staleMs;
      let anyStale = false;
      const lines = state.chartLayout.lines.map(line => {
        const minDate = line.data[line.data.length - 1].datum.timestamp;
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
        return cp.setImmutable(line, `data.${line.data.length - 1}`, datum => {
          return {...datum, icon: 'cp:clock', iconColor};
        });
      });
      if (!anyStale) return state;
      return {...state, chartLayout: {...state.chartLayout, lines}};
    },
  };

  // Fetch data for lineDescriptors in order until the first non-empty line is
  // found.
  ChartCompound.findFirstNonEmptyLineDescriptor = async(
    lineDescriptors, refStatePath, dispatch, getState) => {
    for (const lineDescriptor of lineDescriptors) {
      const fetchDescriptors = cp.ChartTimeseries.createFetchDescriptors(
          lineDescriptor, cp.LEVEL_OF_DETAIL.XY);

      const results = await Promise.all(fetchDescriptors.map(
          async fetchDescriptor => {
            const reader = new cp.TimeseriesRequest(fetchDescriptor).reader();
            for await (const timeseries of reader) {
              return timeseries;
            }
          }));

      for (const timeseries of results) {
        if (!timeseries || !timeseries.length) continue;
        return {
          firstNonEmptyLineDescriptor: lineDescriptor,
          timeserieses: results,
        };
      }
    }

    return {
      timeserieses: [],
    };
  };

  ChartCompound.findFirstRevision = timeserieses => {
    const firstRevision = tr.b.math.Statistics.min(timeserieses.map(ts => {
      if (!ts) return Infinity;
      const datum = ts[0];
      if (datum === undefined) return Infinity;
      return datum.revision;
    }));
    if (firstRevision === Infinity) return undefined;
    return firstRevision;
  };

  ChartCompound.findLastRevision = timeserieses => {
    const lastRevision = tr.b.math.Statistics.max(timeserieses.map(ts => {
      if (!ts) return -Infinity;
      const datum = ts[ts.length - 1];
      if (datum === undefined) return -Infinity;
      return datum.revision;
    }));
    if (lastRevision === -Infinity) return undefined;
    return lastRevision;
  };

  ChartCompound.computeMinRevision = (
      minRevision, timeserieses, firstRevision, lastRevision) => {
    if (minRevision &&
        minRevision >= firstRevision &&
        minRevision < lastRevision) {
      return minRevision;
    }

    let closestTimestamp = Infinity;
    const minTimestampMs = new Date() - MS_PER_MONTH;
    for (const timeseries of timeserieses) {
      if (!timeseries || !timeseries.length) continue;
      const datum = tr.b.findClosestElementInSortedArray(
          timeseries, d => d.timestamp, minTimestampMs);
      if (!datum) continue;
      const timestamp = datum.timestamp;
      if (Math.abs(timestamp - minTimestampMs) <
          Math.abs(closestTimestamp - minTimestampMs)) {
        minRevision = datum.revision;
        closestTimestamp = timestamp;
      }
    }
    return minRevision;
  };

  ChartCompound.computeMaxRevision = (
      maxRevision, firstRevision, lastRevision) => {
    if (!maxRevision || maxRevision <= firstRevision) {
      return lastRevision;
    }
    return maxRevision;
  };

  cp.ElementBase.register(ChartCompound);

  return {ChartCompound};
});
