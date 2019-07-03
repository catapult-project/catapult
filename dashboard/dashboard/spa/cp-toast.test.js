/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import {assert} from 'chai';
import {CpToast} from './cp-toast.js';

suite('cp-toast', function() {
  teardown(() => {
    for (const child of document.body.children) {
      if (!child.matches('cp-toast')) continue;
      document.body.removeChild(child);
    }
  });

  test('autoclose', async function() {
    const toast = document.createElement('cp-toast');
    document.body.appendChild(toast);
    assert.isFalse(toast.opened);
    let finish;
    const promise = toast.open(new Promise(resolve => {finish = resolve;}));
    assert.isTrue(toast.opened);
    finish();
    await promise;
    assert.isFalse(toast.opened);
  });

  test('no-autoclose', async function() {
    const toast = document.createElement('cp-toast');
    document.body.appendChild(toast);
    assert.isFalse(toast.opened);
    const promise = toast.open(false);
    assert.isTrue(toast.opened);
    await promise;
    assert.isTrue(toast.opened);
  });

  test('autoclose-only-last', async function() {
    const toast = document.createElement('cp-toast');
    document.body.appendChild(toast);
    assert.isFalse(toast.opened);

    let finishFirst;
    const firstPromise = toast.open(new Promise(resolve => {
      finishFirst = resolve;
    }));
    assert.isTrue(toast.opened);

    let finishSecond;
    const secondPromise = toast.open(new Promise(resolve => {
      finishSecond = resolve;
    }));
    assert.isTrue(toast.opened);

    finishFirst();
    await firstPromise;
    assert.isTrue(toast.opened);

    finishSecond();
    await secondPromise;
    assert.isFalse(toast.opened);
  });
});
