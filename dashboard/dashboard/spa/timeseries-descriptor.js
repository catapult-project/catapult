/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';
tr.exportTo('cp', () => {
  class TimeseriesDescriptor extends cp.ElementBase {
    ready() {
      super.ready();
      this.dispatch('ready', this.statePath);
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
      this.dispatch(Redux.TOGGLE(`${this.statePath}.suite.isAggregated`));
      this.dispatchMatrixChange_();
    }

    async onBotAggregateChange_(event) {
      this.dispatch(Redux.TOGGLE(`${this.statePath}.bot.isAggregated`));
      this.dispatchMatrixChange_();
    }

    async onCaseAggregateChange_(event) {
      this.dispatch(Redux.TOGGLE(`${this.statePath}.case.isAggregated`));
      this.dispatchMatrixChange_();
    }
  }

  TimeseriesDescriptor.State = {
    suite: options => {
      const suite = (options || {}).suite || {};
      suite.label = 'Suite';
      if (!suite.options) suite.options = [];
      return {
        isAggregated: suite.isAggregated !== false,
        ...cp.MenuInput.buildState(suite),
      };
    },
    measurement: options => {
      const measurement = (options || {}).measurement || {};
      measurement.label = 'Measurement';
      if (!measurement.options) measurement.options = [];
      return {
        ...cp.MenuInput.buildState(measurement),
      };
    },
    bot: options => {
      const bot = (options || {}).bot || {};
      bot.label = 'Bot';
      if (!bot.options) bot.options = [];
      return {
        isAggregated: bot.isAggregated !== false,
        ...cp.MenuInput.buildState(bot),
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
        ...cp.MenuInput.buildState(cas),
        ...cp.TagFilter.buildState(cas.tags),
      };
    },
  };

  TimeseriesDescriptor.buildState = options => cp.buildState(
      TimeseriesDescriptor.State, options);

  TimeseriesDescriptor.properties = {
    ...cp.buildProperties('state', TimeseriesDescriptor.State),
  };

  TimeseriesDescriptor.actions = {
    ready: statePath => async(dispatch, getState) => {
      const request = new cp.TestSuitesRequest({});
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
        new cp.DescribeRequest({suite}).response);
      for await (const {results, errors} of new cp.BatchIterator(descriptors)) {
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
          cp.DescribeRequest.mergeDescriptor(mergedDescriptor, descriptor);
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
        cp.MenuInput.actions.focus(`${statePath}.measurement`)(
            dispatch, getState);
      }
    },
  };

  TimeseriesDescriptor.reducers = {
    receiveTestSuites: (state, {suites}, rootState) => {
      const suite = TimeseriesDescriptor.State.suite({suite: {
        isAggregated: state.suite.isAggregated,
        options: suites,
      }});
      return {...state, suite};
    },

    receiveDescriptor: (state, {descriptor}, rootState) => {
      state = {...state};

      state.measurement = {
        ...state.measurement,
        optionValues: descriptor.measurements,
        options: cp.OptionGroup.groupValues(descriptor.measurements),
        label: `Measurements (${descriptor.measurements.size})`,
      };

      const botOptions = cp.OptionGroup.groupValues(descriptor.bots);
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
          options: cp.OptionGroup.groupValues(descriptor.cases),
        });
      }

      state.case = cp.TagFilter.reducers.filter({
        ...state.case,
        optionValues: descriptor.cases,
        options: caseOptions,
        label: `Cases (${descriptor.cases.size})`,
        tags: {
          ...state.case.tags,
          map: descriptor.caseTags,
          optionValues: new Set(descriptor.caseTags.keys()),
          options: cp.OptionGroup.groupValues(descriptor.caseTags.keys()),
        },
      });

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

  cp.ElementBase.register(TimeseriesDescriptor);
  return {TimeseriesDescriptor};
});
