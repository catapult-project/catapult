/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import './cp-checkbox.js';
import './recommended-options.js';
import DescribeRequest from './describe-request.js';
import ElementBase from './element-base.js';
import MemoryComponents from './memory-components.js';
import MenuInput from './menu-input.js';
import OptionGroup from './option-group.js';
import TagFilter from './tag-filter.js';
import TestSuitesRequest from './test-suites-request.js';
import {TOGGLE} from './simple-redux.js';

import {
  BatchIterator,
  buildProperties,
  buildState,
} from './utils.js';

export default class TimeseriesDescriptor extends ElementBase {
  static get is() { return 'timeseries-descriptor'; }

  static get template() {
    return Polymer.html`
      <style>
        :host {
          display: flex;
        }
        menu-input {
          margin-right: 8px;
        }
        .error {
          color: var(--error-color, red);
          position: absolute;
          visibility: hidden;
        }
        .error[visible] {
          visibility: visible;
        }
        cp-checkbox[hidden] {
          visibility: hidden;
        }
      </style>

      <div>
        <menu-input
            state-path="[[statePath]].suite"
            on-option-select="onSuiteSelect_">
          <recommended-options slot="top" state-path="[[statePath]].suite">
          </recommended-options>
        </menu-input>

        <div class="error" visible$="[[isEmpty_(suite.selectedOptions)]]">
          At least one required
        </div>

        <template is="dom-if" if="[[suite.canAggregate]]">
          <cp-checkbox
              hidden$="[[isEmpty_(suite.selectedOptions)]]"
              disabled$="[[!isMultiple_(suite.selectedOptions)]]"
              checked="[[suite.isAggregated]]"
              on-change="onSuiteAggregateChange_">
            Aggregate
          </cp-checkbox>
        </template>
      </div>

      <div>
        <menu-input
            state-path="[[statePath]].measurement"
            on-option-select="onMeasurementSelect_">
          <div slot="top">
            <recommended-options state-path="[[statePath]].measurement">
            </recommended-options>
            <memory-components state-path="[[statePath]].measurement">
            </memory-components>
          </div>
        </menu-input>

        <template is="dom-if" if="[[!measurement.requireSingle]]">
          <div class="error"
                visible$="[[isEmpty_(measurement.selectedOptions)]]">
            At least one required
          </div>
        </template>

        <template is="dom-if" if="[[measurement.requireSingle]]">
          <div class="error"
                visible$="[[showExactlyOneRequiredMeasurement_(measurement)]]">
            Exactly one required
          </div>
        </template>
      </div>

      <div>
        <menu-input
            state-path="[[statePath]].bot"
            on-option-select="onBotSelect_">
          <recommended-options slot="top" state-path="[[statePath]].bot">
          </recommended-options>
        </menu-input>

        <div class="error" visible$="[[isEmpty_(bot.selectedOptions)]]">
          At least one required
        </div>

        <template is="dom-if" if="[[bot.canAggregate]]">
          <cp-checkbox
              hidden$="[[isEmpty_(bot.selectedOptions)]]"
              disabled$="[[!isMultiple_(bot.selectedOptions)]]"
              checked="[[bot.isAggregated]]"
              on-change="onBotAggregateChange_">
            Aggregate
          </cp-checkbox>
        </template>
      </div>

      <div>
        <menu-input
            state-path="[[statePath]].case"
            on-option-select="onCaseSelect_">
          <recommended-options slot="top" state-path="[[statePath]].case">
          </recommended-options>

          <tag-filter slot="left" state-path="[[statePath]].case">
          </tag-filter>
        </menu-input>

        <template is="dom-if" if="[[case.canAggregate]]">
          <cp-checkbox
              disabled$="[[!isMultiple_(case.selectedOptions)]]"
              checked="[[case.isAggregated]]"
              on-change="onCaseAggregateChange_">
            Aggregate
          </cp-checkbox>
        </template>
      </div>
    `;
  }

  async ready() {
    super.ready();
    await this.dispatch('ready', this.statePath);
    this.dispatchMatrixChange_();
  }

  showExactlyOneRequiredMeasurement_(measurement) {
    return measurement && (1 !== measurement.selectedOptions.length);
  }

  dispatchMatrixChange_() {
    this.dispatchEvent(new CustomEvent('matrix-change', {
      bubbles: true,
      composed: true,
      detail: TimeseriesDescriptor.getParameterMatrix(
          this.suite, this.measurement, this.bot, this.case),
    }));
  }

  async onSuiteSelect_(event) {
    await this.dispatch('describeSuites', this.statePath);
    this.dispatchMatrixChange_();
  }

  async onMeasurementSelect_(event) {
    this.dispatchMatrixChange_();
  }

  async onBotSelect_(event) {
    this.dispatchMatrixChange_();
  }

  async onCaseSelect_(event) {
    this.dispatchMatrixChange_();
  }

  async onSuiteAggregateChange_(event) {
    this.dispatch(TOGGLE(`${this.statePath}.suite.isAggregated`));
    this.dispatchMatrixChange_();
  }

  async onBotAggregateChange_(event) {
    this.dispatch(TOGGLE(`${this.statePath}.bot.isAggregated`));
    this.dispatchMatrixChange_();
  }

  async onCaseAggregateChange_(event) {
    this.dispatch(TOGGLE(`${this.statePath}.case.isAggregated`));
    this.dispatchMatrixChange_();
  }
}

TimeseriesDescriptor.State = {
  suite: options => {
    const suite = (options || {}).suite || {};
    suite.label = 'Suite';
    suite.required = true;
    if (!suite.options) suite.options = [];
    return {
      isAggregated: suite.isAggregated !== false,
      canAggregate: suite.canAggregate !== false,
      ...MenuInput.buildState(suite),
    };
  },
  measurement: options => {
    const measurement = (options || {}).measurement || {};
    measurement.label = 'Measurement';
    measurement.required = true;
    if (!measurement.options) measurement.options = [];
    return {
      ...MemoryComponents.buildState(measurement),
      ...MenuInput.buildState(measurement),
    };
  },
  bot: options => {
    const bot = (options || {}).bot || {};
    bot.label = 'Bot';
    bot.required = true;
    if (!bot.options) bot.options = [];
    return {
      isAggregated: bot.isAggregated !== false,
      canAggregate: bot.canAggregate !== false,
      ...MenuInput.buildState(bot),
    };
  },
  case: options => {
    const cas = (options || {}).case || {};
    cas.label = 'Case';
    if (!cas.options) cas.options = [];
    if (!cas.tags) cas.tags = {};
    if (!cas.tags.options) cas.tags.options = [];
    return {
      isAggregated: cas.isAggregated !== false,
      canAggregate: cas.canAggregate !== false,
      ...MenuInput.buildState(cas),
      ...TagFilter.buildState(cas.tags),
    };
  },
};

TimeseriesDescriptor.buildState = options => buildState(
    TimeseriesDescriptor.State, options);

TimeseriesDescriptor.properties = {
  ...buildProperties('state', TimeseriesDescriptor.State),
};

TimeseriesDescriptor.actions = {
  ready: statePath => async(dispatch, getState) => {
    const suitesLoaded = TimeseriesDescriptor.actions.loadSuites(
        statePath)(dispatch, getState);

    const state = Polymer.Path.get(getState(), statePath);
    if (state && state.suite && state.suite.selectedOptions &&
        state.suite.selectedOptions.length) {
      await Promise.all([
        suitesLoaded,
        TimeseriesDescriptor.actions.describeSuites(statePath)(
            dispatch, getState),
      ]);
    } else {
      await suitesLoaded,
      MenuInput.actions.focus(`${statePath}.suite`)(
          dispatch, getState);
    }
  },

  loadSuites: statePath => async(dispatch, getState) => {
    const request = new TestSuitesRequest({});
    const suites = await request.response;
    dispatch({
      type: TimeseriesDescriptor.reducers.receiveTestSuites.name,
      statePath,
      suites,
    });
  },

  describeSuites: statePath => async(dispatch, getState) => {
    const mergedDescriptor = {
      measurements: new Set(),
      bots: new Set(),
      cases: new Set(),
      caseTags: new Map(),
    };
    let state = Polymer.Path.get(getState(), statePath);
    if (state.suite.selectedOptions.length === 0) {
      dispatch({
        type: TimeseriesDescriptor.reducers.receiveDescriptor.name,
        statePath,
        descriptor: mergedDescriptor,
      });
      dispatch({
        type: TimeseriesDescriptor.reducers.finalizeParameters.name,
        statePath,
      });
      return;
    }

    const suites = new Set(state.suite.selectedOptions);
    const descriptors = state.suite.selectedOptions.map(suite =>
      new DescribeRequest({suite}).response);
    for await (const {results, errors} of new BatchIterator(descriptors)) {
      state = Polymer.Path.get(getState(), statePath);
      if (!state.suite || !tr.b.setsEqual(
          suites, new Set(state.suite.selectedOptions))) {
        // The user changed the set of selected suites, so stop handling
        // the old set of suites. The new set of suites will be
        // handled by a new dispatch of this action creator.
        return;
      }
      // TODO display errors
      for (const descriptor of results) {
        if (!descriptor) continue;
        DescribeRequest.mergeDescriptor(mergedDescriptor, descriptor);
      }
      dispatch({
        type: TimeseriesDescriptor.reducers.receiveDescriptor.name,
        statePath,
        descriptor: mergedDescriptor,
      });
    }
    dispatch({
      type: TimeseriesDescriptor.reducers.finalizeParameters.name,
      statePath,
    });

    state = Polymer.Path.get(getState(), statePath);

    if (state.measurement.selectedOptions.length === 0) {
      MenuInput.actions.focus(`${statePath}.measurement`)(
          dispatch, getState);
    }
  },
};

TimeseriesDescriptor.reducers = {
  receiveTestSuites: (state, {suites}, rootState) => {
    if (!state) return state;
    const suite = TimeseriesDescriptor.State.suite({suite: {
      ...state.suite,
      options: suites,
    }});
    return {...state, suite};
  },

  receiveDescriptor: (state, {descriptor}, rootState) => {
    state = {...state};

    state.measurement = {
      ...state.measurement,
      optionValues: descriptor.measurements,
      options: OptionGroup.groupValues(descriptor.measurements),
      label: `Measurements (${descriptor.measurements.size})`,
    };

    const botOptions = OptionGroup.groupValues(descriptor.bots);
    state.bot = {
      ...state.bot,
      optionValues: descriptor.bots,
      options: botOptions.map(option => {
        return {...option, isExpanded: true};
      }),
      label: `Bots (${descriptor.bots.size})`,
    };

    const caseOptions = [];
    if (descriptor.cases.size) {
      caseOptions.push({
        label: `All test cases`,
        isExpanded: true,
        options: OptionGroup.groupValues(descriptor.cases),
      });
    }

    state.case = {
      ...state.case,
      optionValues: descriptor.cases,
      options: caseOptions,
      label: `Cases (${descriptor.cases.size})`,
      tags: {
        ...state.case.tags,
        map: descriptor.caseTags,
        optionValues: new Set(descriptor.caseTags.keys()),
        options: OptionGroup.groupValues(descriptor.caseTags.keys()),
      },
    };

    return state;
  },

  finalizeParameters: (state, action, rootState) => {
    state = {...state};
    state.measurement = {...state.measurement};
    if (state.measurement.optionValues.size === 1) {
      state.measurement.selectedOptions = [...state.measurement.optionValues];
    } else {
      state.measurement.selectedOptions =
        state.measurement.selectedOptions.filter(
            m => state.measurement.optionValues.has(m));
    }

    state.bot = {...state.bot};
    if ((state.bot.optionValues.size === 1) ||
        ((state.bot.selectedOptions.length === 1) &&
          (state.bot.selectedOptions[0] === '*'))) {
      state.bot.selectedOptions = [...state.bot.optionValues];
    } else {
      state.bot.selectedOptions = state.bot.selectedOptions.filter(b =>
        state.bot.optionValues.has(b));
    }

    state.case = {
      ...state.case,
      selectedOptions: state.case.selectedOptions.filter(t =>
        state.case.optionValues.has(t)),
    };
    if (state.case.tags && state.case.tags.selectedOptions &&
        state.case.tags.selectedOptions.length) {
      state.case = TagFilter.reducers.filter(state.case);
    }

    return state;
  },
};

TimeseriesDescriptor.getParameterMatrix = (suite, measurement, bot, cas) => {
  // Organizes selected options from redux state into an object like
  // {suites, measurements, bots, cases}.
  // suites is an array of arrays of test suite names.
  // measurements is an array of measurement names.
  // bots is an array of arrays of bot names.
  // cases is an array of arrays of test case names.
  // suites, bots, and cases can be aggregated or unaggregated.
  // Aggregated parameters contain a single array that can contain multiple
  // names like [[a, b, c]].
  // Unaggregated parameters contain multiple arrays that contain a single
  // name like [[a], [b], [c]].

  if (!suite || !measurement || !bot || !cas) {
    return {suites: [], measurements: [], bots: [], cases: []};
  }

  let suites = suite.selectedOptions;
  if (suite.isAggregated) {
    suites = [suites];
  } else {
    suites = suites.map(suite => [suite]);
  }

  let bots = bot.selectedOptions;
  if (bot.isAggregated) {
    bots = [bots];
  } else {
    bots = bots.map(bot => [bot]);
  }

  let cases = cas.selectedOptions.filter(x => x);
  if (cas.isAggregated) {
    cases = [cases];
  } else {
    cases = cases.map(c => [c]);
  }
  if (cases.length === 0) cases.push([]);

  const measurements = measurement.selectedOptions;
  return {suites, measurements, bots, cases};
};

TimeseriesDescriptor.createLineDescriptors = ({
  suiteses, measurements, botses, caseses, statistics,
  buildTypes,
}) => {
  const lineDescriptors = [];
  for (const suites of suiteses) {
    for (const measurement of measurements) {
      for (const bots of botses) {
        for (const cases of caseses) {
          for (const statistic of statistics) {
            for (const buildType of buildTypes) {
              lineDescriptors.push({
                suites,
                measurement,
                bots,
                cases,
                statistic,
                buildType,
              });
            }
          }
        }
      }
    }
  }
  return lineDescriptors;
};

ElementBase.register(TimeseriesDescriptor);
