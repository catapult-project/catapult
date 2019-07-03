/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import {ElementBase, STORE} from './element-base.js';
import {OptionGroup} from './option-group.js';
import {get} from 'dot-prop-immutable';
import {html, css} from 'lit-element';

const DEFAULT_RECOMMENDATIONS = [
  'Chromium Perf Sheriff',
  'memory:chrome:all_processes:reported_by_chrome:effective_size',
];

export class RecommendedOptions extends ElementBase {
  static get is() { return 'recommended-options'; }

  static get properties() {
    return {
      ...OptionGroup.properties,
      recommended: Object,
      optionRecommendations: Array,
    };
  }

  static buildState(options) {
    return {
      ...OptionGroup.buildState(options),
      recommended: options.recommended || {},
    };
  }

  static get styles() {
    return css`
      option-group {
        border-bottom: 1px solid var(--primary-color-dark, blue);
      }
    `;
  }

  render() {
    if (!this.recommended || !this.recommended.options ||
        !this.recommended.options.length) {
      return html``;
    }

    if (this.query) {
      const queryParts = this.query.toLocaleLowerCase().split(' ');
      if (!this.recommended.options.filter(o => OptionGroup.matches(
          o, queryParts)).length) {
        return html``;
      }
    }

    return html`
      <b style="margin: 4px;">Recommended</b>
      <option-group
          .statePath="${this.statePath}.recommended"
          .rootStatePath="${this.statePath}">
      </option-group>
    `;
  }

  firstUpdated() {
    if (!this.optionRecommendations) {
      STORE.dispatch({
        type: RecommendedOptions.reducers.getRecommendations.name,
      });
    }
  }

  stateChanged(rootState) {
    if (!this.statePath) return;

    this.optionRecommendations = rootState.optionRecommendations;
    const oldSelectedOptions = this.selectedOptions;
    const oldOptionValues = this.optionValues;
    Object.assign(this, get(rootState, this.statePath));

    if (this.optionValues && this.optionValues !== oldOptionValues) {
      STORE.dispatch({
        type: RecommendedOptions.reducers.recommendOptions.name,
        statePath: this.statePath,
      });
    }
    if (this.selectedOptions !== oldSelectedOptions &&
        oldSelectedOptions && this.selectedOptions) {
      // This can't just listen for option-select because that only fires when
      // the user selects a recommended option.
      const addedOptions = this.selectedOptions.filter(o =>
        !oldSelectedOptions.includes(o));
      // Ignore when users deselect options or select whole groups of options.
      if (addedOptions.length === 1) {
        STORE.dispatch({
          type: RecommendedOptions.reducers.updateRecommendations.name,
          addedOption: addedOptions[0],
        });
      }
    }
  }
}

RecommendedOptions.STORAGE_KEY = 'optionRecommendations';
RecommendedOptions.OPTION_LIMIT = 5;
RecommendedOptions.OLD_MS = 1000 * 60 * 60 * 24 * 7 * 12;

RecommendedOptions.reducers = {
  getRecommendations: (rootState) => {
    let optionRecommendations;
    const now = new Date().getTime();
    try {
      optionRecommendations = JSON.parse(localStorage.getItem(
          RecommendedOptions.STORAGE_KEY)) || {};

      for (const value of DEFAULT_RECOMMENDATIONS) {
        if (!(value in optionRecommendations)) {
          optionRecommendations[value] = [now];
        }
      }

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
    if (!state) return state;
    const optionValues = RecommendedOptions.recommendOptions(
        state.optionValues, rootState.optionRecommendations).slice(
        0, RecommendedOptions.OPTION_LIMIT);
    const recommended = {
      optionValues,
      options: OptionGroup.groupValues(optionValues),
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
  if (!values || !recommendations) return [];
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

ElementBase.register(RecommendedOptions);
