/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import '@chopsui/tsmon-client';
import 'dashboard-metrics';
import * as PolymerAsync from '@polymer/polymer/lib/utils/async.js';
import {Debouncer} from '@polymer/polymer/lib/utils/debounce.js';
import {LitElement} from 'lit-element';
import {get} from 'dot-prop-immutable';
import {isDebug, isProduction} from './utils.js';

import {
  DEFAULT_REDUCER_WRAPPERS,
  UPDATE,
  createSimpleStore,
  freezingReducer,
  registerReducers,
  renameReducer,
} from './simple-redux.js';

export const STORE = createSimpleStore({
  devtools: {
    // Do not record changes automatically when in a production environment.
    shouldRecordChanges: !isProduction(),

    // Increase the maximum number of actions stored in the history tree.
    // The oldest actions are removed once maxAge is reached.
    maxAge: 75,
  },
});

// Export the state store directly to window in order to facilitate debugging.
window.STORE = STORE;

/*
 * This base class mixes LitElement with Polymer-Redux and provides
 * utility functions to help data-bindings in elements perform minimal
 * computation without computed properties.
 */
export class ElementBase extends LitElement {
  constructor() {
    super();
    this.debounceJobs_ = new Map();
  }

  connectedCallback() {
    super.connectedCallback();
    this.unsubscribeRedux_ = STORE.subscribe(() =>
      this.stateChanged(STORE.getState()));
    this.stateChanged(STORE.getState());
  }

  stateChanged(rootState) {
    if (!this.statePath) return;
    Object.assign(this, get(rootState, this.statePath));
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    this.unsubscribeRedux_();
  }

  /**
    * Wrap Debouncer in a friendlier syntax.
    *
    * @param {*} jobName
    * @param {Function()} callback
    * @param {Object=} asyncModule See PolymerAsync.
    */
  debounce(jobName, callback, asyncModule = PolymerAsync.animationFrame) {
    this.debounceJobs_.set(jobName, Debouncer.debounce(
        this.debounceJobs_.get(jobName), asyncModule, callback));
  }
}

if (isDebug()) {
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

export function maybeScheduleAutoReload(
    statePath, pred, callback, ms = (1000 * 60 * 60)) {
  const state = get(STORE.getState(), statePath);
  if (!state) return;
  if (state.reloadTimer) window.clearTimeout(state.reloadTimer);
  let reloadTimer;
  if (pred(state)) {
    // Automatically reload after some time.
    reloadTimer = window.setTimeout(callback, ms);
  }
  STORE.dispatch(UPDATE(statePath, {reloadTimer}));
}
