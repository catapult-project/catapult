/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import {assert} from 'chai';
import ColumnHead from './column-head.js';

suite('column-head', function() {
  test('icon', async function() {
    const columnHead = document.createElement('column-head');
    columnHead.innerText = 'AAA';
    document.body.appendChild(columnHead);
    columnHead.name = 'A';
    columnHead.sortColumn = 'B';
    columnHead.sortDescending = false;
    assert.isTrue(columnHead.$.icon.hasAttribute('empty'));

    columnHead.sortColumn = 'A';
    assert.isFalse(columnHead.$.icon.hasAttribute('empty'));
    assert.strictEqual('cp:arrow-upward', columnHead.$.icon.icon);

    columnHead.sortDescending = true;
    assert.strictEqual('cp:arrow-downward', columnHead.$.icon.icon);
    document.body.removeChild(columnHead);
  });
});
