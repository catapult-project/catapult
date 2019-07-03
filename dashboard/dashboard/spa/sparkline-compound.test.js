/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import {CHAIN, ENSURE, UPDATE} from './simple-redux.js';
import {DescribeRequest} from './describe-request.js';
import {MODE} from './layout-timeseries.js';
import {STORE} from './element-base.js';
import {SparklineCompound} from './sparkline-compound.js';
import {TimeseriesDescriptor} from './timeseries-descriptor.js';
import {TimeseriesRequest} from './timeseries-request.js';
import {afterRender, denormalize, setDebugForTesting} from './utils.js';
import {assert} from 'chai';

suite('sparkline-compound', function() {
  let MS_PER_YEAR;  // tr might not be loaded yet.
  const NOW_MS = new Date().getTime();
  let originalFetch;
  setup(() => {
    MS_PER_YEAR = tr.b.convertUnit(
        1, tr.b.UnitScale.TIME.YEAR, tr.b.UnitScale.TIME.MILLI_SEC);
    setDebugForTesting(true);
    originalFetch = window.fetch;
    window.fetch = async(url, options) => {
      return {
        ok: true,
        async json() {
          if (url === DescribeRequest.URL) {
            return {
              measurements: ['measure'],
              bots: ['master:aaa', 'master:bbb', 'master:ccc'],
              cases: ['ddd', 'eee', 'fff', 'ggg', 'hhh'],
              caseTags: {
                tagA: ['ddd', 'fff'],
                tagB: ['ddd', 'ggg'],
              },
            };
          }
          if (url === TimeseriesRequest.URL) {
            const data = [];
            const sequenceLength = 100;
            for (let i = 0; i < sequenceLength; ++i) {
              const pct = (sequenceLength - i - 1) / sequenceLength;
              const timestamp = NOW_MS - pct * MS_PER_YEAR;
              data.push({
                revision: timestamp,
                timestamp,
                avg: 1 + (i % 3),
                count: 1,
                std: (i % 4) / 2,
              });
            }
            return {
              units: options.body.get('measurement'),
              data: denormalize(
                  data, options.body.get('columns').split(',')),
            };
          }
        },
      };
    };
  });
  teardown(() => {
    for (const child of document.body.children) {
      if (!child.matches('sparkline-compound')) continue;
      document.body.removeChild(child);
    }
    window.fetch = originalFetch;
  });

  async function fixture() {
    const sc = document.createElement('sparkline-compound');
    sc.statePath = 'test';
    await STORE.dispatch(CHAIN(
        ENSURE('test'),
        UPDATE('test', {
          ...SparklineCompound.buildState({}),
          chartLayout: {},
        })));
    document.body.appendChild(sc);
    await afterRender();
    return sc;
  }

  test('build', async function() {
    const sc = await fixture();
    await STORE.dispatch(CHAIN(
        UPDATE('test', {
          descriptor: TimeseriesDescriptor.buildState({
            suite: {selectedOptions: ['suite:xxx', 'suite:yyy', 'suite:zzz']},
            measurement: {selectedOptions: ['ms']},
            bot: {selectedOptions: [
              'master:aaa', 'master:bbb', 'master:ccc',
            ]},
            case: {
              selectedOptions: [],
              options: ['ddd', 'eee', 'fff', 'ggg', 'hhh'],
            },
          }),
          statistic: {selectedOptions: ['avg']},
        }),
        {
          type: SparklineCompound.reducers.buildRelatedTabs.name,
          statePath: 'test',
        }));
    await afterRender();

    assert.lengthOf(sc.relatedTabs, 3);
    assert.lengthOf(sc.relatedTabs[0].sparklines, 3);
    assert.lengthOf(sc.relatedTabs[1].sparklines, 3);
    assert.lengthOf(sc.relatedTabs[2].sparklines, 5);

    await SparklineCompound.selectRelatedTab(sc.statePath, 'Suites');
    await afterRender();

    assert.lengthOf(sc.relatedTabs[0].renderedSparklines, 3);
    assert.lengthOf(sc.relatedTabs[0].renderedSparklines[0].layout.lines, 2);
    assert.lengthOf(sc.relatedTabs[0].renderedSparklines[1].layout.lines, 2);
    assert.lengthOf(sc.relatedTabs[0].renderedSparklines[2].layout.lines, 2);
  });

  test('observeCursor', async function() {
    const sc = await fixture();
    await STORE.dispatch(CHAIN(
        UPDATE('test', {
          mode: MODE.NORMALIZE_UNIT,
          descriptor: TimeseriesDescriptor.buildState({
            suite: {selectedOptions: ['suite:xxx', 'suite:yyy', 'suite:zzz']},
            measurement: {selectedOptions: ['ms']},
            bot: {selectedOptions: [
              'master:aaa', 'master:bbb', 'master:ccc',
            ]},
            case: {
              selectedOptions: [],
              options: ['ddd', 'eee', 'fff', 'ggg', 'hhh'],
            },
          }),
          statistic: {selectedOptions: ['avg']},
        }),
        {
          type: SparklineCompound.reducers.buildRelatedTabs.name,
          statePath: 'test',
        }));
    await afterRender();
    await SparklineCompound.selectRelatedTab(sc.statePath, 'Suites');
    await afterRender();
    await STORE.dispatch(UPDATE(sc.statePath, {
      cursorRevision: NOW_MS - (MS_PER_YEAR / 20),
      cursorScalar: new tr.b.Scalar(tr.b.Unit.byJSONName.ms, 1.5),
    }));
    await afterRender();

    const sparks = sc.relatedTabs[0].renderedSparklines;
    assert.strictEqual('94.9%', sparks[0].layout.xAxis.cursor.pct);
    assert.strictEqual('75%', sparks[0].layout.yAxis.cursor.pct);
    assert.strictEqual('94.9%', sparks[1].layout.xAxis.cursor.pct);
    assert.strictEqual('75%', sparks[1].layout.yAxis.cursor.pct);
    assert.strictEqual('94.9%', sparks[2].layout.xAxis.cursor.pct);
    assert.strictEqual('75%', sparks[2].layout.yAxis.cursor.pct);
  });

  test('observeRevisions', async function() {
    const sc = await fixture();
    await STORE.dispatch(CHAIN(
        UPDATE('test', {
          descriptor: TimeseriesDescriptor.buildState({
            suite: {selectedOptions: ['suite:xxx', 'suite:yyy', 'suite:zzz']},
            measurement: {selectedOptions: ['ms']},
            bot: {selectedOptions: [
              'master:aaa', 'master:bbb', 'master:ccc',
            ]},
            case: {
              selectedOptions: [],
              options: ['ddd', 'eee', 'fff', 'ggg', 'hhh'],
            },
          }),
          statistic: {selectedOptions: ['avg']},
        }),
        {
          type: SparklineCompound.reducers.buildRelatedTabs.name,
          statePath: 'test',
        }));
    await afterRender();
    await SparklineCompound.selectRelatedTab(sc.statePath, 'Suites');
    await afterRender();

    let sparks = sc.relatedTabs[0].renderedSparklines;
    assert.isUndefined(sparks[0].layout.minRevision);
    assert.isUndefined(sparks[0].layout.maxRevision);
    assert.isUndefined(sparks[1].layout.minRevision);
    assert.isUndefined(sparks[1].layout.maxRevision);
    assert.isUndefined(sparks[2].layout.minRevision);
    assert.isUndefined(sparks[2].layout.maxRevision);

    await STORE.dispatch(UPDATE(sc.statePath, {
      minRevision: NOW_MS - (MS_PER_YEAR / 2),
      maxRevision: NOW_MS - (MS_PER_YEAR / 20),
    }));
    await afterRender();

    sparks = sc.relatedTabs[0].renderedSparklines;
    assert.strictEqual(sc.minRevision, sparks[0].layout.minRevision);
    assert.strictEqual(sc.maxRevision, sparks[0].layout.maxRevision);
    assert.strictEqual(sc.minRevision, sparks[1].layout.minRevision);
    assert.strictEqual(sc.maxRevision, sparks[1].layout.maxRevision);
    assert.strictEqual(sc.minRevision, sparks[2].layout.minRevision);
    assert.strictEqual(sc.maxRevision, sparks[2].layout.maxRevision);
  });

  test('click', async function() {
    const sc = await fixture();
    await STORE.dispatch(CHAIN(
        UPDATE('test', {
          descriptor: TimeseriesDescriptor.buildState({
            suite: {selectedOptions: ['suite:xxx', 'suite:yyy', 'suite:zzz']},
            measurement: {selectedOptions: ['ms']},
            bot: {selectedOptions: [
              'master:aaa', 'master:bbb', 'master:ccc',
            ]},
            case: {
              selectedOptions: [],
              options: ['ddd', 'eee', 'fff', 'ggg', 'hhh'],
            },
          }),
          statistic: {selectedOptions: ['avg']},
        }),
        {
          type: SparklineCompound.reducers.buildRelatedTabs.name,
          statePath: 'test',
        }));
    await afterRender();
    await SparklineCompound.selectRelatedTab(sc.statePath, 'Suites');
    await afterRender();

    let newChartEvents = 0;
    sc.addEventListener('new-chart', e => {
      ++newChartEvents;
    });
    sc.shadowRoot.querySelector('.sparkline_tile').click();

    assert.strictEqual(1, newChartEvents);
  });
});
