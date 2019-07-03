/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import './error-set.js';
import './recommended-options.js';
import '@chopsui/chops-checkbox';
import '@chopsui/chops-loading';
import {BatchIterator} from '@chopsui/batch-iterator';
import {DescribeRequest} from './describe-request.js';
import {ElementBase, STORE} from './element-base.js';
import {MemoryComponents} from './memory-components.js';
import {MenuInput} from './menu-input.js';
import {OptionGroup} from './option-group.js';
import {TOGGLE, UPDATE} from './simple-redux.js';
import {TagFilter} from './tag-filter.js';
import {TestSuitesRequest} from './test-suites-request.js';
import {get} from 'dot-prop-immutable';
import {html, css} from 'lit-element';

export class TimeseriesDescriptor extends ElementBase {
  static get is() { return 'timeseries-descriptor'; }

  static get properties() {
    return {
      statePath: String,
      suite: Object,
      measurement: Object,
      bot: Object,
      case: Object,
      isLoading: Boolean,
      errors: Array,
    };
  }

  static buildState(options) {
    if (!options) options = {};
    const suite = options.suite || {};
    suite.label = 'Suite';
    suite.required = true;
    if (!suite.options) suite.options = [];

    const measurement = options.measurement || {};
    measurement.label = 'Measurement';
    measurement.required = true;
    if (!measurement.options) measurement.options = [];

    const bot = options.bot || {};
    bot.label = 'Bot';
    bot.required = true;
    if (!bot.options) bot.options = [];

    const cas = options.case || {};
    cas.label = 'Case';
    if (!cas.options) cas.options = [];
    if (!cas.tags) cas.tags = {};
    if (!cas.tags.options) cas.tags.options = [];

    return {
      isLoading: false,
      errors: [],
      suite: {
        isAggregated: suite.isAggregated !== false,
        canAggregate: suite.canAggregate !== false,
        ...MenuInput.buildState(suite),
      },
      measurement: {
        ...MemoryComponents.buildState(measurement),
        ...MenuInput.buildState(measurement),
      },
      bot: {
        isAggregated: bot.isAggregated !== false,
        canAggregate: bot.canAggregate !== false,
        ...MenuInput.buildState(bot),
      },
      case: {
        isAggregated: cas.isAggregated !== false,
        canAggregate: cas.canAggregate !== false,
        ...MenuInput.buildState(cas),
        ...TagFilter.buildState(cas.tags),
      },
    };
  }

  static get styles() {
    return css`
      #row {
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
      chops-checkbox[hidden] {
        visibility: hidden;
      }
    `;
  }

  render() {
    return html`
      <div id="row">
        <div>
          <menu-input
              .statePath="${this.statePath}.suite"
              @keydown="${this.onSuiteKeyDown_}"
              @option-select="${this.onSuiteSelect_}">
            <recommended-options
                slot="top"
                .statePath="${this.statePath}.suite">
            </recommended-options>
          </menu-input>

          <div class="error"
              ?visible="${this.suite.selectedOptions.length === 0}">
            At least one required
          </div>

          ${!this.suite.canAggregate ? '' : html`
            <chops-checkbox
                ?hidden="${this.suite.selectedOptions.length === 0}"
                ?disabled="${this.suite.selectedOptions.length === 1}"
                ?checked="${this.suite.isAggregated}"
                @change="${this.onSuiteAggregateChange_}">
              Aggregate
            </chops-checkbox>
          `}
        </div>

        <div>
          <menu-input
              .statePath="${this.statePath}.measurement"
              @keydown="${this.onMeasurementKeyDown_}"
              @option-select="${this.onMeasurementSelect_}">
            <div slot="top">
              <recommended-options .statePath="${this.statePath}.measurement">
              </recommended-options>
              <memory-components .statePath="${this.statePath}.measurement">
              </memory-components>
            </div>
          </menu-input>

          ${this.measurement.requireSingle ? html`
            <div class="error"
                ?visible="${this.measurement.selectedOptions.length !== 1}">
              Exactly one required
            </div>
          ` : html`
            <div class="error"
                ?visible="${this.measurement.selectedOptions.length === 0}">
              At least one required
            </div>
          `}
        </div>

        <div>
          <menu-input
              .statePath="${this.statePath}.bot"
              @keydown="${this.onBotKeyDown_}"
              @option-select="${this.onBotSelect_}">
            <recommended-options slot="top" .statePath="${this.statePath}.bot">
            </recommended-options>
          </menu-input>

          <div class="error"
              ?visible="${this.bot.selectedOptions.length === 0}">
            At least one required
          </div>

          ${!this.bot.canAggregate ? '' : html`
            <chops-checkbox
                ?hidden="${this.bot.selectedOptions.length === 0}"
                ?disabled="${this.bot.selectedOptions.length === 1}"
                ?checked="${this.bot.isAggregated}"
                @change="${this.onBotAggregateChange_}">
              Aggregate
            </chops-checkbox>
          `}
        </div>

        <div>
          <menu-input
              .statePath="${this.statePath}.case"
              @keydown="${this.onCaseKeyDown_}"
              @option-select="${this.onCaseSelect_}">
            <recommended-options slot="top" .statePath="${this.statePath}.case">
            </recommended-options>

            <tag-filter slot="left" .statePath="${this.statePath}.case">
            </tag-filter>
          </menu-input>

          ${!this.case.canAggregate ? '' : html`
            <chops-checkbox
                ?hidden="${this.case.selectedOptions.length === 0}"
                ?disabled="${this.case.selectedOptions.length === 1}"
                ?checked="${this.case.isAggregated}"
                @change="${this.onCaseAggregateChange_}">
              Aggregate
            </chops-checkbox>
          `}
        </div>
      </div>

      <chops-loading ?loading="${this.isLoading}"></chops-loading>
      <error-set .errors="${this.errors}"></error-set>
    `;
  }

  async firstUpdated() {
    await TimeseriesDescriptor.ready(this.statePath);
    this.dispatchMatrixChange_();
  }

  static async ready(statePath) {
    const suitesLoaded = TimeseriesDescriptor.loadSuites(statePath);

    const state = get(STORE.getState(), statePath);
    if (state && state.suite && state.suite.selectedOptions &&
        state.suite.selectedOptions.length) {
      await Promise.all([
        suitesLoaded,
        TimeseriesDescriptor.describeSuites(statePath),
      ]);
    } else {
      await suitesLoaded,
      MenuInput.focus(`${statePath}.suite`);
    }
  }

  static async loadSuites(statePath) {
    try {
      const request = new TestSuitesRequest({});
      const suites = await request.response;
      STORE.dispatch({
        type: TimeseriesDescriptor.reducers.receiveTestSuites.name,
        statePath,
        suites,
      });
    } catch (err) {
      STORE.dispatch(UPDATE(statePath, {errors: [err.message]}));
    }
  }

  static async describeSuites(statePath) {
    const mergedDescriptor = {
      measurements: new Set(),
      bots: new Set(),
      cases: new Set(),
      caseTags: new Map(),
    };
    let state = get(STORE.getState(), statePath);
    if (state.suite.selectedOptions.length === 0) {
      STORE.dispatch({
        type: TimeseriesDescriptor.reducers.receiveDescriptor.name,
        statePath,
        descriptor: mergedDescriptor,
      });
      STORE.dispatch({
        type: TimeseriesDescriptor.reducers.finalizeParameters.name,
        statePath,
      });
      return;
    }

    const suites = new Set(state.suite.selectedOptions);
    const descriptors = state.suite.selectedOptions.map(suite =>
      new DescribeRequest({suite}).response);
    for await (const {results, errors} of new BatchIterator(descriptors)) {
      state = get(STORE.getState(), statePath);
      if (!state.suite || !tr.b.setsEqual(
          suites, new Set(state.suite.selectedOptions))) {
        // The user changed the set of selected suites, so stop handling
        // the old set of suites. The new set of suites will be
        // handled by a new dispatch of this action creator.
        return;
      }
      for (const descriptor of results) {
        if (!descriptor) continue;
        DescribeRequest.mergeDescriptor(mergedDescriptor, descriptor);
      }
      STORE.dispatch({
        type: TimeseriesDescriptor.reducers.receiveDescriptor.name,
        statePath,
        descriptor: mergedDescriptor,
        errors,
      });
    }
    STORE.dispatch({
      type: TimeseriesDescriptor.reducers.finalizeParameters.name,
      statePath,
    });

    state = get(STORE.getState(), statePath);

    if (state.measurement.selectedOptions.length === 0) {
      MenuInput.focus(`${statePath}.measurement`);
    }
  }

  dispatchMatrixChange_() {
    this.dispatchEvent(new CustomEvent('matrix-change', {
      bubbles: true,
      composed: true,
      detail: TimeseriesDescriptor.getParameterMatrix(
          this.suite, this.measurement, this.bot, this.case),
    }));
  }

  async onSuiteKeyDown_(event) {
    if (event.key === 'Tab') {
      MenuInput.focus(`${this.statePath}.measurement`);
    }
  }

  async onMeasurementKeyDown_(event) {
    if (event.key === 'Tab') {
      MenuInput.focus(`${this.statePath}.bot`);
    }
  }

  async onBotKeyDown_(event) {
    if (event.key === 'Tab') {
      MenuInput.focus(`${this.statePath}.case`);
    }
  }

  async onCaseKeyDown_(event) {
    if (event.key === 'Tab') {
      MenuInput.focus(`${this.statePath}.statistic`);
    }
  }

  async onSuiteSelect_(event) {
    METRICS.startLoadMenu();
    await TimeseriesDescriptor.describeSuites(this.statePath);
    METRICS.endLoadMenu();
    this.dispatchMatrixChange_();
  }

  async onMeasurementSelect_(event) {
    METRICS.startLoadMenu();
    // The next menu is already loaded. Add a sample to the load/menu metric
    // (even though it's zero) because the V1 UI adds a sample in this
    // situation. This load/menu sample can be removed when V1 UI is removed.
    METRICS.endLoadMenu();
    this.dispatchMatrixChange_();
  }

  async onBotSelect_(event) {
    METRICS.startLoadMenu();
    // The next menu is already loaded. Add a sample to the load/menu metric
    // (even though it's zero) because the V1 UI adds a sample in this
    // situation. This load/menu sample can be removed when V1 UI is removed.
    METRICS.endLoadMenu();
    this.dispatchMatrixChange_();
  }

  async onCaseSelect_(event) {
    METRICS.startLoadMenu();
    // The next menu is already loaded. Add a sample to the load/menu metric
    // (even though it's zero) because the V1 UI adds a sample in this
    // situation. This load/menu sample can be removed when V1 UI is removed.
    METRICS.endLoadMenu();
    this.dispatchMatrixChange_();
  }

  async onSuiteAggregateChange_(event) {
    STORE.dispatch(TOGGLE(`${this.statePath}.suite.isAggregated`));
    this.dispatchMatrixChange_();
  }

  async onBotAggregateChange_(event) {
    STORE.dispatch(TOGGLE(`${this.statePath}.bot.isAggregated`));
    this.dispatchMatrixChange_();
  }

  async onCaseAggregateChange_(event) {
    STORE.dispatch(TOGGLE(`${this.statePath}.case.isAggregated`));
    this.dispatchMatrixChange_();
  }

  static getParameterMatrix(suite, measurement, bot, cas) {
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
  }

  static createLineDescriptors({
    suiteses, measurements, botses, caseses, statistics,
    buildTypes,
  }) {
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
  }
}

TimeseriesDescriptor.reducers = {
  receiveTestSuites: (state, {suites}, rootState) => {
    if (!state) return state;
    const suite = {
      ...state.suite,
      ...MenuInput.buildState({
        ...state.suite,
        options: suites,
        label: `Suites (${suites.length})`,
      }),
    };
    return {...state, suite};
  },

  receiveDescriptor: (state, {descriptor, errors}, rootState) => {
    state = {...state};

    if (errors) {
      errors = errors.map(e => e.message);
      state.errors = [...new Set([...state.errors, ...errors])];
    }

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

ElementBase.register(TimeseriesDescriptor);
