/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';
tr.exportTo('cp', () => {
  class RecommendedOptions extends cp.ElementBase {
    ready() {
      super.ready();
      if (!this.optionRecommendations) this.dispatch('getRecommendations');
    }

    observeOptionValues_(newOptionValues, oldOptionValues) {
      this.dispatch('recommendOptions', this.statePath);
    }

    observeSelectedOptions_(newSelectedOptions, oldSelectedOptions) {
      // This can't just listen for option-select because that only fires when
      // the user selects a recommended option.
      if (!newSelectedOptions || !oldSelectedOptions) return;
      const addedOptions = newSelectedOptions.filter(o =>
        !oldSelectedOptions.includes(o));
      if (addedOptions.length !== 1) return;
      // Ignore when users deselect options or select whole groups of options.
      this.dispatch('updateRecommendations', addedOptions[0]);
    }
  }

  RecommendedOptions.State = {
    ...cp.OptionGroup.RootState,
    ...cp.OptionGroup.State,
    recommended: options => options.recommended || {},
  };

  RecommendedOptions.buildState = options => cp.buildState(
      RecommendedOptions.State, options);

  RecommendedOptions.properties = {
    ...cp.buildProperties('state', RecommendedOptions.State),
    optionRecommendations: {statePath: 'optionRecommendations'},
  };

  RecommendedOptions.properties.selectedOptions.observer =
    'observeSelectedOptions_';
  RecommendedOptions.properties.optionValues.observer =
    'observeOptionValues_';

  RecommendedOptions.actions = {
    getRecommendations: () => async(dispatch, getState) => {
      dispatch({type: RecommendedOptions.reducers.getRecommendations.name});
    },

    recommendOptions: statePath => async(dispatch, getState) => {
      dispatch({
        type: RecommendedOptions.reducers.recommendOptions.name,
        statePath,
      });
    },

    updateRecommendations: addedOption => async(dispatch, getState) => {
      dispatch({
        type: RecommendedOptions.reducers.updateRecommendations.name,
        addedOption,
      });
    },
  };

  RecommendedOptions.STORAGE_KEY = 'optionRecommendations';
  RecommendedOptions.OLD_MS = tr.b.convertUnit(
      12, tr.b.UnitScale.TIME.WEEK, tr.b.UnitScale.TIME.MILLI_SEC);
  RecommendedOptions.OPTION_LIMIT = 5;

  RecommendedOptions.reducers = {
    getRecommendations: (rootState) => {
      let optionRecommendations;
      const now = new Date().getTime();
      try {
        optionRecommendations = JSON.parse(localStorage.getItem(
            RecommendedOptions.STORAGE_KEY));
        for (const [value, dates] of Object.entries(optionRecommendations)) {
          optionRecommendations[value] = dates.map(d => new Date(d)).filter(
              date => ((now - date) < RecommendedOptions.OLD_MS));
        }
      } catch (err) {
        // eslint-disable-next-line no-console
        console.error('Error getting stored recommendations', err);
        optionRecommendations = {};
      }
      return {...rootState, optionRecommendations};
    },

    recommendOptions: (state, action, rootState) => {
      const optionValues = RecommendedOptions.recommendOptions(
          state.optionValues, rootState.optionRecommendations).slice(
          0, RecommendedOptions.OPTION_LIMIT);
      const recommended = {
        optionValues,
        options: cp.OptionGroup.groupValues(optionValues),
      };
      return {...state, recommended};
    },

    updateRecommendations: (rootState, {addedOption}) => {
      const optionRecommendations = {
        ...rootState.optionRecommendations,
        [addedOption]: [
          new Date(),
          ...(rootState.optionRecommendations[addedOption] || []),
        ],
      };
      try {
        localStorage.setItem(RecommendedOptions.STORAGE_KEY,
            JSON.stringify(optionRecommendations));
      } catch (err) {
        // eslint-disable-next-line no-console
        console.error('Error updating optionRecommendations', err);
      }
      return {...rootState, optionRecommendations};
    },
  };

  function score(dates, now) {
    if (!dates) return 0;
    return tr.b.math.Statistics.sum(dates, date => (1 / (now - date)));
  }

  RecommendedOptions.recommendOptions = (values, recommendations) => {
    if (!recommendations) return [];
    const now = new Date();
    const recommended = [];
    for (const value of values) {
      const s = score(recommendations[value], now);
      if (s <= 0) continue;
      recommended.push({value, score: s});
    }
    recommended.sort((valueA, valueB) => valueB.score - valueA.score);
    return recommended.map(v => v.value);
  };

  cp.ElementBase.register(RecommendedOptions);
  return {RecommendedOptions};
});
