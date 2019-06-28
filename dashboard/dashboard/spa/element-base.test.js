/* Copyright 2019 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import {assert} from 'chai';
import {maybeScheduleAutoReload} from './element-base.js';
import {timeout} from './utils.js';
import {ENSURE} from './simple-redux.js';

suite('element-base', function() {
  test('maybeScheduleAutoReload', async function() {
    STORE.dispatch(ENSURE('test'));
    let callbacks = 0;
    function incr() {
      ++callbacks;
    }
    maybeScheduleAutoReload('test', state => false, incr, 1);
    await timeout(10);
    assert.strictEqual(0, callbacks);

    maybeScheduleAutoReload('test', state => true, incr, 1);
    await timeout(10);
    assert.strictEqual(1, callbacks);

    maybeScheduleAutoReload('test', state => true, incr, 2);
    // Calling again quickly should prevent the first callback from being called
    // via clearTimeout.
    maybeScheduleAutoReload('test', state => true, incr, 1);
    await timeout(10);
    assert.strictEqual(2, callbacks);
  });
});
