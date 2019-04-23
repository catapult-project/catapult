/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import {
  DEFAULT_REDUCER_WRAPPERS,
  createSimpleStore,
  freezingReducer,
  registerReducers,
  renameReducer,
} from './simple-redux.js';

import {
  plural,
} from './utils.js';

const ReduxMixin = PolymerRedux(createSimpleStore({
  devtools: {
    // Do not record changes automatically when in a production environment.
    shouldRecordChanges: !window.IS_PRODUCTION,

    // Increase the maximum number of actions stored in the history tree. The
    // oldest actions are removed once maxAge is reached.
    maxAge: 75,
  },
}));

/*
  * This base class mixes Polymer.Element with Polymer-Redux and provides
  * utility functions to help data-bindings in elements perform minimal
  * computation without computed properties.
  */
export default class ElementBase extends ReduxMixin(Polymer.Element) {
  constructor() {
    super();
    this.debounceJobs_ = new Map();
  }

  add_() {
    let sum = arguments[0];
    for (const arg of Array.from(arguments).slice(1)) {
      sum += arg;
    }
    return sum;
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
    * Wrap Polymer.Debouncer in a friendlier syntax.
    *
    * @param {*} jobName
    * @param {Function()} callback
    * @param {Object=} asyncModule See Polymer.Async.
    */
  debounce(jobName, callback, opt_asyncModule) {
    const asyncModule = opt_asyncModule || Polymer.Async.microTask;
    this.debounceJobs_.set(jobName, Polymer.Debouncer.debounce(
        this.debounceJobs_.get(jobName), asyncModule, callback));
  }

  // This is used to bind state properties in `buildProperties()` in utils.js.
  identity_(x) { return x; }
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
