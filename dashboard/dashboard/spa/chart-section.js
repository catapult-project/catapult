/* Copyright 2019 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';
tr.exportTo('cp', () => {
  class ChartSection extends cp.ElementBase {
    ready() {
      super.ready();
      this.scrollIntoView(true);
    }

    isLoading_(isLoading, minimapLayout, chartLayout) {
      if (isLoading) return true;
      if (minimapLayout && minimapLayout.isLoading) return true;
      if (chartLayout && chartLayout.isLoading) return true;
      return false;
    }

    isLegendOpen_(isExpanded, legend, histograms) {
      return isExpanded && !this.isEmpty_(legend) && this.isEmpty_(histograms);
    }

    async onMatrixChange_(event) {
      if (!this.descriptor) return;
      await this.dispatch('maybeLoadTimeseries', this.statePath);
    }

    async onStatisticSelect_(event) {
      await this.dispatch('maybeLoadTimeseries', this.statePath);
    }

    async onTitleKeyup_(event) {
      await this.dispatch(Redux.UPDATE(this.statePath, {
        title: event.target.value,
        isTitleCustom: true,
      }));
    }

    async onCopy_(event) {
      this.dispatchEvent(new CustomEvent('new-chart', {
        bubbles: true,
        composed: true,
        detail: {
          options: {
            clone: true,
            minRevision: this.minRevision,
            maxRevision: this.maxRevision,
            title: this.title,
            parameters: {
              suites: [...this.descriptor.suite.selectedOptions],
              suitesAggregated: this.descriptor.suite.isAggregated,
              measurements: [...this.descriptor.measurement.selectedOptions],
              bots: [...this.descriptor.bot.selectedOptions],
              botsAggregated: this.descriptor.bot.isAggregated,
              cases: [...this.descriptor.case.selectedOptions],
              casesAggregated: this.descriptor.case.isAggregated,
              statistics: [...this.statistic.selectedOptions],
            },
          },
        },
      }));
    }

    onClose_(event) {
      this.dispatchEvent(new CustomEvent('close-section', {
        bubbles: true,
        composed: true,
        detail: {sectionId: this.sectionId},
      }));
    }

    onLegendMouseOver_(event) {
      this.dispatch('legendMouseOver', this.statePath,
          event.detail.lineDescriptor);
    }

    onLegendMouseOut_(event) {
      this.dispatch('legendMouseOut', this.statePath);
    }

    onLegendLeafClick_(event) {
      this.dispatch('legendLeafClick', this.statePath,
          event.detail.lineDescriptor);
    }

    async onLegendClick_(event) {
      this.dispatch('legendClick', this.statePath);
    }

    onLineCountChange_() {
      this.dispatch('updateLegendColors', this.statePath);
    }
  }

  ChartSection.State = {
    sectionId: options => options.sectionId || tr.b.GUID.allocateSimple(),
    ...cp.ChartCompound.State,
    descriptor: options => {
      const params = options.parameters || {};

      // Support old spelling of some parameters including 'test'.
      if (params.testSuites || params.testCases) {
        params.suites = params.testSuites;
        params.suitesAggregated = params.testSuitesAggregated;
        params.cases = params.testCases;
        params.casesAggregated = params.testCasesAggregated;
      }

      return cp.TimeseriesDescriptor.buildState({
        suite: {
          selectedOptions: params.suites,
          isAggregated: params.suitesAggregated,
        },
        measurement: {
          selectedOptions: params.measurements,
        },
        bot: {
          selectedOptions: params.bots,
          isAggregated: params.botsAggregated,
        },
        case: {
          selectedOptions: params.cases,
          isAggregated: params.casesAggregated,
        },
      });
    },
    title: options => options.title || '',
    isTitleCustom: options => false,
    legend: options => undefined,
    selectedLineDescriptorHash: options => options.selectedLineDescriptorHash,
    isLoading: options => false,
    statistic: options => {
      let selectedOptions = ['avg'];
      if (options) {
        if (options.statistics) selectedOptions = options.statistics;
        if (options.parameters && options.parameters.statistics) {
          // Support old format.
          selectedOptions = options.parameters.statistics;
        }
      }
      return cp.MenuInput.buildState({
        label: 'Statistics',
        required: true,
        selectedOptions,
        options: ['avg', 'std', 'count', 'min', 'max', 'sum'],
      });
    },
    histograms: options => undefined,
  };

  ChartSection.buildState = options => cp.buildState(
      ChartSection.State, options);

  ChartSection.properties = {
    ...cp.buildProperties('state', ChartSection.State),
    ...cp.buildProperties('linkedState', {
      // ChartSection only needs the linkedStatePath property to forward to
      // ChartCompound.
    }),
  };

  ChartSection.actions = {
    maybeLoadTimeseries: statePath => async(dispatch, getState) => {
      // If the first 3 components are filled, then load the timeseries.
      const state = Polymer.Path.get(getState(), statePath);
      if (state.descriptor.suite.selectedOptions.length &&
          state.descriptor.measurement.selectedOptions.length &&
          state.statistic.selectedOptions.length) {
        ChartSection.actions.loadTimeseries(statePath)(dispatch, getState);
      } else {
        dispatch(Redux.UPDATE(statePath, {lineDescriptors: []}));
      }
    },

    loadTimeseries: statePath => async(dispatch, getState) => {
      dispatch({type: ChartSection.reducers.loadTimeseries.name, statePath});

      const state = Polymer.Path.get(getState(), statePath);
      if (state.selectedLineDescriptorHash) {
        // Restore from URL.
        for (const lineDescriptor of state.lineDescriptors) {
          const lineDescriptorHash = await cp.sha(
              cp.ChartTimeseries.stringifyDescriptor(lineDescriptor));
          if (!lineDescriptorHash.startsWith(
              state.selectedLineDescriptorHash)) {
            continue;
          }
          dispatch(Redux.UPDATE(statePath, {
            lineDescriptors: [lineDescriptor],
          }));
          break;
        }
      }
    },

    legendMouseOver: (statePath, lineDescriptor) =>
      async(dispatch, getState) => {
        const chartPath = statePath + '.chartLayout';
        const state = Polymer.Path.get(getState(), statePath);
        lineDescriptor = JSON.stringify(lineDescriptor);
        for (let lineIndex = 0; lineIndex < state.chartLayout.lines.length;
          ++lineIndex) {
          const line = state.chartLayout.lines[lineIndex];
          if (JSON.stringify(line.descriptor) === lineDescriptor) {
            dispatch(Redux.CHAIN(
                {
                  type: cp.ChartTimeseries.reducers.mouseYTicks.name,
                  statePath: chartPath,
                  line,
                },
                {
                  type: cp.ChartBase.reducers.boldLine.name,
                  statePath: chartPath,
                  lineIndex,
                },
            ));
            break;
          }
        }
      },

    legendMouseOut: statePath => async(dispatch, getState) => {
      const chartPath = statePath + '.chartLayout';
      dispatch(Redux.CHAIN(
          {
            type: cp.ChartTimeseries.reducers.mouseYTicks.name,
            statePath: chartPath,
          },
          {
            type: cp.ChartBase.reducers.boldLine.name,
            statePath: chartPath,
          },
      ));
    },

    legendLeafClick: (statePath, lineDescriptor) =>
      async(dispatch, getState) => {
        dispatch({
          type: ChartSection.reducers.selectLine.name,
          statePath,
          lineDescriptor,
          selectedLineDescriptorHash: await cp.sha(
              cp.ChartTimeseries.stringifyDescriptor(lineDescriptor)),
        });
      },

    legendClick: statePath => async(dispatch, getState) => {
      dispatch({
        type: ChartSection.reducers.deselectLine.name,
        statePath,
      });
    },

    updateLegendColors: statePath => async(dispatch, getState) => {
      const state = Polymer.Path.get(getState(), statePath);
      if (!state || !state.legend) return;
      dispatch({
        type: ChartSection.reducers.updateLegendColors.name,
        statePath,
      });
    },
  };

  ChartSection.reducers = {
    loadTimeseries: (state, action, rootState) => {
      const title = ChartSection.computeTitle(state);
      const legend = ChartSection.buildLegend(
          ChartSection.parameterMatrix(state));
      const parameterMatrix = ChartSection.parameterMatrix(state);
      const lineDescriptors = cp.TimeseriesDescriptor.createLineDescriptors(
          parameterMatrix);
      return {
        ...state,
        title,
        legend,
        lineDescriptors,
      };
    },

    selectLine: (state, action, rootState) => {
      if (state.selectedLineDescriptorHash ===
          action.selectedLineDescriptorHash) {
        return ChartSection.reducers.deselectLine(state, action, rootState);
      }
      return {
        ...state,
        lineDescriptors: [action.lineDescriptor],
        selectedLineDescriptorHash: action.selectedLineDescriptorHash,
      };
    },

    deselectLine: (state, action, rootState) => {
      const parameterMatrix = ChartSection.parameterMatrix(state);
      const lineDescriptors = cp.TimeseriesDescriptor.createLineDescriptors(
          parameterMatrix);
      return {
        ...state,
        lineDescriptors,
        selectedLineDescriptorHash: undefined,
      };
    },

    updateLegendColors: (state, action, rootState) => {
      if (!state.legend) return state;
      const colorMap = new Map();
      for (const line of state.chartLayout.lines) {
        colorMap.set(cp.ChartTimeseries.stringifyDescriptor(
            line.descriptor), line.color);
      }
      function handleLegendEntry(entry) {
        if (entry.children) {
          return {...entry, children: entry.children.map(handleLegendEntry)};
        }
        const color = colorMap.get(cp.ChartTimeseries.stringifyDescriptor(
            entry.lineDescriptor)) || 'grey';
        return {...entry, color};
      }
      return {...state, legend: state.legend.map(handleLegendEntry)};
    },
  };

  ChartSection.newStateOptionsFromQueryParams = routeParams => {
    return {
      parameters: {
        suites: routeParams.getAll('suite') || routeParams.getAll('testSuite'),
        suitesAggregated: routeParams.get('aggSuites') !== null ||
          routeParams.get('splitSuites') === null,
        measurements: routeParams.getAll('measurement'),
        bots: routeParams.getAll('bot'),
        botsAggregated: routeParams.get('splitBots') === null,
        cases: routeParams.getAll('case'),
        caseTags: routeParams.getAll('caseTag'),
        casesAggregated: routeParams.get('splitCases') === null,
        statistics: routeParams.get('stat') ? routeParams.getAll('stat') :
          ['avg'],
      },
      isExpanded: !routeParams.has('compact'),
      minRevision: parseInt(routeParams.get('minRev')) || undefined,
      maxRevision: parseInt(routeParams.get('maxRev')) || undefined,
      selectedRelatedTabName: routeParams.get('spark') || '',
      mode: routeParams.get('mode') || undefined,
      fixedXAxis: !routeParams.has('natural'),
      zeroYAxis: routeParams.has('zeroY'),
      selectedLineDescriptorHash: routeParams.get('select'),
    };
  };

  function legendEntry(label, children) {
    if (children.length === 1) {
      return {...children[0], label};
    }
    return {label, children};
  }

  ChartSection.buildLegend = ({
    suiteses, measurements, botses, caseses, statistics,
    buildTypes,
  }) => {
    // Return [{label, children: [{label, lineDescriptor, color}]}}]
    let legendItems = suiteses.map(suites =>
      legendEntry(suites[0], measurements.map(measurement =>
        legendEntry(measurement, botses.map(bots =>
          legendEntry(bots[0], caseses.map(cases =>
            legendEntry(cases[0], statistics.map(statistic =>
              legendEntry(statistic, buildTypes.map(buildType => {
                const lineDescriptor = {
                  suites,
                  measurement,
                  bots,
                  cases,
                  statistic,
                  buildType,
                };
                return {
                  label: buildType,
                  lineDescriptor,
                  color: '',
                };
              })))))))))));

    if (legendItems.length === 1) legendItems = legendItems[0].children;

    function stripSharedPrefix(items) {
      if (!items || !items.length) return;
      let sharedPrefixLength = items[0].label.length;
      for (let i = 1; i < items.length; ++i) {
        for (let c = 0; c < sharedPrefixLength; ++c) {
          if (items[0].label[c] === items[i].label[c]) continue;
          sharedPrefixLength = c - 1;
          break;
        }
      }
      sharedPrefixLength = items[0].label.slice(
          0, sharedPrefixLength + 1).lastIndexOf(':');
      if (sharedPrefixLength > 0) {
        for (let i = 0; i < items.length; ++i) {
          items[i].label = items[i].label.slice(sharedPrefixLength + 1);
        }
      }

      for (const child of items) {
        if (!child.children) continue;
        stripSharedPrefix(child.children);
      }
    }
    stripSharedPrefix(legendItems);

    return legendItems;
  };

  ChartSection.parameterMatrix = state => {
    const descriptor = cp.TimeseriesDescriptor.getParameterMatrix(
        state.descriptor.suite, state.descriptor.measurement,
        state.descriptor.bot, state.descriptor.case);
    return {
      suiteses: descriptor.suites,
      measurements: descriptor.measurements,
      botses: descriptor.bots,
      caseses: descriptor.cases,
      statistics: state.statistic.selectedOptions,
      buildTypes: ['test'],
    };
  };

  /*
  Don't change the session state (aka options) format!
  {
    parameters: {
      suites: Array<string>,
      suitesAggregated: boolean,
      measurements: Array<string>,
      bots: Array<string>,
      botsAggregated: boolean,
      cases: Array<string>
      casesAggregated: boolean,
      statistics: Array<string>,
    },
    isLinked: boolean,
    isExpanded: boolean,
    title: string,
    minRevision: number,
    maxRevision: number,
    zeroYAxis: boolean,
    fixedXAxis: boolean,
    mode: string,
    selectedRelatedTabName: string,
    selectedLineDescriptorHash: string,
  }

  This format is slightly different from ChartSection.State, which has
  `descriptor` (which does not include statistics) instead of `parameters`
  (which does include statistics).
  */

  ChartSection.getSessionState = state => {
    return {
      parameters: {
        suites: state.descriptor.suite.selectedOptions,
        suitesAggregated: state.descriptor.suite.isAggregated,
        measurements: state.descriptor.measurement.selectedOptions,
        bots: state.descriptor.bot.selectedOptions,
        botsAggregated: state.descriptor.bot.isAggregated,
        cases: state.descriptor.case.selectedOptions,
        casesAggregated: state.descriptor.case.isAggregated,
        statistics: state.statistic.selectedOptions,
      },
      isLinked: state.isLinked,
      isExpanded: state.isExpanded,
      title: state.title,
      minRevision: state.minRevision,
      maxRevision: state.maxRevision,
      zeroYAxis: state.zeroYAxis,
      fixedXAxis: state.fixedXAxis,
      mode: state.mode,
      selectedRelatedTabName: state.selectedRelatedTabName,
      selectedLineDescriptorHash: state.selectedLineDescriptorHash,
    };
  };

  ChartSection.getRouteParams = state => {
    const allBotsSelected = state.descriptor.bot.selectedOptions.length ===
        cp.OptionGroup.countDescendents(state.descriptor.bot.options);

    if (state.descriptor.suite.selectedOptions.length > 2 ||
        state.descriptor.case.selectedOptions.length > 2 ||
        state.descriptor.measurement.selectedOptions.length > 2 ||
        ((state.descriptor.bot.selectedOptions.length > 2) &&
         !allBotsSelected)) {
      return undefined;
    }

    const routeParams = new URLSearchParams();
    for (const suite of state.descriptor.suite.selectedOptions) {
      routeParams.append('suite', suite);
    }
    if (!state.descriptor.suite.isAggregated) {
      routeParams.set('splitSuites', '');
    }
    for (const measurement of state.descriptor.measurement.selectedOptions) {
      routeParams.append('measurement', measurement);
    }
    if (allBotsSelected) {
      routeParams.set('bot', '*');
    } else {
      for (const bot of state.descriptor.bot.selectedOptions) {
        routeParams.append('bot', bot);
      }
    }
    if (!state.descriptor.bot.isAggregated) {
      routeParams.set('splitBots', '');
    }
    for (const cas of state.descriptor.case.selectedOptions) {
      routeParams.append('case', cas);
    }
    for (const tag of state.descriptor.case.tags.selectedOptions) {
      routeParams.append('caseTag', tag);
    }
    if (!state.descriptor.case.isAggregated) {
      routeParams.set('splitCases', '');
    }
    const statistics = state.statistic.selectedOptions;
    if (statistics.length > 1 || statistics[0] !== 'avg') {
      for (const statistic of statistics) {
        routeParams.append('stat', statistic);
      }
    }
    if (state.minRevision !== undefined) {
      routeParams.set('minRev', state.minRevision);
    }
    if (state.maxRevision !== undefined) {
      routeParams.set('maxRev', state.maxRevision);
    }
    if (state.mode !== cp.MODE.NORMALIZE_UNIT) {
      routeParams.set('mode', state.mode);
    }
    if (state.selectedLineDescriptorHash) {
      routeParams.set('select', state.selectedLineDescriptorHash.slice(0, 6));
    }
    if (!state.fixedXAxis) {
      routeParams.set('natural', '');
    }
    if (state.zeroYAxis) {
      routeParams.set('zeroY', '');
    }
    if (state.selectedRelatedTabName) {
      routeParams.set('spark', state.selectedRelatedTabName);
    }
    if (!state.isExpanded) {
      routeParams.set('compact', '');
    }
    return routeParams;
  };

  ChartSection.computeTitle = state => {
    if (state.isTitleCustom) return state.title;
    let title = state.descriptor.measurement.selectedOptions.join(', ');
    if (state.descriptor.bot.selectedOptions.length > 0 &&
        state.descriptor.bot.selectedOptions.length < 4) {
      title += ' on ' + state.descriptor.bot.selectedOptions.join(', ');
    }
    if (state.descriptor.case.selectedOptions.length > 0 &&
        state.descriptor.case.selectedOptions.length < 4) {
      title += ' for ' + state.descriptor.case.selectedOptions.join(', ');
    }
    return title;
  };

  ChartSection.isEmpty = state => {
    if (!state) return true;
    if (!state.descriptor) return true;
    if (!state.descriptor.suite) return true;
    if (!state.descriptor.measurement) return true;
    if (!state.descriptor.bot) return true;
    if (!state.descriptor.case) return true;
    if (state.descriptor.suite.selectedOptions.length === 0 &&
        state.descriptor.measurement.selectedOptions.length === 0 &&
        state.descriptor.bot.selectedOptions.length === 0 &&
        state.descriptor.case.selectedOptions.length === 0) {
      return true;
    }
    return false;
  };

  ChartSection.matchesOptions = (state, options) => {
    if (!options ||
        !state ||
        !state.descriptor ||
        !state.descriptor.suite ||
        !state.descriptor.measurement ||
        !state.descriptor.bot ||
        !state.descriptor.case) {
      return false;
    }
    if (options.mode !== undefined &&
        options.mode !== state.mode) {
      return false;
    }
    if (options.isLinked !== undefined &&
        options.isLinked !== state.isLinked) {
      return false;
    }
    if (options.zeroYAxis !== undefined &&
        options.zeroYAxis !== state.zeroYAxis) {
      return false;
    }
    if (options.fixedXAxis !== undefined &&
        options.fixedXAxis !== state.fixedXAxis) {
      return false;
    }
    if (options.parameters) {
      if (options.parameters.suites && !tr.b.setsEqual(
          new Set(options.parameters.suites),
          new Set(state.descriptor.suite.selectedOptions))) {
        return false;
      }
      if (options.parameters.measurements && !tr.b.setsEqual(
          new Set(options.parameters.measurements),
          new Set(state.descriptor.measurement.selectedOptions))) {
        return false;
      }
      if (options.parameters.bots && !tr.b.setsEqual(
          new Set(options.parameters.bots),
          new Set(state.descriptor.bot.selectedOptions))) {
        return false;
      }
      if (options.parameters.cases && !tr.b.setsEqual(
          new Set(options.parameters.cases),
          new Set(state.descriptor.case.selectedOptions))) {
        return false;
      }
      if (options.parameters.suitesAggregated !== undefined &&
          options.parameters.suitesAggregated !=
          state.descriptor.suite.isAggregated) {
        return false;
      }
      if (options.parameters.botsAggregated !== undefined &&
          options.parameters.botsAggregated !=
          state.descriptor.bot.isAggregated) {
        return false;
      }
      if (options.parameters.casesAggregated !== undefined &&
          options.parameters.casesAggregated !=
          state.descriptor.case.isAggregated) {
        return false;
      }
      if (options.parameters.statistics && !tr.b.setsEqual(
          new Set(options.parameters.statistics),
          new Set(state.statistic.selectedOptions))) {
        return false;
      }
    }
    if (options.minRevision !== undefined &&
        options.minRevision !== state.minRevision) {
      return false;
    }
    if (options.maxRevision !== undefined &&
        options.maxRevision !== state.maxRevision) {
      return false;
    }
    if (options.selectedRelatedTabName !== undefined &&
        options.selectedRelatedTabName !== state.selectedRelatedTabName) {
      return false;
    }
    return true;
  };

  cp.ElementBase.register(ChartSection);

  return {ChartSection};
});
