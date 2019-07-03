/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import {assert} from 'chai';
import {DescribeCacheRequest} from './describe-cache-request.js';

class MockFetchEvent {
  constructor(internal) {
    const headers = new Map();
    if (internal) headers.set('Authorization');
    this.request = {
      url: 'http://example.com/path',
      headers,
      clone: () => this.request,
      formData: () => new Map([['test_suite', 'suite']]),
    };
  }

  waitUntil() {
  }
}

suite('DescribeCacheRequest', function() {
  test('external', async() => {
    const cacheRequest = new DescribeCacheRequest(new MockFetchEvent());
    assert.strictEqual('describe_suite', await cacheRequest.databaseKeyPromise);
  });

  test('internal', async() => {
    const cacheRequest = new DescribeCacheRequest(new MockFetchEvent(true));
    const actual = await cacheRequest.databaseKeyPromise;
    assert.strictEqual('describe_suite_internal', actual);
  });
});
