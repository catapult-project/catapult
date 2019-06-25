/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import {assert} from 'chai';
import RequestBase from './request-base.js';
import {ResultChannelSender} from '@chopsui/result-channel';

import {
  simpleGUID,
  setDebugForTesting,
  setProductionForTesting,
} from './utils.js';

suite('RequestBase', function() {
  let originalFetch;
  let originalAuthorizationHeaders;
  setup(() => {
    originalFetch = window.fetch;
    originalAuthorizationHeaders = RequestBase.getAuthorizationHeaders;
  });
  teardown(() => {
    window.fetch = originalFetch;
    RequestBase.getAuthorizationHeaders = originalAuthorizationHeaders;
  });

  // HTML imports may not have loaded when suite() is called, but are loaded
  // when tests are called.
  function TestRequest(options) {
    return new class TestRequest extends RequestBase {
      constructor(options = {}) {
        super(options);
        this.body_ = new FormData();
        this.body_.set('channelName', simpleGUID());
      }

      get url_() {
        return '/url';
      }

      postProcess_(response, isFromChannel = false) {
        return response.map(x => (isFromChannel ? x : (x * x)));
      }
    }(options);
  }

  test('getAuthorizationHeaders', async() => {
    RequestBase.getAuthorizationHeaders = async() => {
      return {Authorization: 'test Authorization'};
    };
    window.fetch = async(url, options) => {
      assert.strictEqual('test Authorization',
          options.headers.get('Authorization'));
      return {
        ok: true,
        async json() {
          return [1];
        }
      };
    };
    setProductionForTesting(true);

    const request = new TestRequest({});
    const response = await request.response;
    assert.deepEqual([1], response);
  });

  test('postProcess', async() => {
    window.fetch = async(url, options) => {
      return {
        ok: true,
        async json() {
          return [3, 4, 5];
        }
      };
    };

    const request = new TestRequest({});
    assert.deepEqual([9, 16, 25], await request.response);
  });

  test('memoized responsePromise', async() => {
    window.fetch = async(url, options) => {
      window.fetch = async() => {
        throw new Error('Unexpected call to fetch()');
      };
      return {
        ok: true,
        async json() {
          return [1];
        }
      };
    };

    const request = new TestRequest({});
    assert.strictEqual(request.response, request.response);
    const response = await request.response;
    assert.deepEqual([1], response);
  });

  test('reader', async function() {
    setDebugForTesting(false);
    window.fetch = async(url, options) => {
      return {
        ok: true,
        async json() {
          return [3, 4, 5];
        }
      };
    };

    const request = new TestRequest({});
    const reader = request.reader();

    const sender = new ResultChannelSender(request.channelName);
    sender.send((async function* () {
      yield [6, 7, 8];
      yield [9, 10, 11];
    })());

    const results = [];
    for await (const result of reader) {
      results.push(result);
    }
    assert.deepEqual(results, [[9, 16, 25], [6, 7, 8], [9, 10, 11]]);
  });
});
