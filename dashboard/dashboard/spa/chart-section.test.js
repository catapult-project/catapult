/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import ChartSection from './chart-section.js';
import DescribeRequest from './describe-request.js';
import TestSuitesRequest from './test-suites-request.js';
import TimeseriesDescriptor from './timeseries-descriptor.js';
import findElements from './find-elements.js';
import {CHAIN, ENSURE, UPDATE} from './simple-redux.js';
import {MODE} from './layout-timeseries.js';
import {STORE} from './element-base.js';
import {TimeseriesRequest} from './timeseries-request.js';
import {afterRender} from './utils.js';
import {assert} from 'chai';

suite('chart-section', function() {
  async function fixture() {
    const chart = document.createElement('chart-section');
    chart.statePath = 'test';
    chart.linkedStatePath = 'linked';
    await STORE.dispatch(CHAIN(
        ENSURE('test'),
        UPDATE('test', ChartSection.buildState({}))));
    document.body.appendChild(chart);
    await afterRender();
    return chart;
  }

  let originalFetch;
  let originalAuthorizationHeaders;
  let timeseriesBody;
  setup(() => {
    originalAuthorizationHeaders = window.getAuthorizationHeaders;
    window.getAuthorizationHeaders = async() => {
      return {};
    };

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
              measurements: ['measure'],
              bots: ['master:bot'],
            };
          }
          if (url === TimeseriesRequest.URL) {
            timeseriesBody = new Map(options.body);
            return {
              units: options.body.get('measurement'),
              data: [
                [10, 1000, 1, 1],
                [20, 2000, 2, 1],
              ],
            };
          }
        },
      };
    };
  });
  teardown(() => {
    for (const child of document.body.children) {
      if (!child.matches('chart-section')) continue;
      document.body.removeChild(child);
    }
    window.fetch = originalFetch;
    window.getAuthorizationHeaders = originalAuthorizationHeaders;
  });

  test('descriptor', async function() {
    const chart = await fixture();
    await STORE.dispatch(UPDATE(chart.statePath, {
      descriptor: TimeseriesDescriptor.buildState({
        suite: {
          selectedOptions: ['suite'],
        },
        bot: {
          selectedOptions: ['master:bot'],
        },
        case: {
          selectedOptions: [],
        },
        measurement: {
          selectedOptions: ['ms'],
        },
      }),
    }));
    await afterRender();
    chart.$.descriptor.dispatchEvent(new CustomEvent('matrix-change'));
    await afterRender();
    assert.deepEqual(chart.lineDescriptors, [{
      bots: ['master:bot'],
      buildType: 'test',
      cases: [],
      measurement: 'ms',
      statistic: 'avg',
      suites: ['suite'],
    }]);
  });

  test('statistic', async function() {
    const chart = await fixture();
    await STORE.dispatch(UPDATE('test', {
      descriptor: TimeseriesDescriptor.buildState({
        suite: {
          selectedOptions: ['suite'],
        },
        bot: {
          selectedOptions: ['master:bot'],
        },
        case: {
          selectedOptions: [],
        },
        measurement: {
          selectedOptions: ['ms'],
        },
      }),
    }));
    chart.$.statistic.dispatchEvent(new CustomEvent('option-select'));
    await afterRender();
    assert.deepEqual(chart.lineDescriptors, [{
      bots: ['master:bot'],
      buildType: 'test',
      cases: [],
      measurement: 'ms',
      statistic: 'avg',
      suites: ['suite'],
    }]);
  });

  test('title', async function() {
    const chart = await fixture();
    chart.$.title.value = 'test';
    chart.$.title.dispatchEvent(new CustomEvent('keyup'));
    await afterRender();
    assert.strictEqual('test', chart.title_);
    assert.isTrue(chart.isTitleCustom);
  });

  test('getRouteParams', async function() {
    const state = {
      descriptor: {
        suite: {
          selectedOptions: ['suite'],
          isAggregated: false,
        },
        measurement: {
          selectedOptions: ['measurement'],
        },
        bot: {
          selectedOptions: ['master:bot'],
          options: [],
          isAggregated: false,
        },
        case: {
          selectedOptions: ['case'],
          isAggregated: false,
          tags: {
            selectedOptions: ['tag'],
          },
        },
      },
      statistic: {
        selectedOptions: ['std'],
      },
      minRevision: 5,
      maxRevision: 50,
      selectedLineDescriptorHash: 'abcdefzzzz',
      selectedRelatedTabName: 'Related',
      isExpanded: false,
      fixedXAxis: false,
      zeroYAxis: true,
      chartLayout: {
        brushRevisions: [10, 20],
      },
      mode: MODE.NORMALIZE_LINE,
    };
    const params = ChartSection.getRouteParams(state);
    assert.strictEqual('std', params.get('stat'));
    assert.strictEqual('tag', params.get('caseTag'));
    assert.strictEqual('case', params.get('case'));
    assert.isTrue(params.has('splitCases'));
    assert.strictEqual('suite', params.get('suite'));
    assert.isTrue(params.has('splitSuites'));
    assert.strictEqual('measurement', params.get('measurement'));
    assert.strictEqual('master:bot', params.get('bot'));
    assert.isTrue(params.has('natural'));
    assert.isTrue(params.has('zeroY'));
    assert.strictEqual('Related', params.get('spark'));
    assert.isTrue(params.has('compact'));
    assert.strictEqual('10-20', params.get('brush'));
    assert.strictEqual(MODE.NORMALIZE_LINE, params.get('mode'));
    assert.strictEqual('abcdef', params.get('select'));
    assert.strictEqual('5', params.get('minRev'));
    assert.strictEqual('50', params.get('maxRev'));
  });
});
