/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

// See architecture.md for background and explanations.

// TODO(benjhayden) Export as ES6 module instead of modifying Redux.

(() => {
  // Maps from string action type to synchronous
  // function(!Object state, !Object action):!Object state.
  const REDUCERS = new Map();

  function rootReducer(state, action) {
    if (state === undefined) state = {};
    const reducer = REDUCERS.get(action.type);
    if (reducer === undefined) return state;
    return reducer(state, action);
  }

  // This is all that is needed from redux-thunk to enable asynchronous action
  // creators.
  const THUNK = Redux.applyMiddleware(store => next => action => {
    if (typeof action === 'function') {
      return action(store.dispatch, store.getState);
    }
    return next(action);
  });

  Redux.createSimpleStore = ({
    middleware,
    defaultState = {},
    devtools = {},
    useThunk = true} = {}) => {
    if (useThunk) {
      if (middleware) {
        middleware = Redux.compose(middleware, THUNK);
      } else {
        middleware = THUNK;
      }
    } else if (!middleware) {
      middleware = Redux.applyMiddleware();
    }
    if (window.__REDUX_DEVTOOLS_EXTENSION_COMPOSE__) {
      middleware = window.__REDUX_DEVTOOLS_EXTENSION_COMPOSE__(
          devtools)(middleware);
    }
    return Redux.createStore(rootReducer, defaultState, middleware);
  };

  /*
   * Register a case function by name in a central Map.
   *
   * Usage:
   * function foo(state, action) { ... }
   * Redux.registerReducer(foo);
   * dispatch({type: foo.name, ...});
   */
  Redux.registerReducer = reducer => REDUCERS.set(reducer.name, reducer);

  /*
   * Wrap a case function in setImmutable so that it can update a node in the
   * state tree denoted by action.statePath.
   *
   * Usage: Redux.registerReducer(Redux.statePathReducer(
   *   function foo(state, action) { return {...state, ...changes}; }));
   * dispatch({type: 'foo', statePath: this.statePath})
   */
  Redux.statePathReducer = reducer => {
    const replacement = (rootState, action) => {
      if (!action.statePath) return reducer(rootState, action, rootState);
      return cp.setImmutable(rootState, action.statePath, state =>
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
  Redux.freezingReducer = reducer => {
    const replacement = (rootState, action) => {
      cp.deepFreeze(rootState);
      return reducer(rootState, action);
    };
    Object.defineProperty(replacement, 'name', {value: reducer.name});
    return replacement;
  };

  /*
   * Wrap a case function with tr.b.Timing.mark().
   */
  Redux.timeReducer = (category = 'reducer') => reducer => {
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
   * Usage: Redux.renameReducer('FooElement.')(FooElement.reducers.frob);
   */
  Redux.renameReducer = prefix => reducer => {
    Object.defineProperty(reducer, 'name', {value: prefix + reducer.name});
    return reducer;
  };

  Redux.DEFAULT_REDUCER_WRAPPERS = [
    Redux.timeReducer(),
    Redux.statePathReducer,
  ];

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
   * Redux.registerReducers(FooElement.reducers,
   * [Redux.renameReducer('FooElement.reducers.'),
   * ...Redux.DEFAULT_REDUCER_WRAPPERS]);
   */
  Redux.registerReducers = (obj, wrappers = Redux.DEFAULT_REDUCER_WRAPPERS) => {
    for (const [name, reducer] of Object.entries(obj)) {
      Redux.registerReducer(wrappers.reduce(wrap, reducer));
    }
  };

  /*
   * Chain together independent case functions without re-rendering state to DOM
   * in between and without requiring case functions to always call other case
   * functions.
   *
   * Usage: dispatch(Redux.CHAIN(
   * {type: 'foo', statePath: 'x.0'}, {type: 'bar', statePath: 'y.1'}));
   */
  Redux.registerReducer(function CHAIN(rootState, {actions}) {
    return actions.reduce(rootReducer, rootState);
  });

  Redux.CHAIN = (...actions) => {return {type: 'CHAIN', actions};};

  /*
   * Update an object in the state tree denoted by `action.statePath`.
   *
   * Usage:
   * dispatch(Redux.UPDATE('x.0.y', {title}));
   */
  Redux.registerReducer(Redux.statePathReducer(function UPDATE(state, {delta}) {
    return {...state, ...delta};
  }));

  Redux.UPDATE = (statePath, delta) => {
    return {type: 'UPDATE', statePath, delta};
  };

  /*
   * Ensure an object exists in the state tree. If it already exists, it is not
   * modified. If it does not yet exist, it is initialized to `defaultState`.
   *
   * Usage:
   * dispatch(Redux.ENSURE('x.0.y', []));
   */
  Redux.registerReducer(Redux.statePathReducer(
      function ENSURE(state, {defaultState = {}}) {
        return state || defaultState;
      }));

  Redux.ENSURE = (statePath, defaultState) => {
    return {type: 'ENSURE', statePath, defaultState};
  };

  /*
   * Toggle booleans in the state tree denoted by `action.statePath`.
   *
   * Usage:
   * dispatch(Redux.TOGGLE(`${this.statePath}.isEnabled`));
   */
  Redux.registerReducer(Redux.statePathReducer(function TOGGLE(state) {
    return !state;
  }));

  Redux.TOGGLE = statePath => {return {type: 'TOGGLE', statePath};};
})();
