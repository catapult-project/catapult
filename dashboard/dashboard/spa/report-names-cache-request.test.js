/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import {ReportNamesCacheRequest} from './report-names-cache-request.js';
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

suite('ReportNamesCacheRequest', function() {
  test('external', async() => {
    const cacheRequest = new ReportNamesCacheRequest(new MockFetchEvent());
    assert.strictEqual('report_names', await cacheRequest.databaseKeyPromise);
  });

  test('internal', async() => {
    const cacheRequest = new ReportNamesCacheRequest(new MockFetchEvent(true));
    const actual = await cacheRequest.databaseKeyPromise;
    assert.strictEqual('report_names_internal', actual);
  });
});
