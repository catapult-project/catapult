/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import * as Redux from 'redux';
import {deepFreeze} from './utils.js';
import {set} from 'dot-prop-immutable';

// See architecture.md for background and explanations.

// Maps from string action type to synchronous
// function(!Object state, !Object action):!Object state.
const REDUCERS = new Map();

function rootReducer(state, action) {
  if (state === undefined) state = {};
  const reducer = REDUCERS.get(action.type);
  if (reducer === undefined) return state;
  return reducer(state, action);
}

export function createSimpleStore({
  middleware,
  defaultState = {},
  devtools = {},
  useThunk = true} = {}) {
  if (useThunk) {
    // This is all that is needed from redux-thunk to enable asynchronous action
    // creators.
    const thunk = Redux.applyMiddleware(store => next => action => {
      if (typeof action === 'function') {
        return action(store.dispatch, store.getState);
      }
      return next(action);
    });

    if (middleware) {
      middleware = Redux.compose(middleware, thunk);
    } else {
      middleware = thunk;
    }
  } else if (!middleware) {
    middleware = Redux.applyMiddleware();
  }
  if (window.__REDUX_DEVTOOLS_EXTENSION_COMPOSE__) {
    middleware = window.__REDUX_DEVTOOLS_EXTENSION_COMPOSE__(
        devtools)(middleware);
  }
  return Redux.createStore(rootReducer, defaultState, middleware);
}

/*
  * Register a case function by name in a central Map.
  *
  * Usage:
  * function foo(state, action) { ... }
  * registerReducer(foo);
  * dispatch({type: foo.name, ...});
  */
export const registerReducer = reducer => REDUCERS.set(reducer.name, reducer);

/*
  * Wrap a case function in set so that it can update a node in the
  * state tree denoted by action.statePath.
  *
  * Usage: registerReducer(statePathReducer(
  *   function foo(state, action) { return {...state, ...changes}; }));
  * dispatch({type: 'foo', statePath: this.statePath})
  */
export const statePathReducer = reducer => {
  const replacement = (rootState, action) => {
    if (!action.statePath) return reducer(rootState, action, rootState);
    return set(rootState, action.statePath, state =>
      reducer(state, action, rootState));
  };
  Object.defineProperty(replacement, 'name', {value: reducer.name});
  return replacement;
};

/*
  * Wrap a case function to deepFreeze the state object so that it will throw
  * an exception when it tries to modify the state object.
  * Warning! This incurs a significant performance penalty! Only use it for
  * debugging!
  */
export const freezingReducer = reducer => {
  const replacement = (rootState, ...args) => {
    deepFreeze(rootState);
    return reducer(rootState, ...args);
  };
  Object.defineProperty(replacement, 'name', {value: reducer.name});
  return replacement;
};

/*
  * Wrap a case function with tr.b.Timing.mark().
  */
export const timeReducer = (category = 'reducer') => reducer => {
  const replacement = (...args) => {
    const mark = tr.b.Timing.mark(category, reducer.name);
    try {
      return reducer.apply(this, args);
    } finally {
      mark.end();
    }
  };
  Object.defineProperty(replacement, 'name', {value: reducer.name});
  return replacement;
};

/*
  * Prepend a prefix to a function's name.
  * Multiple web components may name their reducers using common words. Using
  * this wrapper prevents name collisions in the central REDUCERS map.
  * This curries so it can be used with registerReducers().
  * This makes reducer.name immutable.
  *
  * Usage: renameReducer('FooElement.')(FooElement.reducers.frob);
  */
export const renameReducer = prefix => reducer => {
  Object.defineProperty(reducer, 'name', {value: prefix + reducer.name});
  return reducer;
};

export const DEFAULT_REDUCER_WRAPPERS = [timeReducer(), statePathReducer];

function wrap(wrapped, wrapper) {
  return wrapper(wrapped);
}

/*
  * Wrap and register an entire namespace of case functions.
  * timeReducer should appear before freezingReducer so that the timing
  * doesn't include the overhead from freezingReducer.
  * statePathReducer must be last because it changes the function signature.
  *
  * Usage:
  * registerReducers(FooElement.reducers,
  * [renameReducer('FooElement.reducers.'),
  * ...DEFAULT_REDUCER_WRAPPERS]);
  */
export const registerReducers = (obj, wrappers = DEFAULT_REDUCER_WRAPPERS) => {
  for (const [name, reducer] of Object.entries(obj)) {
    registerReducer(wrappers.reduce(wrap, reducer));
  }
};

/*
  * Chain together independent case functions without re-rendering state to DOM
  * in between and without requiring case functions to always call other case
  * functions.
  *
  * Usage: dispatch(CHAIN(
  * {type: 'foo', statePath: 'x.0'}, {type: 'bar', statePath: 'y.1'}));
  */
registerReducer(function CHAIN(rootState, {actions}) {
  return actions.reduce(rootReducer, rootState);
});

export const CHAIN = (...actions) => {return {type: 'CHAIN', actions};};

/*
  * Update an object in the state tree denoted by `action.statePath`.
  *
  * Usage:
  * dispatch(UPDATE('x.0.y', {title}));
  */
registerReducer(statePathReducer(function UPDATE(state, {delta}) {
  return {...state, ...delta};
}));

export const UPDATE = (statePath, delta) => {
  return {type: 'UPDATE', statePath, delta};
};

/*
  * Ensure an object exists in the state tree. If it already exists, it is not
  * modified. If it does not yet exist, it is initialized to `defaultState`.
  *
  * Usage:
  * dispatch(ENSURE('x.0.y', []));
  */
registerReducer(statePathReducer(
    function ENSURE(state, {defaultState = {}}) {
      return state || defaultState;
    }));

export const ENSURE = (statePath, defaultState) => {
  return {type: 'ENSURE', statePath, defaultState};
};

/*
  * Toggle booleans in the state tree denoted by `action.statePath`.
  *
  * Usage:
  * dispatch(TOGGLE(`${this.statePath}.isEnabled`));
  */
registerReducer(statePathReducer(function TOGGLE(state) {
  return !state;
}));

export const TOGGLE = statePath => {return {type: 'TOGGLE', statePath};};

registerReducer(function RESET(rootState, {state = {}}) {
  return state;
});
export const RESET = {type: 'RESET'};
