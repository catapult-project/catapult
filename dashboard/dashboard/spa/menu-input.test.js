/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import MenuInput from './menu-input.js';
import {STORE} from './element-base.js';
import {UPDATE} from './simple-redux.js';
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
});
