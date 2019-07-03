/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import {ExistingBugRequest} from './existing-bug-request.js';
import {MIN_PCT_DELTA, autotriage} from './autotriage.js';
import {assert} from 'chai';

suite('autotriage', function() {
  test('ignore', function() {
    const {bugId, explanation} = autotriage([
      {percentDeltaValue: MIN_PCT_DELTA * 0.99},
    ], []);
    assert.strictEqual(ExistingBugRequest.IGNORE_BUG_ID, bugId);
    assert.isTrue(!!explanation);
  });

  test('existing', function() {
    const {bugId, explanation} = autotriage([
      {percentDeltaValue: MIN_PCT_DELTA * 1.1},
    ], [
      {bugId: 42},
      {bugId: 42},
      {bugId: 57},
    ]);
    assert.strictEqual(42, bugId);
    assert.isTrue(!!explanation);
  });

  test('existing not ignored', function() {
    const {bugId, explanation} = autotriage([
      {percentDeltaValue: MIN_PCT_DELTA * 1.1},
    ], [
      {bugId: 42},
      {bugId: ExistingBugRequest.IGNORE_BUG_ID},
      {bugId: ExistingBugRequest.IGNORE_BUG_ID},
    ]);
    assert.strictEqual(42, bugId);
    assert.isTrue(!!explanation);
  });

  test('new', function() {
    const {bugId, explanation} = autotriage([
      {percentDeltaValue: MIN_PCT_DELTA * 1.1},
    ], [
    ]);
    assert.strictEqual(0, bugId);
    assert.isTrue(!!explanation);
  });
});
