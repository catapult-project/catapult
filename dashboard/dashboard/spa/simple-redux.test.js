/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import {assert} from 'chai';
import * as SimpleRedux from './simple-redux.js';

suite('simple-redux', function() {
  test('renameReducer', function() {
    function cer() {}
    const renamer = SimpleRedux.renameReducer('redu');
    renamer(cer);
    assert.strictEqual('reducer', cer.name);
  });

  test('registerReducer', function() {
    function testRegisterReducer(state, action) {
      return {...state, test: action.testValue};
    }
    SimpleRedux.registerReducer(testRegisterReducer);
    const store = SimpleRedux.createSimpleStore();
    store.dispatch({type: testRegisterReducer.name, testValue: 42});
    assert.strictEqual(42, store.getState().test);
  });

  test('registerReducers', function() {
    const reducers = {
      a(localState, {a}, rootState) {
        return {...localState, a};
      },
      b(localState, {b}, rootState) {
        localState.b = b;
      },
    };
    SimpleRedux.registerReducers(reducers, [
      SimpleRedux.renameReducer('namespace.'),
      SimpleRedux.freezingReducer,
      SimpleRedux.statePathReducer,
    ]);
    const store = SimpleRedux.createSimpleStore();
    store.dispatch(SimpleRedux.UPDATE('', {b: {}}));

    store.dispatch({type: reducers.a.name, statePath: 'b', a: ''});
    assert.strictEqual('', store.getState().b.a);

    assert.throws(() => store.dispatch({
      type: reducers.b.name,
      statePath: '',
      b: '',
    }));
  });

  test('statePathReducer', function() {
    const reducer = SimpleRedux.statePathReducer((localState, action) => {
      return {...localState, test: action.testValue};
    });
    assert.deepEqual({a: [{b: {pre: 1, test: 'c'}}]}, reducer(
        {a: [{b: {pre: 1}}]}, {statePath: 'a.0.b', testValue: 'c'}));
  });

  test('freezingReducer', function() {
    const reducer = SimpleRedux.freezingReducer((state, action) => {
      state.modification = 'error';
    });
    assert.throws(() => reducer({}, {}));
  });

  test('timeReducer', function() {
    function testRegisterReducer(state, action) {
      return {...state, test: action.testValue};
    }
    SimpleRedux.registerReducer(SimpleRedux.timeReducer()(testRegisterReducer));
    const store = SimpleRedux.createSimpleStore();
    store.dispatch({type: testRegisterReducer.name, testValue: 42});
    assert.isBelow(0, window.performance.getEntriesByName(
        'reducer testRegisterReducer').length);
  });

  test('thunk', function() {
    const store = SimpleRedux.createSimpleStore();
    const actionCreator = (testValue) => (dispatch, getState) => {
      dispatch(SimpleRedux.UPDATE('', {testValue}));
    };
    store.dispatch(actionCreator(42));
    assert.strictEqual(42, store.getState().testValue);
  });

  test('nothunk', function() {
    const store = SimpleRedux.createSimpleStore({useThunk: false});
    const actionCreator = (testValue) => (dispatch, getState) => {
      dispatch(SimpleRedux.UPDATE('', {testValue}));
    };
    assert.throws(() => store.dispatch(actionCreator(42)));
  });

  test('CHAIN', function() {
    const store = SimpleRedux.createSimpleStore();
    store.dispatch(SimpleRedux.CHAIN(
        SimpleRedux.UPDATE('a', {testValue: 0}),
        SimpleRedux.UPDATE('b', {testValue: 1}),
    ));
    assert.strictEqual(0, store.getState().a.testValue);
    assert.strictEqual(1, store.getState().b.testValue);
  });

  test('UPDATE', function() {
    const store = SimpleRedux.createSimpleStore();
    store.dispatch(SimpleRedux.UPDATE('a', {testValue: 42}));
    assert.strictEqual(42, store.getState().a.testValue);
  });

  test('TOGGLE', function() {
    const store = SimpleRedux.createSimpleStore({
      defaultState: {testValue: false},
    });
    store.dispatch(SimpleRedux.TOGGLE('testValue'));
    assert.isTrue(store.getState().testValue);
  });
});
