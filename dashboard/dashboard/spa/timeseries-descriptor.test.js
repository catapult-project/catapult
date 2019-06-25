/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import DescribeRequest from './describe-request.js';
import TestSuitesRequest from './test-suites-request.js';
import TimeseriesDescriptor from './timeseries-descriptor.js';
import findElements from './find-elements.js';
import {ENSURE, TOGGLE, UPDATE} from './simple-redux.js';
import {STORE} from './element-base.js';
import {afterRender} from './utils.js';
import {assert} from 'chai';

suite('timeseries-descriptor', function() {
  let originalFetch;
  setup(() => {
    originalFetch = window.fetch;
    window.fetch = async(url, options) => {
      return {
        ok: true,
        async json() {
          if (url === TestSuitesRequest.URL) {
            return ['suite_a', 'suite_b', 'suite_c'];
          }
          if (url === DescribeRequest.URL) {
            return {
              measurements: [
                'measurement_a', 'measurement_b', 'measurement_c',
              ],
              bots: ['bot_a', 'bot_b', 'bot_c'],
              cases: ['case_a', 'case_b', 'case_c'],
              caseTags: {
                tag_a: ['case_b', 'case_c'],
                tag_b: ['case_a', 'case_c'],
                tag_c: ['case_a', 'case_b'],
              },
            };
          }
        }
      };
    };
  });

  teardown(() => {
    for (const child of document.body.children) {
      if (!child.matches('timeseries-descriptor')) continue;
      document.body.removeChild(child);
    }
    window.fetch = originalFetch;
  });

  test('suite select describe', async function() {
    const td = document.createElement('timeseries-descriptor');
    td.statePath = 'test';
    STORE.dispatch(ENSURE('test'));
    STORE.dispatch(UPDATE('test', TimeseriesDescriptor.buildState({})));
    document.body.appendChild(td);
    await afterRender();

    findElements(td, e =>
      e.matches('chops-checkbox') && /suite_a/.test(e.textContent))[0].click();
    await afterRender();

    assert.lengthOf(td.measurement.options, 3);
    assert.lengthOf(td.bot.options, 3);
    assert.lengthOf(td.case.options, 1);
    assert.lengthOf(td.case.options[0].options, 3);
    assert.lengthOf(td.case.tags.options, 3);
  });

  test('option-select matrix-change', async function() {
    const td = document.createElement('timeseries-descriptor');
    td.statePath = 'test';
    STORE.dispatch(ENSURE('test'));
    STORE.dispatch(UPDATE('test', TimeseriesDescriptor.buildState({})));
    document.body.appendChild(td);
    await afterRender();

    let matrix;
    td.addEventListener('matrix-change', e => {
      matrix = e.detail;
    });

    findElements(td, e =>
      e.matches('chops-checkbox') && /suite_a/.test(e.textContent))[0].click();
    findElements(td, e =>
      e.matches('chops-checkbox') && /suite_b/.test(e.textContent))[0].click();
    await afterRender();
    findElements(td, e =>
      e.matches('chops-checkbox') &&
      /measurement_a/.test(e.textContent))[0].click();
    findElements(td, e =>
      e.matches('chops-checkbox') && /bot_a/.test(e.textContent))[0].click();
    findElements(td, e =>
      e.matches('chops-checkbox') && /bot_b/.test(e.textContent))[0].click();
    await afterRender();

    assert.deepEqual([['suite_a', 'suite_b']], matrix.suites);
    assert.deepEqual(['measurement_a'], matrix.measurements);
    assert.deepEqual([['bot_a', 'bot_b']], matrix.bots);
    assert.deepEqual([[]], matrix.cases);

    STORE.dispatch(TOGGLE('test.suite.isAggregated'));
    STORE.dispatch(TOGGLE('test.bot.isAggregated'));
    STORE.dispatch(TOGGLE('test.case.isAggregated'));

    findElements(td, e =>
      e.matches('chops-checkbox') && /case_a/.test(e.textContent))[0].click();
    findElements(td, e =>
      e.matches('chops-checkbox') && /case_b/.test(e.textContent))[0].click();
    await afterRender();

    assert.deepEqual([['suite_a'], ['suite_b']], matrix.suites);
    assert.deepEqual(['measurement_a'], matrix.measurements);
    assert.deepEqual([['bot_a'], ['bot_b']], matrix.bots);
    assert.deepEqual([['case_a'], ['case_b']], matrix.cases);
  });
});
