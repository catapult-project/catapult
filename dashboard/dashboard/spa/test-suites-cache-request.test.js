/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import {TestSuitesCacheRequest} from './test-suites-cache-request.js';
import {assert} from 'chai';

class MockFetchEvent {
  constructor(internal) {
    const headers = new Map();
    if (internal) headers.set('Authorization');
    this.request = {
      url: 'http://example.com/path',
      headers,
    };
  }

  waitUntil() {
  }
}

suite('TestSuitesCacheRequest', function() {
  test('external', async() => {
    const cacheRequest = new TestSuitesCacheRequest(new MockFetchEvent());
    assert.strictEqual('test_suites', await cacheRequest.databaseKeyPromise);
  });

  test('internal', async() => {
    const cacheRequest = new TestSuitesCacheRequest(new MockFetchEvent(true));
    const actual = await cacheRequest.databaseKeyPromise;
    assert.strictEqual('test_suites_internal', actual);
  });
});
