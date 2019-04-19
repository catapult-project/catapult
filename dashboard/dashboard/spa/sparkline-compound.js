/* Copyright 2019 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

export default class SparklineCompound extends cp.ElementBase {
  static get template() {
    const chartPath = Polymer.html([
      '[[statePath]].relatedTabs.[[tabIndex]].renderedSparklines.' +
      '[[sparklineIndex]].layout',
    ]);
    return Polymer.html`
      <style>
        .related_tab {
          background-color: var(--primary-color-light, lightblue);
          display: flex;
          flex-wrap: wrap;
          max-height: 380px;
          overflow: auto;
        }

        .related_tab:not(.iron-collapse-closed) {
          border: 2px solid var(--primary-color-dark, blue);
          border-top: none;
        }

        .sparkline_tile {
          background: var(--background-color);
          cursor: pointer;
          margin: 4px;
          width: 300px;
        }

        .sparkline_name {
          display: flex;
          justify-content: center;
          padding: 4px;
        }

        .sparkline_container {
          display: flex;
          flex-wrap: wrap;
          justify-content: center;
          width: 100%;
        }

        cp-tab-bar {
          border-bottom: 2px solid var(--primary-color-dark, blue);
        }
      </style>

      <template is="dom-if" if="[[!isEmpty_(relatedTabs)]]">
        <cp-tab-bar selected="[[selectedRelatedTabName]]">
          <template is="dom-repeat" items="[[relatedTabs]]" as="tab"
                                    index-as="tabIndex">
            <cp-tab name="[[tab.name]]" on-click="onRelatedTabClick_">
              [[tab.name]]
            </cp-tab>
          </template>
        </cp-tab-bar>

        <template is="dom-repeat" items="[[relatedTabs]]" as="tab"
                                  index-as="tabIndex">
          <iron-collapse
              opened="[[isEqual_(tab.name, selectedRelatedTabName)]]"
              class="related_tab">
            <div class="sparkline_container">
              <template is="dom-repeat" items="[[tab.renderedSparklines]]"
    as="sparkline" index-as="sparklineIndex">
                <div
                    class="sparkline_tile"
                    hidden$="[[hideTile_(sparkline)]]"
                    on-click="onSparklineClick_">
                  <div class="sparkline_name">[[sparkline.name]]</div>
                  <cp-loading loading$="[[sparkline.layout.isLoading]]">
                  </cp-loading>
                  <chart-timeseries state-path="${chartPath}">
                  </chart-timeseries>
                </div>
              </template>
            </div>
          </iron-collapse>
        </template>
      </template>
    `;
  }

  async onRelatedTabClick_(event) {
    this.dispatch('selectRelatedTab', this.statePath, event.model.tab.name);
  }

  hideTile_(sparkline) {
    return !sparkline.isLoading && this.isEmpty_(sparkline.layout.lines);
  }

  async onSparklineClick_(event) {
    this.dispatchEvent(new CustomEvent('new-chart', {
      bubbles: true,
      composed: true,
      detail: {options: event.model.sparkline.chartOptions},
    }));
  }

  observeRevisions_() {
    this.dispatch({
      type: SparklineCompound.reducers.updateSparklineRevisions.name,
      statePath: this.statePath,
    });
  }

  observeCursor_(cursorRevision, cursorScalar) {
    this.dispatch({
      type: SparklineCompound.reducers.setCursors.name,
      statePath: this.statePath,
    });
  }
}

SparklineCompound.State = {
  lineDescriptors: options => [],
  relatedTabs: options => [],
  selectedRelatedTabName: options => options.selectedRelatedTabName || '',
  cursorRevision: options => 0,
  cursorScalar: options => undefined,
  minRevision: options => options.minRevision,
  maxRevision: options => options.maxRevision,
};

SparklineCompound.buildState = options => cp.buildState(
    SparklineCompound.State, options);
SparklineCompound.properties = cp.buildProperties(
    'state', SparklineCompound.State);
SparklineCompound.observers = [
  'observeRevisions_(minRevision, maxRevision)',
  'observeCursor_(cursorRevision, cursorScalar)',
];

SparklineCompound.actions = {
  selectRelatedTab: (statePath, selectedRelatedTabName) =>
    async(dispatch, getState) => {
      const state = Polymer.Path.get(getState(), statePath);
      if (selectedRelatedTabName === state.selectedRelatedTabName) {
        selectedRelatedTabName = '';
      }

      const selectedRelatedTabIndex = state.relatedTabs.findIndex(tab =>
        tab.name === selectedRelatedTabName);
      if (selectedRelatedTabIndex >= 0 &&
          state.relatedTabs[selectedRelatedTabIndex].renderedSparklines ===
          undefined) {
        const path = `${statePath}.relatedTabs.${selectedRelatedTabIndex}`;
        const relatedTab = state.relatedTabs[selectedRelatedTabIndex];
        dispatch(Redux.UPDATE(path, {
          renderedSparklines: relatedTab.sparklines,
        }));
      }

      dispatch(Redux.UPDATE(statePath, {selectedRelatedTabName}));
    },
};

function createSparkline(name, sparkLayout, revisions, matrix) {
  const lineDescriptors = cp.TimeseriesDescriptor.createLineDescriptors(
      matrix);
  if (lineDescriptors.length === 1) {
    lineDescriptors.push({
      ...lineDescriptors[0],
      buildType: 'ref',
    });
  }

  return {
    name: cp.breakWords(name),
    chartOptions: {
      parameters: parametersFromMatrix(matrix),
      ...revisions,
    },
    layout: {
      ...sparkLayout,
      ...revisions,
      lineDescriptors,
    },
  };
}

function parametersFromMatrix(matrix) {
  const parameters = {
    suites: [],
    suitesAggregated: ((matrix.suiteses.length === 1) &&
                            (matrix.suiteses[0].length > 1)),
    measurements: matrix.measurements,
    bots: [],
    botsAggregated: ((matrix.botses.length === 1) &&
                      (matrix.botses[0].length > 1)),
    cases: [],
    casesAggregated: ((matrix.caseses.length === 1) &&
                          (matrix.caseses[0].length > 1)),
    statistics: matrix.statistics,
  };
  for (const suites of matrix.suiteses) {
    parameters.suites.push(...suites);
  }
  for (const bots of matrix.botses) {
    parameters.bots.push(...bots);
  }
  for (const cases of matrix.caseses) {
    parameters.cases.push(...cases);
  }
  return parameters;
}

SparklineCompound.parameterMatrix = state => {
  const descriptor = cp.TimeseriesDescriptor.getParameterMatrix(
      state.descriptor.suite,
      state.descriptor.measurement,
      state.descriptor.bot,
      state.descriptor.case);
  if (descriptor.cases.length === 0) descriptor.cases.push([]);
  return {
    suiteses: descriptor.suites,
    measurements: descriptor.measurements,
    botses: descriptor.bots,
    caseses: descriptor.cases,
    statistics: state.statistic.selectedOptions,
    buildTypes: ['test'],
  };
};

function maybeAddParameterTab(
    parameterMatrix, revisions, sparkLayout, relatedTabs, descriptor,
    propertyName, tabName, matrixName) {
  let options = descriptor[propertyName].selectedOptions;
  if (options.length === 0) {
    // If zero suites or bots are selected, then buildRelatedTabs
    // wouldn't be called. If zero cases are selected, then build
    // sparklines for all available cases.
    options = []; // Do not append to [propertyName].selectedOptions!
    for (const option of descriptor[propertyName].options) {
      options.push(...cp.OptionGroup.getValuesFromOption(option));
    }
    if (options.length === 0) return;
  } else if (options.length === 1 || !descriptor[propertyName].isAggregated) {
    return;
  }
  relatedTabs.push({
    name: tabName,
    sparklines: options.map(option =>
      createSparkline(option, sparkLayout, revisions, {
        ...parameterMatrix,
        [matrixName]: [[option]],
      })),
  });
}

function maybeAddV8BrowsingTabs(
    parameterMatrix, revisions, sparkLayout, relatedTabs, descriptor) {
  if (descriptor.suite.selectedOptions.filter(
      ts => ts.startsWith('v8:browsing')).length === 0) {
    return;
  }

  const rails = ['Response', 'Animation', 'Idle', 'Load', 'Startup'];
  const measurements = descriptor.measurement.selectedOptions;

  if (measurements.filter(
      m => (!rails.includes(m.split('_')[0]) &&
            !m.startsWith('memory:'))).length) {
    const sparklines = rails.map(rail => createSparkline(
        rail, sparkLayout, revisions, {
          ...parameterMatrix,
          measurements: measurements.map(m => rail + '_' + m),
        }));
    relatedTabs.push({name: 'RAILS', sparklines});
  }

  const sparklines = [];

  if (measurements.filter(
      m => (m.startsWith('Total:') &&
            ['count', 'duration'].includes(m.split(':')[1]))).length) {
    for (const relatedName of ['Blink C++', 'V8-Only']) {
      sparklines.push(createSparkline(
          relatedName, sparkLayout, revisions, {
            ...parameterMatrix,
            measurements: measurements.map(
                m => relatedName + ':' + m.split(':')[1]),
          }));
    }
  }

  const v8Only = measurements.filter(m => m.includes('V8-Only:'));
  if (v8Only.length) {
    for (const relatedName of [
      'API',
      'Compile',
      'Compile-Background',
      'GC',
      'IC',
      'JavaScript',
      'Optimize',
      'Parse',
      'Parse-Background',
      'V8 C++',
    ]) {
      sparklines.push(createSparkline(
          relatedName, sparkLayout, revisions, {
            ...parameterMatrix,
            measurements: v8Only.map(
                m => m.replace('V8-Only', relatedName)),
          }));
    }
  }

  const gc = measurements.filter(m => m.includes('GC:'));
  if (gc.length) {
    for (const relatedName of [
      'MajorMC', 'Marking', 'MinorMC', 'Other', 'Scavenger', 'Sweeping',
    ]) {
      sparklines.push(createSparkline(
          relatedName, sparkLayout, revisions, {
            ...parameterMatrix,
            measurements: gc.map(
                m => m.replace('GC', 'GC-Background-' + relatedName)),
          }));
    }
  }

  if (sparklines.length) {
    relatedTabs.push({name: 'Component', sparklines});
  }
}

function maybeAddMemoryTabs(
    parameterMatrix, revisions, sparkLayout, relatedTabs, descriptor) {
  const processSparklines = [];
  const componentSparklines = [];

  for (const measurement of descriptor.measurement.selectedOptions) {
    const measurementAvg = measurement + '_avg';
    if (d.MEMORY_PROCESS_RELATED_NAMES.has(measurementAvg)) {
      for (let relatedMeasurement of d.MEMORY_PROCESS_RELATED_NAMES.get(
          measurementAvg)) {
        if (relatedMeasurement.endsWith('_avg')) {
          relatedMeasurement = relatedMeasurement.slice(0, -4);
        }
        if (relatedMeasurement === measurement) continue;
        const relatedParts = relatedMeasurement.split(':');
        processSparklines.push(createSparkline(
            relatedParts[2], sparkLayout, revisions, {
              ...parameterMatrix,
              measurements: [relatedMeasurement],
            }));
      }
    }
    if (d.MEMORY_COMPONENT_RELATED_NAMES.has(measurementAvg)) {
      for (let relatedMeasurement of d.MEMORY_COMPONENT_RELATED_NAMES.get(
          measurementAvg)) {
        if (relatedMeasurement.endsWith('_avg')) {
          relatedMeasurement = relatedMeasurement.slice(0, -4);
        }
        if (relatedMeasurement === measurement) continue;
        const relatedParts = relatedMeasurement.split(':');
        const name = relatedParts.slice(
            4, relatedParts.length - 1).join(':');
        componentSparklines.push(createSparkline(
            name, sparkLayout, revisions, {
              ...parameterMatrix,
              measurements: [relatedMeasurement],
            }));
      }
    }
  }
  if (processSparklines.length) {
    relatedTabs.push({
      name: 'Process',
      sparklines: processSparklines,
    });
  }
  if (componentSparklines.length) {
    relatedTabs.push({
      name: 'Component',
      sparklines: componentSparklines,
    });
  }
}

SparklineCompound.reducers = {
  buildRelatedTabs: (state, action, rootState) => {
    const relatedTabs = [];
    const parameterMatrix = SparklineCompound.parameterMatrix(state);
    const revisions = {
      minRevision: state.chartLayout.minRevision,
      maxRevision: state.chartLayout.maxRevision,
      zeroYAxis: state.zeroYAxis,
      fixedXAxis: state.fixedXAxis,
      mode: state.mode,
    };
    const descriptor = state.descriptor;
    const sparkLayout = cp.ChartTimeseries.buildState({});
    sparkLayout.yAxis.generateTicks = false;
    sparkLayout.xAxis.generateTicks = false;
    sparkLayout.graphHeight = 100;

    maybeAddParameterTab(
        parameterMatrix, revisions, sparkLayout, relatedTabs, descriptor,
        'suite', 'Suites', 'suiteses');

    maybeAddV8BrowsingTabs(
        parameterMatrix, revisions, sparkLayout, relatedTabs, descriptor);

    maybeAddMemoryTabs(
        parameterMatrix, revisions, sparkLayout, relatedTabs, descriptor);

    maybeAddParameterTab(
        parameterMatrix, revisions, sparkLayout, relatedTabs, descriptor,
        'bot', 'Bots', 'botses');
    maybeAddParameterTab(
        parameterMatrix, revisions, sparkLayout, relatedTabs, descriptor,
        'case', 'Cases', 'caseses');

    if (state.selectedRelatedTabName) {
      const selectedRelatedTabIndex = relatedTabs.findIndex(tab =>
        tab.name === state.selectedRelatedTabName);
      if (selectedRelatedTabIndex >= 0) {
        relatedTabs[selectedRelatedTabIndex].renderedSparklines =
          relatedTabs[selectedRelatedTabIndex].sparklines;
      }
    }

    return {...state, relatedTabs};
  },

  // Copy state.min/maxRevision to all sparklines.
  updateSparklineRevisions: (state, action, rootState) => {
    if (!state || !state.relatedTabs) return state;

    const minRevision = state.minRevision;
    const maxRevision = state.maxRevision;
    const relatedTabs = state.relatedTabs.map(tab => {
      const sparklines = tab.sparklines.map(sparkline => {
        const layout = {...sparkline.layout, minRevision, maxRevision};
        return {...sparkline, layout};
      });
      const renderedSparklines = tab.renderedSparklines ? sparklines :
        undefined;
      return {...tab, sparklines, renderedSparklines};
    });
    return {...state, relatedTabs};
  },

  // Copy state.cursorScalar/cursorRevision to all renderedSparklines in all
  // tabs.
  setCursors: (state, action, rootState) => {
    if (!state.cursorRevision || !state.cursorScalar || !state.relatedTabs) {
      return state;
    }

    const relatedTabs = state.relatedTabs.map(tab => {
      if (!tab.renderedSparklines) return tab;

      const renderedSparklines = tab.renderedSparklines.map(sparkline => {
        if (sparkline.layout.xAxis.range.isEmpty ||
            !sparkline.layout.yAxis) {
          return sparkline;
        }

        let xPct;
        if (state.fixedXAxis) {
          let nearestDatum;
          for (const line of sparkline.layout.lines) {
            if (!line.data || !line.data.length) continue;
            const datum = tr.b.findClosestElementInSortedArray(
                line.data, d => d.x, state.cursorRevision);
            if (!nearestDatum ||
                (Math.abs(state.cursorRevision - datum.x) <
                Math.abs(state.cursorRevision - nearestDatum.x))) {
              nearestDatum = datum;
            }
          }
          if (nearestDatum) xPct = nearestDatum.xPct + '%';
        } else {
          xPct = sparkline.layout.xAxis.range.normalize(state.cursorRevision);
          xPct = tr.b.math.truncate(xPct * 100, 1) + '%';
        }

        let yPct;
        let yRange;
        if (state.mode === cp.MODE.NORMALIZE_UNIT) {
          if (sparkline.layout.yAxis.rangeForUnitName) {
            yRange = sparkline.layout.yAxis.rangeForUnitName.get(
                state.cursorScalar.unit.baseUnit.unitName);
          }
        } else if (sparkline.layout.lines.length === 1) {
          yRange = sparkline.layout.lines[0].yRange;
        }
        if (yRange) {
          yPct = tr.b.math.truncate((1 - yRange.normalize(
              state.cursorScalar.value)) * 100, 1) + '%';
        }

        return {
          ...sparkline,
          layout: {
            ...sparkline.layout,
            xAxis: {
              ...sparkline.layout.xAxis,
              cursor: {pct: xPct},
            },
            yAxis: {
              ...sparkline.layout.yAxis,
              cursor: {pct: yPct},
            },
          },
        };
      });
      return {...tab, renderedSparklines};
    });
    return {...state, relatedTabs};
  },
};

cp.ElementBase.register(SparklineCompound);
