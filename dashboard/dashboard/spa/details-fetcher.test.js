/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import {assert} from 'chai';
import {RangeFinder} from './details-fetcher.js';

suite('details-fetcher', function() {
  test('matchRange', async function() {
    const {minRevision, maxRevision} = RangeFinder.matchRange(
        tr.b.math.Range.fromExplicitRange(3, 5), [
          {revision: 1},
          {revision: 2},
          {revision: 4},
          {revision: 6},
        ]);
    assert.strictEqual(minRevision, 2);
    assert.strictEqual(maxRevision, 4);
  });
});
