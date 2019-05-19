/* Copyright 2019 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import './chart-legend.js';
import './cp-input.js';
import './cp-loading.js';
import './expand-button.js';
import ChartBase from './chart-base.js';
import ChartCompound from './chart-compound.js';
import ChartTimeseries from './chart-timeseries.js';
import MenuInput from './menu-input.js';
import OptionGroup from './option-group.js';
import SparklineCompound from './sparkline-compound.js';
import TimeseriesDescriptor from './timeseries-descriptor.js';
import sha from './sha.js';
import {CHAIN, UPDATE} from './simple-redux.js';
import {ElementBase, STORE} from './element-base.js';
import {MODE} from './layout-timeseries.js';
import {get} from '@polymer/polymer/lib/utils/path.js';
import {html} from '@polymer/polymer/polymer-element.js';
import {simpleGUID} from './utils.js';

export default class ChartSection extends ElementBase {
  static get is() { return 'chart-section'; }

  static get properties() {
    return {
      statePath: String,
      linkedStatePath: String,
      sectionId: Number,
      descriptor: Object,
      title_: String,
      isTitleCustom: Boolean,
      legend: Object,
      selectedLineDescriptorHash: String,
      isLoading: Boolean,
      ...ChartCompound.properties,
      ...SparklineCompound.properties,
    };
  }

  static buildState(options = {}) {
    const params = options.parameters || {};

    // Support old spelling of some parameters including 'test'.
    if (params.testSuites || params.testCases) {
      params.suites = params.testSuites;
      params.suitesAggregated = params.testSuitesAggregated;
      params.cases = params.testCases;
      params.casesAggregated = params.testCasesAggregated;
    }

    const descriptor = TimeseriesDescriptor.buildState({
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

    let selectedOptions = ['avg'];
    if (options.statistics) selectedOptions = options.statistics;
    if (options.parameters && options.parameters.statistics) {
      // Support old format.
      selectedOptions = options.parameters.statistics;
    }
    const statistic = MenuInput.buildState({
      label: 'Statistics',
      required: true,
      selectedOptions,
      options: ['avg', 'std', 'count', 'min', 'max', 'sum'],
    });

    return {
      sectionId: options.sectionId || simpleGUID(),
      ...ChartCompound.buildState(options),
      ...SparklineCompound.buildState(options),
      descriptor,
      title_: options.title || '',
      isTitleCustom: false,
      legend: undefined,
      selectedLineDescriptorHash: options.selectedLineDescriptorHash,
      isLoading: false,
      statistic,
    };
  }

  static get template() {
    return html`
      <style>
        #controls {
          align-items: center;
          display: flex;
          margin-bottom: 8px;
        }

        #controls_inner {
          display: flex;
          flex-direction: column;
        }

        #parameters {
          display: flex;
        }

        #spacer {
          flex-grow: 1;
        }

        #toggle_chart_only,
        #copy,
        #close {
          align-self: flex-start;
          cursor: pointer;
          flex-shrink: 0;
          height: var(--icon-size, 1em);
          width: var(--icon-size, 1em);
        }

        #chart_container {
          display: flex;
        }

        chart-legend {
          overflow-y: auto;
          overflow-x: hidden;
        }

        #legend_container {
          display: flex;
          flex-direction: column;
          justify-content: center;
          max-height: 311px;
        }
      </style>

      <div id="controls">
        <div id="controls_inner">
          <iron-collapse id="parameters"
                        opened="[[isExpanded]]">
            <timeseries-descriptor
                id="descriptor"
                state-path="[[statePath]].descriptor"
                on-matrix-change="onMatrixChange_">
            </timeseries-descriptor>

            <menu-input
                id="statistic"
                state-path="[[statePath]].statistic"
                on-option-select="onStatisticSelect_">
            </menu-input>
          </iron-collapse>

          <iron-collapse opened="[[!isExpanded]]">
            <cp-input
                id="title"
                value="[[title_]]"
                label="Title"
                on-keyup="onTitleKeyup_">
            </cp-input>
          </iron-collapse>
        </div>

        <span id="spacer">&nbsp;</span>

        <expand-button
            id="toggle_chart_only"
            state-path="[[statePath]]">
        </expand-button>

        <iron-icon
            id="copy"
            icon="cp:copy"
            title="Clone"
            on-click="onCopy_">
        </iron-icon>

        <iron-icon
            id="close"
            icon="cp:close"
            title="Close"
            on-click="onClose_">
        </iron-icon>
      </div>

      <cp-loading loading$="[[isLoading_(
          isLoading, minimapLayout, chartLayout)]]">
      </cp-loading>

      <div id="chart_container">
        <chart-compound
            state-path="[[statePath]]"
            linked-state-path="[[linkedStatePath]]"
            on-line-count-change="onLineCountChange_">
          Select at least one Test suite and Measurement above.
        </chart-compound>

        <iron-collapse
            id="legend_container"
            horizontal
            opened="[[isLegendOpen_(isExpanded, legend)]]"
            on-click="onLegendClick_">
          <chart-legend
              items="[[legend]]"
              on-leaf-mouseover="onLegendMouseOver_"
              on-leaf-mouseout="onLegendMouseOut_"
              on-leaf-click="onLegendLeafClick_">
          </chart-legend>
        </iron-collapse>
      </div>

      <iron-collapse opened="[[isExpanded]]">
        <sparkline-compound state-path="[[statePath]]">
        </sparkline-compound>
      </iron-collapse>
    `;
  }

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

  isLegendOpen_(isExpanded, legend) {
    return isExpanded && !this.isEmpty_(legend);
  }

  async onMatrixChange_(event) {
    if (!this.descriptor) return;
    await ChartSection.maybeLoadTimeseries(this.statePath);
  }

  async onStatisticSelect_(event) {
    await ChartSection.maybeLoadTimeseries(this.statePath);
  }

  async onTitleKeyup_(event) {
    await STORE.dispatch(UPDATE(this.statePath, {
      title_: event.target.value,
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
          title: this.title_,
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
    ChartSection.legendMouseOver(
        this.statePath, event.detail.lineDescriptor);
  }

  onLegendMouseOut_(event) {
    STORE.dispatch(CHAIN(
        {
          type: ChartTimeseries.reducers.mouseYTicks.name,
          statePath: statePath + '.chartLayout',
        },
        {
          type: ChartBase.reducers.boldLine.name,
          statePath: statePath + '.chartLayout',
        },
    ));
  }

  async onLegendLeafClick_(event) {
    STORE.dispatch({
      type: ChartSection.reducers.selectLine.name,
      statePath: this.statePath,
      lineDescriptor: event.detail.lineDescriptor,
      selectedLineDescriptorHash: await sha(
          ChartTimeseries.stringifyDescriptor(event.detail.lineDescriptor)),
    });
  }

  async onLegendClick_(event) {
    STORE.dispatch({
      type: ChartSection.reducers.deselectLine.name,
      statePath: this.statePath,
    });
  }

  onLineCountChange_() {
    const state = get(STORE.getState(), this.statePath);
    if (!state || !state.legend) return;
    STORE.dispatch({
      type: ChartSection.reducers.updateLegendColors.name,
      statePath: this.statePath,
    });
  }

  static async maybeLoadTimeseries(statePath) {
    // If the first 3 components are filled, then load the timeseries.
    const state = get(STORE.getState(), statePath);
    if (state.descriptor.suite.selectedOptions &&
        state.descriptor.suite.selectedOptions.length &&
        state.descriptor.measurement.selectedOptions &&
        state.descriptor.measurement.selectedOptions.length &&
        state.statistic.selectedOptions &&
        state.statistic.selectedOptions.length) {
      METRICS.endChartAction();
      ChartSection.loadTimeseries(statePath);
    } else {
      STORE.dispatch(UPDATE(statePath, {lineDescriptors: []}));
    }
  }

  static async loadTimeseries(statePath) {
    STORE.dispatch(CHAIN(
        {type: ChartSection.reducers.loadTimeseries.name, statePath},
        {
          type: SparklineCompound.reducers.buildRelatedTabs.name,
          statePath,
        }));

    const state = get(STORE.getState(), statePath);
    if (state.selectedLineDescriptorHash) {
      // Restore from URL.
      for (const lineDescriptor of state.lineDescriptors) {
        const lineDescriptorHash = await sha(
            ChartTimeseries.stringifyDescriptor(lineDescriptor));
        if (!lineDescriptorHash.startsWith(
            state.selectedLineDescriptorHash)) {
          continue;
        }
        STORE.dispatch(UPDATE(statePath, {
          lineDescriptors: [lineDescriptor],
        }));
        break;
      }
    }
  }

  static async legendMouseOver(statePath, lineDescriptor) {
    const chartPath = statePath + '.chartLayout';
    const state = get(STORE.getState(), statePath);
    lineDescriptor = JSON.stringify(lineDescriptor);
    for (let lineIndex = 0; lineIndex < state.chartLayout.lines.length;
      ++lineIndex) {
      const line = state.chartLayout.lines[lineIndex];
      if (JSON.stringify(line.descriptor) === lineDescriptor) {
        STORE.dispatch(CHAIN(
            {
              type: ChartTimeseries.reducers.mouseYTicks.name,
              statePath: chartPath,
              line,
            },
            {
              type: ChartBase.reducers.boldLine.name,
              statePath: chartPath,
              lineIndex,
            },
        ));
        break;
      }
    }
  }
}

ChartSection.reducers = {
  loadTimeseries: (state, action, rootState) => {
    const title_ = ChartSection.computeTitle(state);
    const parameterMatrix = SparklineCompound.parameterMatrix(state);
    const legend = ChartSection.buildLegend(parameterMatrix);
    const lineDescriptors = TimeseriesDescriptor.createLineDescriptors(
        parameterMatrix);
    return {
      ...state,
      title_,
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
    const parameterMatrix = SparklineCompound.parameterMatrix(state);
    const lineDescriptors = TimeseriesDescriptor.createLineDescriptors(
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
      colorMap.set(ChartTimeseries.stringifyDescriptor(
          line.descriptor), line.color);
    }
    function handleLegendEntry(entry) {
      if (entry.children) {
        return {...entry, children: entry.children.map(handleLegendEntry)};
      }
      const color = colorMap.get(ChartTimeseries.stringifyDescriptor(
          entry.lineDescriptor)) || 'grey';
      return {...entry, color};
    }
    return {...state, legend: state.legend.map(handleLegendEntry)};
  },
};

ChartSection.newStateOptionsFromQueryParams = routeParams => {
  let brushRevisions = [];
  try {
    brushRevisions = routeParams.get('brush').split('-').map(r =>
      parseInt(r));
  } catch (unused) {
  }

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
    brushRevisions,
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

This format is slightly different from ChartSection.buildState(), which has
`descriptor` (which does not include statistics) instead of `parameters` (which
does include statistics).
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
    title: state.title_,
    minRevision: state.minRevision,
    maxRevision: state.maxRevision,
    brushRevisions: state.chartLayout && state.chartLayout.brushRevisions,
    zeroYAxis: state.zeroYAxis,
    fixedXAxis: state.fixedXAxis,
    mode: state.mode,
    selectedRelatedTabName: state.selectedRelatedTabName,
    selectedLineDescriptorHash: state.selectedLineDescriptorHash,
  };
};

ChartSection.getRouteParams = state => {
  const allBotsSelected = state.descriptor.bot.selectedOptions.length ===
      OptionGroup.countDescendents(state.descriptor.bot.options);

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
  if (state.mode !== MODE.NORMALIZE_UNIT) {
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
  if (state.chartLayout &&
      state.chartLayout.brushRevisions &&
      state.chartLayout.brushRevisions.length) {
    routeParams.set('brush', state.chartLayout.brushRevisions.join('-'));
  }
  return routeParams;
};

ChartSection.computeTitle = state => {
  if (state.isTitleCustom) return state.title_;
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

ElementBase.register(ChartSection);
