/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import {assert} from 'chai';
import ColumnHead from './column-head.js';
import {afterRender} from './utils.js';

suite('column-head', function() {
  test('icon', async function() {
    const columnHead = document.createElement('column-head');
    columnHead.innerText = 'AAA';
    document.body.appendChild(columnHead);
    columnHead.name = 'A';
    columnHead.sortColumn = 'B';
    columnHead.sortDescending = false;
    await afterRender();
    assert.isTrue(columnHead.icon.hasAttribute('empty'));

    columnHead.sortColumn = 'A';
    await afterRender();
    assert.isFalse(columnHead.icon.hasAttribute('empty'));
    assert.strictEqual('up', columnHead.icon.icon);

    columnHead.sortDescending = true;
    await afterRender();
    assert.strictEqual('down', columnHead.icon.icon);
    document.body.removeChild(columnHead);
  });
});
