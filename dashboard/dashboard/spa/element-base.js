/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import '@chopsui/tsmon-client';
import 'dashboard-metrics';
import {Debouncer} from '@polymer/polymer/lib/utils/debounce.js';
import * as PolymerAsync from '@polymer/polymer/lib/utils/async.js';
import {PolymerElement} from '@polymer/polymer/polymer-element.js';
import {get} from '@polymer/polymer/lib/utils/path.js';

import {
  DEFAULT_REDUCER_WRAPPERS,
  RESET,
  createSimpleStore,
  freezingReducer,
  registerReducers,
  renameReducer,
} from './simple-redux.js';

import {
  plural,
} from './utils.js';

// Lazily create STORE because Redux might not be loaded yet. In tests, it's
// loaded via an html import, whereas subclasses are loaded via es6 import.
// redux/es/redux.mjs uses require so it doesn't work in webpack.
// redux/es/redux.js uses a bare import so it doesn't work in tests.
let STORE;
function getStore() {
  if (!STORE) {
    STORE = createSimpleStore({
      devtools: {
        // Do not record changes automatically when in a production environment.
        shouldRecordChanges: !window.IS_PRODUCTION,

        // Increase the maximum number of actions stored in the history tree.
        // The oldest actions are removed once maxAge is reached.
        maxAge: 75,
      },
    });
  }
  return STORE;
}

/*
  * This base class mixes PolymerElement with Polymer-Redux and provides
  * utility functions to help data-bindings in elements perform minimal
  * computation without computed properties.
  */
export default class ElementBase extends PolymerElement {
  constructor() {
    super();
    this.debounceJobs_ = new Map();
  }

  connectedCallback() {
    super.connectedCallback();
    this.unsubscribeRedux_ = getStore().subscribe(() =>
      this.stateChanged(this.getState()));
    this.stateChanged(this.getState());
  }

  getState() {
    return getStore().getState();
  }

  dispatch(...args) {
    let [action] = args;
    if (typeof action === 'string') {
      if (typeof this.constructor.actions[action] !== 'function') {
        throw new TypeError(
            `Invalid action creator ${this.constructor.is}.actions.${action}`);
      }
      action = this.constructor.actions[action](...args.slice(1));
    }
    return getStore().dispatch(action);
  }

  stateChanged(rootState) {
    if (!this.statePath) return;
    this.setProperties(get(rootState, this.statePath));
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    this.unsubscribeRedux_();
  }

  add_() {
    let sum = arguments[0];
    for (const arg of Array.from(arguments).slice(1)) {
      sum += arg;
    }
    return sum;
  }

  union_() {
    const results = new Set();
    for (const arg of Array.from(arguments)) {
      if (!arg) continue;
      for (const elem of arg) {
        results.add(elem);
      }
    }
    return [...results];
  }

  isEqual_() {
    const test = arguments[0];
    for (const arg of Array.from(arguments).slice(1)) {
      if (arg !== test) return false;
    }
    return true;
  }

  plural_(count, pluralSuffix = 's', singularSuffix = '') {
    return plural(count, pluralSuffix, singularSuffix);
  }

  lengthOf_(seq) {
    if (seq === undefined) return 0;
    if (seq === null) return 0;
    if (seq instanceof Array || typeof(seq) === 'string') return seq.length;
    if (seq instanceof Map || seq instanceof Set) return seq.size;
    if (seq instanceof tr.v.HistogramSet) return seq.length;
    return Object.keys(seq).length;
  }

  isMultiple_(seq) {
    return this.lengthOf_(seq) > 1;
  }

  isEmpty_(seq) {
    return this.lengthOf_(seq) === 0;
  }

  /**
    * Wrap Debouncer in a friendlier syntax.
    *
    * @param {*} jobName
    * @param {Function()} callback
    * @param {Object=} asyncModule See PolymerAsync.
    */
  debounce(jobName, callback, opt_asyncModule) {
    const asyncModule = opt_asyncModule || PolymerAsync.microTask;
    this.debounceJobs_.set(jobName, Debouncer.debounce(
        this.debounceJobs_.get(jobName), asyncModule, callback));
  }

  static resetStoreForTest() {
    getStore().dispatch(RESET);
  }
}

if (window.location.hostname === 'localhost') {
  // timeReducer should appear before freezingReducer so that the timing
  // doesn't include the overhead from freezingReducer. statePathReducer must
  // be last because it changes the function signature.
  DEFAULT_REDUCER_WRAPPERS.splice(1, 0, freezingReducer);
}

ElementBase.register = subclass => {
  customElements.define(subclass.is, subclass);
  if (subclass.reducers) {
    registerReducers(subclass.reducers, [
      renameReducer(subclass.name + '.'),
      ...DEFAULT_REDUCER_WRAPPERS,
    ]);
  }
};
