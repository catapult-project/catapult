/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import ChartTimeseries from './chart-timeseries.js';
import ResultChannelSender from './result-channel-sender.js';
import {CHAIN, ENSURE, UPDATE} from './simple-redux.js';
import {LEVEL_OF_DETAIL, TimeseriesRequest} from './timeseries-request.js';
import {STORE} from './element-base.js';
import {afterRender, measureElement} from './utils.js';
import {assert} from 'chai';

suite('chart-timeseries', function() {
  async function fixture() {
    const ct = document.createElement('chart-timeseries');
    ct.statePath = 'test';
    await STORE.dispatch(CHAIN(
        ENSURE('test'),
        UPDATE('test', ChartTimeseries.buildState({
          yAxis: {
            showTickLines: true,
          },
          xAxis: {
            height: 15,
            showTickLines: true,
          },
        }))));
    document.body.appendChild(ct);
    await afterRender();
    return ct;
  }

  let originalFetch;
  let timeseriesBody;
  setup(() => {
    originalFetch = window.fetch;
    window.fetch = async(url, options) => {
      return {
        ok: true,
        async json() {
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
      if (!child.matches('chart-timeseries')) continue;
      document.body.removeChild(child);
    }
    window.fetch = originalFetch;
  });

  test('load', async function() {
    const ct = await fixture();
    await STORE.dispatch(UPDATE('test', {lineDescriptors: [{
      suites: ['suite'],
      bots: ['master:bot'],
      measurement: 'ms',
      statistic: 'avg',
      buildType: 'test',
      cases: [],
    }]}));
    await afterRender();
    assert.strictEqual('suite', timeseriesBody.get('test_suite'));
    assert.strictEqual('ms', timeseriesBody.get('measurement'));
    assert.strictEqual('master:bot', timeseriesBody.get('bot'));
    assert.strictEqual('avg', timeseriesBody.get('statistic'));
    assert.strictEqual('test', timeseriesBody.get('build_type'));
    assert.strictEqual('revision,timestamp,avg,count',
        timeseriesBody.get('columns'));
    assert.isUndefined(timeseriesBody.get('min_revision'));
    assert.isUndefined(timeseriesBody.get('max_revision'));
    assert.strictEqual(ct.lines[0].path, 'M1.2,96.5 L98.8,3.6');
  });

  test('lineCountChange', async function() {
    const ct = await fixture();
    let lineCountChanges = 0;
    ct.addEventListener('line-count-change', () => {
      ++lineCountChanges;
    });

    STORE.dispatch(UPDATE('test', {lineDescriptors: [{
      suites: ['suite'],
      bots: ['master:bot'],
      measurement: 'ms',
      statistic: 'avg',
      buildType: 'test',
      cases: [],
    }]}));
    await afterRender();
    assert.strictEqual(lineCountChanges, 1);
  });

  test('loadPersistent', async function() {
    // Load 2 lines (ms, sizeInBytes), each requiring 2 fetches (aaa, bbb).
    // Receive fetches in this order:
    // ms aaa, sizeInBytes aaa, ms bbb, sizeInBytes bbb.
    // Test that loadLines doesn't forget any data.

    const ct = await fixture();

    window.IS_DEBUG = false;
    window.fetch = async(url, options) => {
      return {
        ok: true,
        async json() {
          return null;
        },
      };
    };

    STORE.dispatch(UPDATE('test', {
      lineDescriptors: [
        {
          suites: ['suite'],
          bots: ['master:bot'],
          measurement: 'ms',
          statistic: 'avg',
          buildType: 'test',
          cases: ['aaa', 'bbb'],
        },
        {
          suites: ['suite'],
          bots: ['master:bot'],
          measurement: 'sizeInBytes',
          statistic: 'avg',
          buildType: 'test',
          cases: ['aaa', 'bbb'],
        },
      ],
    }));
    await afterRender();
    await afterRender();

    assert.isTrue(ct.isLoading);
    assert.lengthOf(ct.lines, 0);

    const url = location.origin + TimeseriesRequest.URL + '?';
    const aMsParams = new URLSearchParams({
      test_suite: 'suite',
      measurement: 'ms',
      bot: 'master:bot',
      test_case: 'aaa',
      statistic: 'avg',
      build_type: 'test',
      columns: 'revision,timestamp,avg,count',
    });
    let sender = new ResultChannelSender(url + aMsParams);
    await sender.send((async function* () {
      yield {
        units: 'ms',
        data: [
          {revision: 10, timestamp: 1000, avg: 1, count: 1},
          {revision: 20, timestamp: 2000, avg: 2, count: 1},
        ],
      };
    })());
    await afterRender();
    await afterRender();
    assert.lengthOf(ct.lines, 1);
    assert.strictEqual(ct.lines[0].data[0].y, 1);
    assert.strictEqual(ct.lines[0].data[1].y, 2);
    assert.isTrue(ct.isLoading);

    const aBytesParams = new URLSearchParams({
      test_suite: 'suite',
      measurement: 'sizeInBytes',
      bot: 'master:bot',
      test_case: 'aaa',
      statistic: 'avg',
      build_type: 'test',
      columns: 'revision,timestamp,avg,count',
    });
    sender = new ResultChannelSender(url + aBytesParams);
    await sender.send((async function* () {
      yield {
        units: 'sizeInBytes',
        data: [
          {revision: 10, timestamp: 1000, avg: 1, count: 1},
          {revision: 20, timestamp: 2000, avg: 2, count: 1},
        ],
      };
    })());
    await afterRender();
    await afterRender();
    assert.lengthOf(ct.lines, 2);
    assert.strictEqual(ct.lines[0].data[0].y, 1);
    assert.strictEqual(ct.lines[0].data[1].y, 2);
    assert.strictEqual(ct.lines[1].data[0].y, 1);
    assert.strictEqual(ct.lines[1].data[1].y, 2);
    assert.isTrue(ct.isLoading);

    const bMsParams = new URLSearchParams({
      test_suite: 'suite',
      measurement: 'ms',
      bot: 'master:bot',
      test_case: 'bbb',
      statistic: 'avg',
      build_type: 'test',
      columns: 'revision,timestamp,avg,count',
    });
    sender = new ResultChannelSender(url + bMsParams);
    await sender.send((async function* () {
      yield {
        units: 'ms',
        data: [
          {revision: 10, timestamp: 1000, avg: 10, count: 1},
          {revision: 20, timestamp: 2000, avg: 20, count: 1},
        ],
      };
    })());
    await afterRender();
    await afterRender();
    assert.lengthOf(ct.lines, 2);
    assert.strictEqual(ct.lines[0].data[0].y, 5.5);
    assert.strictEqual(ct.lines[0].data[1].y, 11);
    assert.strictEqual(ct.lines[1].data[0].y, 1);
    assert.strictEqual(ct.lines[1].data[1].y, 2);
    assert.isTrue(ct.isLoading);

    const bBytesParams = new URLSearchParams({
      test_suite: 'suite',
      measurement: 'sizeInBytes',
      bot: 'master:bot',
      test_case: 'bbb',
      statistic: 'avg',
      build_type: 'test',
      columns: 'revision,timestamp,avg,count',
    });
    sender = new ResultChannelSender(url + bBytesParams);
    await sender.send((async function* () {
      yield {
        units: 'sizeInBytes',
        data: [
          {revision: 10, timestamp: 1000, avg: 10, count: 1},
          {revision: 20, timestamp: 2000, avg: 20, count: 1},
        ],
      };
    })());
    await afterRender();
    assert.lengthOf(ct.lines, 2);
    assert.strictEqual(ct.lines[0].data[0].y, 5.5);
    assert.strictEqual(ct.lines[0].data[1].y, 11);
    assert.strictEqual(ct.lines[1].data[0].y, 5.5);
    assert.strictEqual(ct.lines[1].data[1].y, 11);

    assert.isFalse(ct.isLoading);
  });

  test('tooltip', async function() {
    const ct = await fixture();
    ct.style.position = 'absolute';
    ct.style.top = 0;
    await STORE.dispatch(UPDATE('test', {lineDescriptors: [{
      suites: ['suite'],
      bots: ['master:bot'],
      measurement: 'ms',
      statistic: 'avg',
      buildType: 'test',
      cases: [],
    }]}));
    await afterRender();
    const cb = ct.shadowRoot.querySelector('chart-base');
    cb.dispatchEvent(new CustomEvent('get-tooltip', {
      detail: {
        mainRect: await measureElement(cb),
        nearestLine: ct.lines[0],
        nearestPoint: ct.lines[0].data[0],
      },
    }));
    await afterRender();
    await afterRender();

    assert.strictEqual(2, ct.lines[0].strokeWidth);
    assert.isTrue(ct.tooltip.isVisible);
    assert.strictEqual(ct.lines[0].color, ct.tooltip.color);
    assert.strictEqual('1.2%', ct.tooltip.left);
    assert.strictEqual('100%', ct.tooltip.top);
    assert.lengthOf(ct.tooltip.rows, 8);
    assert.strictEqual('Click for details', ct.tooltip.rows[0].name);
    assert.strictEqual(2, ct.tooltip.rows[0].colspan);
    assert.strictEqual('value', ct.tooltip.rows[1].name);
    assert.strictEqual('1.000 ms', ct.tooltip.rows[1].value);
    assert.strictEqual('revision', ct.tooltip.rows[2].name);
    assert.strictEqual(10, ct.tooltip.rows[2].value);
    assert.strictEqual('Upload timestamp', ct.tooltip.rows[3].name);
    assert.strictEqual('build type', ct.tooltip.rows[4].name);
    assert.strictEqual('test', ct.tooltip.rows[4].value);
    assert.strictEqual('test suite', ct.tooltip.rows[5].name);
    assert.strictEqual('suite', ct.tooltip.rows[5].value);
    assert.strictEqual('measurement', ct.tooltip.rows[6].name);
    assert.strictEqual('ms', ct.tooltip.rows[6].value);
    assert.strictEqual('bot', ct.tooltip.rows[7].name);
    assert.strictEqual('master:bot', ct.tooltip.rows[7].value);

    cb.dispatchEvent(new CustomEvent('mouse-leave-main'));
    await afterRender();
    assert.strictEqual(1, ct.lines[0].strokeWidth);
    assert.isUndefined(ct.tooltip);
  });

  test('mouseYTicks', async function() {
    // When there are multiple units, yAxis.ticks should only be displayed when
    // the user is hovering over a line.

    const ct = await fixture();
    await STORE.dispatch(UPDATE('test', {
      lineDescriptors: [
        {
          suites: ['suite'],
          bots: ['master:bot'],
          measurement: 'sizeInBytes',
          statistic: 'avg',
          buildType: 'test',
          cases: [],
        },
        {
          suites: ['suite'],
          bots: ['master:bot'],
          measurement: 'ms',
          statistic: 'avg',
          buildType: 'test',
          cases: [],
        },
      ]
    }));
    await afterRender();

    assert.lengthOf(ct.yAxis.ticks, 0);

    const cb = ct.shadowRoot.querySelector('chart-base');
    cb.dispatchEvent(new CustomEvent('get-tooltip', {
      detail: {
        mainRect: await measureElement(cb),
        nearestLine: ct.lines[0],
        nearestPoint: ct.lines[0].data[0],
      },
    }));

    await afterRender();
    assert.lengthOf(ct.yAxis.ticks, 5);

    cb.dispatchEvent(new CustomEvent('mouse-leave-main'));
    await afterRender();
    assert.lengthOf(ct.yAxis.ticks, 0);
  });

  test('lineDescriptorEqual', async function() {
    assert.isFalse(ChartTimeseries.lineDescriptorEqual({
      suites: ['bbb'],
      bots: ['ccc', 'ddd'],
      cases: ['eee', 'fff'],
      measurement: 'mmm',
      statistic: 'avg',
      buildType: 'test',
      minRevision: 10,
      maxRevision: 100,
    }, {
      suites: ['bbb', 'aaa'],
      bots: ['ddd', 'ccc'],
      cases: ['fff', 'eee'],
      measurement: 'mmm',
      statistic: 'avg',
      buildType: 'test',
      minRevision: 10,
      maxRevision: 100,
    }));

    assert.isFalse(ChartTimeseries.lineDescriptorEqual({
      suites: ['bbb'],
      bots: ['ddd'],
      cases: ['eee', 'fff'],
      measurement: 'mmm',
      statistic: 'avg',
      buildType: 'test',
      minRevision: 10,
      maxRevision: 100,
    }, {
      suites: ['bbb'],
      bots: ['ddd', 'ccc'],
      cases: ['fff', 'eee'],
      measurement: 'mmm',
      statistic: 'avg',
      buildType: 'test',
      minRevision: 0,
      maxRevision: 100,
    }));

    assert.isFalse(ChartTimeseries.lineDescriptorEqual({
      suites: ['bbb'],
      bots: ['ddd'],
      cases: ['fff'],
      measurement: 'mmm',
      statistic: 'avg',
      buildType: 'test',
      minRevision: 10,
      maxRevision: 100,
    }, {
      suites: ['bbb'],
      bots: ['ddd'],
      cases: ['fff', 'eee'],
      measurement: 'mmm',
      statistic: 'avg',
      buildType: 'test',
      minRevision: 0,
      maxRevision: 100,
    }));

    assert.isFalse(ChartTimeseries.lineDescriptorEqual({
      suites: ['bbb'],
      bots: ['ccc', 'ddd'],
      cases: ['eee', 'fff'],
      measurement: 'mmm',
      statistic: 'avg',
      buildType: 'test',
      minRevision: 10,
      maxRevision: 100,
    }, {
      suites: ['bbb'],
      bots: ['ddd', 'ccc'],
      cases: ['fff', 'eee'],
      measurement: 'mm',
      statistic: 'avg',
      buildType: 'test',
      minRevision: 10,
      maxRevision: 100,
    }));

    assert.isFalse(ChartTimeseries.lineDescriptorEqual({
      suites: ['bbb'],
      bots: ['ccc', 'ddd'],
      cases: ['eee', 'fff'],
      measurement: 'mmm',
      statistic: 'avg',
      buildType: 'test',
      minRevision: 10,
      maxRevision: 100,
    }, {
      suites: ['bbb'],
      bots: ['ddd', 'ccc'],
      cases: ['fff', 'eee'],
      measurement: 'mmm',
      statistic: 'std',
      buildType: 'test',
      minRevision: 10,
      maxRevision: 100,
    }));

    assert.isFalse(ChartTimeseries.lineDescriptorEqual({
      suites: ['bbb'],
      bots: ['ccc', 'ddd'],
      cases: ['eee', 'fff'],
      measurement: 'mmm',
      statistic: 'avg',
      buildType: 'test',
      minRevision: 10,
      maxRevision: 100,
    }, {
      suites: ['bbb'],
      bots: ['ddd', 'ccc'],
      cases: ['fff', 'eee'],
      measurement: 'mmm',
      statistic: 'avg',
      buildType: 'ref',
      minRevision: 10,
      maxRevision: 100,
    }));

    assert.isFalse(ChartTimeseries.lineDescriptorEqual({
      suites: ['bbb'],
      bots: ['ccc', 'ddd'],
      cases: ['eee', 'fff'],
      measurement: 'mmm',
      statistic: 'avg',
      buildType: 'test',
      minRevision: 10,
      maxRevision: 100,
    }, {
      suites: ['bbb'],
      bots: ['ddd', 'ccc'],
      cases: ['fff', 'eee'],
      measurement: 'mmm',
      statistic: 'avg',
      buildType: 'test',
      minRevision: 0,
      maxRevision: 100,
    }));

    assert.isTrue(ChartTimeseries.lineDescriptorEqual({
      suites: ['aaa', 'bbb'],
      bots: ['ccc', 'ddd'],
      cases: ['eee', 'fff'],
      measurement: 'mmm',
      statistic: 'avg',
      buildType: 'test',
      minRevision: 10,
      maxRevision: 100,
    }, {
      suites: ['bbb', 'aaa'],
      bots: ['ddd', 'ccc'],
      cases: ['fff', 'eee'],
      measurement: 'mmm',
      statistic: 'avg',
      buildType: 'test',
      minRevision: 10,
      maxRevision: 100,
    }));
  });

  test('createFetchDescriptors', async function() {
    assert.deepEqual(ChartTimeseries.createFetchDescriptors({
      suites: ['aaa', 'bbb'],
      bots: ['ccc', 'ddd'],
      measurement: 'mmm',
      cases: [],
      buildType: 'test',
      statistic: 'avg',
    }, LEVEL_OF_DETAIL.ALERTS), [
      {
        suite: 'aaa',
        bot: 'ccc',
        case: undefined,
        measurement: 'mmm',
        statistic: 'avg',
        buildType: 'test',
        levelOfDetail: LEVEL_OF_DETAIL.ALERTS,
      },
      {
        suite: 'aaa',
        bot: 'ddd',
        case: undefined,
        measurement: 'mmm',
        statistic: 'avg',
        buildType: 'test',
        levelOfDetail: LEVEL_OF_DETAIL.ALERTS,
      },
      {
        suite: 'bbb',
        bot: 'ccc',
        case: undefined,
        measurement: 'mmm',
        statistic: 'avg',
        buildType: 'test',
        levelOfDetail: LEVEL_OF_DETAIL.ALERTS,
      },
      {
        suite: 'bbb',
        bot: 'ddd',
        case: undefined,
        measurement: 'mmm',
        statistic: 'avg',
        buildType: 'test',
        levelOfDetail: LEVEL_OF_DETAIL.ALERTS,
      },
    ]);

    assert.deepEqual(ChartTimeseries.createFetchDescriptors({
      suites: ['aaa'],
      bots: ['ccc'],
      measurement: 'mmm',
      cases: ['bbb', 'ddd'],
      buildType: 'test',
      statistic: 'avg',
    }, LEVEL_OF_DETAIL.ALERTS), [
      {
        suite: 'aaa',
        bot: 'ccc',
        measurement: 'mmm',
        case: 'bbb',
        statistic: 'avg',
        buildType: 'test',
        levelOfDetail: LEVEL_OF_DETAIL.ALERTS,
      },
      {
        suite: 'aaa',
        bot: 'ccc',
        case: 'ddd',
        measurement: 'mmm',
        statistic: 'avg',
        buildType: 'test',
        levelOfDetail: LEVEL_OF_DETAIL.ALERTS,
      },
    ]);
  });
});
