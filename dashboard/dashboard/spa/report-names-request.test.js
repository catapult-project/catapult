/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import {ReportNamesRequest} from './report-names-request.js';
import {assert} from 'chai';

suite('ReportNamesRequest', function() {
  let originalFetch;
  setup(() => {
    originalFetch = window.fetch;
  });
  teardown(() => {
    window.fetch = originalFetch;
  });

  test('modified Date', async function() {
    const expected = [
      {
        id: 42,
        modified: new Date(0),
      },
    ];

    window.fetch = async(url, options) => {
      return {
        ok: true,
        async json() {
          return expected.map(info => {
            return {...info, modified: info.modified.toISOString()};
          });
        }
      };
    };

    const request = new ReportNamesRequest({});
    assert.deepEqual(expected, await request.response);
  });
});
