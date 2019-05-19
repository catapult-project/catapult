/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import NudgeAlert from './nudge-alert.js';
import NudgeAlertRequest from './nudge-alert-request.js';
import findElements from './find-elements.js';
import {STORE} from './element-base.js';
import {TimeseriesRequest} from './timeseries-request.js';
import {UPDATE} from './simple-redux.js';
import {afterRender} from './utils.js';
import {assert} from 'chai';

suite('nudge-alert', function() {
  async function fixture() {
    const na = document.createElement('nudge-alert');
    na.statePath = 'test';
    await STORE.dispatch(UPDATE('test', NudgeAlert.buildState({
      isOpen: true,
      key: 'key',
      suite: 'suite',
      measurement: 'ms',
      bot: 'master:bot',
      case: 'case',
      endRevision: 10,
      minRevision: 5,
      maxRevision: 15,
    })));
    document.body.appendChild(na);
    await afterRender();
    return na;
  }

  let nudgeBody;
  let originalFetch;
  setup(() => {
    window.IS_DEBUG = true;
    originalFetch = window.fetch;
    window.fetch = async(url, options) => {
      return {
        ok: true,
        async json() {
          if (url === TimeseriesRequest.URL) {
            return {
              units: options.body.get('measurement'),
              data: [
                [5, 1000, 1, 1],
                [10, 2000, 2, 1],
                [15, 3000, 3, 1],
              ],
            };
          }
          if (url === NudgeAlertRequest.URL) {
            nudgeBody = new Map(options.body);
            return {};
          }
        },
      };
    };
  });

  teardown(() => {
    for (const child of document.body.children) {
      if (!child.matches('nudge-alert')) continue;
      document.body.removeChild(child);
    }
    window.fetch = originalFetch;
  });

  test('nudge', async function() {
    const na = await fixture();
    const row = findElements(na, e => e.matches('tr:not([selected])'))[0];
    row.click();
    await afterRender();
    assert.strictEqual('key', nudgeBody.get('key'));
    assert.strictEqual('11', nudgeBody.get('new_start_revision'));
    assert.strictEqual('15', nudgeBody.get('new_end_revision'));
  });
});
