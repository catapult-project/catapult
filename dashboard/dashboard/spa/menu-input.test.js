/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import MenuInput from './menu-input.js';
import {STORE} from './element-base.js';
import {CHAIN, UPDATE} from './simple-redux.js';
import {assert} from 'chai';
import {afterRender} from './utils.js';

suite('menu-input', function() {
  teardown(() => {
    for (const child of document.body.querySelectorAll('menu-input')) {
      document.body.removeChild(child);
    }
  });

  test('focus', async function() {
    const xxxInput = document.createElement('menu-input');
    xxxInput.statePath = 'xxx';
    const yyyInput = document.createElement('menu-input');
    yyyInput.statePath = 'yyy';
    await STORE.dispatch(UPDATE('', {
      xxx: MenuInput.buildState({
        label: 'XXX',
        options: new Set([
          'aaa',
          'bbb:ccc',
          'bbb:ddd',
          'bbb:ddd:eee',
          'bbb:ddd:fff',
        ]),
      }),
      yyy: MenuInput.buildState({
        label: 'YYY',
        options: new Set([
          'aaa',
          'bbb:ccc',
          'bbb:ddd',
          'bbb:ddd:eee',
          'bbb:ddd:fff',
        ]),
      }),
    }));
    document.body.appendChild(xxxInput);
    document.body.appendChild(yyyInput);
    await afterRender();
    xxxInput.nativeInput.click();
    assert.isTrue(xxxInput.isFocused);
    assert.isFalse(yyyInput.isFocused);

    yyyInput.nativeInput.click();
    assert.isFalse(xxxInput.isFocused);
    assert.isTrue(yyyInput.isFocused);
  });

  test('inputValue', async function() {
    assert.strictEqual('q', MenuInput.inputValue(true, 'q', undefined));
    assert.strictEqual('', MenuInput.inputValue(false, 'q', undefined));
    assert.strictEqual('', MenuInput.inputValue(false, 'q', []));
    assert.strictEqual('o', MenuInput.inputValue(false, 'q', ['o']));
    assert.strictEqual('[2 selected]', MenuInput.inputValue(
        false, 'q', ['o', 'p']));
  });

  function press(key) {
    STORE.dispatch({
      type: MenuInput.reducers.arrowCursor.name,
      statePath: 'test',
      key,
    });
  }

  test('ArrowDown initial', async function() {
    STORE.dispatch(UPDATE('', {
      test: MenuInput.buildState({
        options: new Set([
          'a', 'b:0', 'b:1:a', 'b:1:b', 'b:1:c', 'b:2', 'c',
        ]),
      }),
    }));

    press('ArrowDown');
    assert.strictEqual('test.options.0', STORE.getState().test.cursor);
  });

  test('ArrowUp initial', async function() {
    STORE.dispatch(UPDATE('', {
      test: MenuInput.buildState({
        options: new Set([
          'a', 'b:0', 'b:1:a', 'b:1:b', 'b:1:c', 'b:2', 'c',
        ]),
      }),
    }));

    press('ArrowUp');
    assert.strictEqual('test.options.2', STORE.getState().test.cursor);
  });

  test('ArrowUp boundary', async function() {
    STORE.dispatch(UPDATE('', {
      test: MenuInput.buildState({
        options: new Set([
          'a', 'b:0', 'b:1:a', 'b:1:b', 'b:1:c', 'b:2', 'c',
        ]),
        cursor: 'test.options.0',
      }),
    }));

    press('ArrowUp');
    assert.strictEqual('test.options.2', STORE.getState().test.cursor);
  });

  test('ArrowUp embedded boundary', async function() {
    STORE.dispatch(UPDATE('', {
      test: MenuInput.buildState({
        options: new Set([
          'a', 'b:0', 'b:1:a', 'b:1:b', 'b:1:c', 'b:2', 'c',
        ]),
        cursor: 'test.options.1.options.0',
      }),
    }));

    press('ArrowUp');
    assert.strictEqual('test.options.1', STORE.getState().test.cursor);
  });

  test('ArrowDown embedded', async function() {
    STORE.dispatch(CHAIN(
        UPDATE('', {
          test: MenuInput.buildState({
            options: new Set([
              'a', 'b:0', 'b:1:a', 'b:1:b', 'b:1:c', 'b:2', 'c',
            ]),
            cursor: 'test.options.1',
          }),
        }),
        UPDATE('test.options.1', {isExpanded: true})));

    press('ArrowDown');
    assert.strictEqual('test.options.1.options.0',
        STORE.getState().test.cursor);
  });

  test('ArrowDown boundary', async function() {
    STORE.dispatch(UPDATE('', {
      test: MenuInput.buildState({
        options: new Set([
          'a', 'b:0', 'b:1:a', 'b:1:b', 'b:1:c', 'b:2', 'c',
        ]),
        cursor: 'test.options.2',
      }),
    }));

    press('ArrowDown');
    assert.strictEqual('test.options.0', STORE.getState().test.cursor);
  });

  test('ArrowUp simple', async function() {
    STORE.dispatch(UPDATE('', {
      test: MenuInput.buildState({
        options: new Set([
          'a', 'b:0', 'b:1:a', 'b:1:b', 'b:1:c', 'b:2', 'c',
        ]),
        cursor: 'test.options.1',
      }),
    }));

    press('ArrowUp');
    assert.strictEqual('test.options.0', STORE.getState().test.cursor);
  });

  test('ArrowDown simple', async function() {
    STORE.dispatch(UPDATE('', {
      test: MenuInput.buildState({
        options: new Set([
          'a', 'b:0', 'b:1:a', 'b:1:b', 'b:1:c', 'b:2', 'c',
        ]),
        cursor: 'test.options.0',
      }),
    }));

    press('ArrowDown');
    assert.strictEqual('test.options.1', STORE.getState().test.cursor);
  });

  test('ArrowUp complex', async function() {
    STORE.dispatch(CHAIN(
        UPDATE('', {
          test: MenuInput.buildState({
            options: new Set([
              'a', 'b:0', 'b:1:a', 'b:1:b', 'b:1:c', 'c',
            ]),
            cursor: 'test.options.2',
          }),
        }),
        UPDATE('test.options.1', {isExpanded: true}),
        UPDATE('test.options.1.options.1', {isExpanded: true})));

    press('ArrowUp');
    assert.strictEqual('test.options.1.options.1.options.2',
        STORE.getState().test.cursor);
  });

  test('ArrowDown complex', async function() {
    STORE.dispatch(CHAIN(
        UPDATE('', {
          test: MenuInput.buildState({
            options: new Set([
              'a', 'b:0', 'b:1:a', 'b:1:b', 'b:1:c', 'c',
            ]),
            cursor: 'test.options.1.options.1.options.2',
          }),
        }),
        UPDATE('test.options.1', {isExpanded: true}),
        UPDATE('test.options.1.options.1', {isExpanded: true})));

    press('ArrowDown');
    assert.strictEqual('test.options.2', STORE.getState().test.cursor);
  });

  test('ArrowLeft n/a', async function() {
    STORE.dispatch(UPDATE('', {
      test: MenuInput.buildState({
        options: new Set([
          'a', 'b:0', 'b:1:a', 'b:1:b', 'b:1:c', 'b:2', 'c',
        ]),
      }),
    }));

    press('ArrowLeft');
    // Nothing should happen.

    STORE.dispatch(UPDATE('test', {cursor: 'test.options.9'}));

    press('ArrowLeft');
    // Nothing should happen.
  });

  test('ArrowLeft simple', async function() {
    STORE.dispatch(CHAIN(
        UPDATE('', {
          test: MenuInput.buildState({
            options: new Set([
              'a', 'b:0', 'b:1:a', 'b:1:b', 'b:1:c', 'c',
            ]),
            cursor: 'test.options.1',
          }),
        }),
        UPDATE('test.options.1', {isExpanded: true})));

    press('ArrowLeft');
    assert.isFalse(STORE.getState().test.options[1].isExpanded);
  });

  test('ArrowLeft complex', async function() {
    STORE.dispatch(CHAIN(
        UPDATE('', {
          test: MenuInput.buildState({
            options: new Set([
              'a', 'b:0', 'b:1:a', 'b:1:b', 'b:1:c', 'c',
            ]),
            cursor: 'test.options.1.options.0',
          }),
        }),
        UPDATE('test.options.1', {isExpanded: true})));

    press('ArrowLeft');
    assert.isFalse(STORE.getState().test.options[1].isExpanded);
    assert.strictEqual('test.options.1', STORE.getState().test.cursor);
  });

  test('ArrowRight n/a', async function() {
    STORE.dispatch(UPDATE('', {
      test: MenuInput.buildState({
        options: new Set([
          'a', 'b:0', 'b:1:a', 'b:1:b', 'b:1:c', 'b:2', 'c',
        ]),
      }),
    }));

    press('ArrowRight');
    // Nothing should happen.

    STORE.dispatch(UPDATE('test', {cursor: 'test.options.0'}));

    press('ArrowRight');
    // Nothing should happen.

    STORE.dispatch(UPDATE('test', {cursor: 'test.options.1'}));
    STORE.dispatch(UPDATE('test.options.1', {isExpanded: true}));
    press('ArrowRight');
    // Nothing should happen.
  });

  test('ArrowRight success', async function() {
    STORE.dispatch(CHAIN(
        UPDATE('', {
          test: MenuInput.buildState({
            options: new Set([
              'a', 'b:0', 'b:1:a', 'b:1:b', 'b:1:c', 'c',
            ]),
            cursor: 'test.options.1',
          }),
        }),
        UPDATE('test.options.1', {isExpanded: true})));

    press('ArrowRight');
    assert.isTrue(STORE.getState().test.options[1].isExpanded);
  });

  test('ArrowUp query', async function() {
    STORE.dispatch(UPDATE('', {
      test: MenuInput.buildState({
        options: new Set([
          'aq', 'b', 'c', 'd', 'eq',
        ]),
        query: 'q',
        cursor: 'test.options.4',
      }),
    }));

    press('ArrowUp');
    assert.strictEqual('test.options.0', STORE.getState().test.cursor);
  });

  test('ArrowDown query', async function() {
    STORE.dispatch(UPDATE('', {
      test: MenuInput.buildState({
        options: new Set([
          'aq', 'b', 'c', 'd', 'eq',
        ]),
        query: 'q',
        cursor: 'test.options.0',
      }),
    }));

    press('ArrowUp');
    assert.strictEqual('test.options.4', STORE.getState().test.cursor);
  });
});
