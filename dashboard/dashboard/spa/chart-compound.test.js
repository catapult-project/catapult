/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import {assert} from 'chai';
import ChartCompound from './chart-compound.js';
import findElements from './find-elements.js';
import {CHAIN, ENSURE, UPDATE} from './simple-redux.js';
import {MODE} from './layout-timeseries.js';
import {TimeseriesRequest} from './timeseries-request.js';
import {afterRender, denormalize} from './utils.js';

suite('chart-compound', function() {
  let MS_PER_YEAR;  // tr might not be loaded yet.
  const NOW_MS = new Date().getTime();

  async function fixture() {
    const cc = document.createElement('chart-compound');
    cc.statePath = 'test';
    cc.linkedStatePath = 'linked';
    await cc.dispatch(CHAIN(
        ENSURE('test'),
        UPDATE('test', ChartCompound.buildState()),
        ENSURE('linked'),
        UPDATE('linked', ChartCompound.buildLinkedState())));
    document.body.appendChild(cc);
    await cc.dispatch(UPDATE('test', {lineDescriptors: [{
      suites: ['suite'],
      bots: ['master:bot'],
      measurement: 'ms',
      statistic: 'avg',
      cases: [],
    }]}));
    await afterRender();
    await afterRender();
    return cc;
  }

  let originalFetch;
  setup(() => {
    MS_PER_YEAR = tr.b.convertUnit(
        1, tr.b.UnitScale.TIME.YEAR, tr.b.UnitScale.TIME.MILLI_SEC);

    // Mocha sets min-width: 900px inside #subsuites, but only 500px outside it,
    // which makes it difficult to see the chart in 'lines'. Reset those
    // min-widths so that the chart can expand to an appropriate size.
    document.body.style.margin = 0;
    document.body.style.minWidth = 0;
    document.documentElement.style.minWidth = 0;

    originalFetch = window.fetch;
    window.fetch = async(url, options) => {
      return {
        ok: true,
        async json() {
          if (url === TimeseriesRequest.URL) {
            const data = [];
            const sequenceLength = 100;
            for (let i = 0; i < sequenceLength; i += 1) {
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
      if (!child.matches('chart-compound')) continue;
      document.body.removeChild(child);
    }
    window.fetch = originalFetch;
  });

  test('load', async function() {
    const cc = await fixture();
    assert.lengthOf(cc.minimapLayout.lineDescriptors, 1);
    assert.isUndefined(cc.minimapLayout.lineDescriptors[0].buildType);
    assert.lengthOf(cc.minimapLayout.lines, 1);
    assert.lengthOf(cc.minimapLayout.lines[0].data, 100);

    assert.lengthOf(cc.chartLayout.lineDescriptors, 2);
    assert.isUndefined(cc.chartLayout.lineDescriptors[0].buildType);
    assert.strictEqual('ref', cc.chartLayout.lineDescriptors[1].buildType);
    assert.lengthOf(cc.chartLayout.lines, 2);
    assert.lengthOf(cc.chartLayout.lines[0].data, 9);
    assert.lengthOf(cc.chartLayout.lines[1].data, 9);
  });

  test('brushMinimap', async function() {
    const cc = await fixture();
    cc.dispatch(UPDATE('test.minimapLayout.xAxis', {brushes: [
      {xPct: '10%'}, {xPct: '90%'},
    ]}));
    cc.$.minimap.dispatchEvent(new CustomEvent('brush', {
      detail: {sourceEvent: {detail: {state: 'end'}}},
    }));
    await afterRender();

    assert.closeTo(cc.chartLayout.minRevision,
        cc.minimapLayout.xAxis.range.lerp(0.1), MS_PER_YEAR / 100);
    assert.closeTo(cc.chartLayout.maxRevision,
        cc.minimapLayout.xAxis.range.lerp(0.9), MS_PER_YEAR / 100);
  });

  test('linkedCursor', async function() {
    const cc = await fixture();
    await cc.dispatch(UPDATE('linked', {
      linkedCursorRevision: NOW_MS - (MS_PER_YEAR / 20),
      linkedCursorScalar: new tr.b.Scalar(
          tr.b.Unit.byName.timeDurationInMs, 2.5),
    }));
    await afterRender();

    assert.strictEqual('94.9%', cc.minimapLayout.xAxis.cursor.pct);
    assert.isUndefined(cc.minimapLayout.yAxis.cursor);
    assert.strictEqual('37.8%', cc.chartLayout.xAxis.cursor.pct);
    assert.strictEqual('26.8%', cc.chartLayout.yAxis.cursor.pct);
  });

  test('linkedRevisions', async function() {
    const cc = await fixture();
    await cc.dispatch(UPDATE('linked', {
      linkedMinRevision: NOW_MS - (MS_PER_YEAR / 2),
      linkedMaxRevision: NOW_MS - (MS_PER_YEAR / 20),
    }));
    await afterRender();
    await afterRender();

    assert.strictEqual('49%', cc.minimapLayout.xAxis.brushes[0].xPct);
    assert.strictEqual('94.4%', cc.minimapLayout.xAxis.brushes[1].xPct);
    assert.closeTo(cc.chartLayout.minRevision,
        cc.minimapLayout.xAxis.range.lerp(0.5), MS_PER_YEAR / 100);
    assert.closeTo(cc.chartLayout.maxRevision,
        cc.minimapLayout.xAxis.range.lerp(0.95), MS_PER_YEAR / 100);
  });

  test('linkedMode', async function() {
    const cc = await fixture();
    await cc.dispatch(UPDATE('linked', {
      linkedMode: MODE.DELTA,
    }));
    await afterRender();

    assert.strictEqual(cc.mode, MODE.DELTA);
    assert.strictEqual(cc.chartLayout.mode, MODE.DELTA);
    assert.strictEqual(cc.chartLayout.lines[0].data[0].y, 0);
    assert.strictEqual(cc.chartLayout.lines[1].data[0].y, 0);
  });

  test('linkedZeroYAxis', async function() {
    const cc = await fixture();
    let yRange = cc.chartLayout.yAxis.rangeForUnitName.get(
        'timeDurationInMs');
    assert.isBelow(0, yRange.min);

    await cc.dispatch(UPDATE('linked', {
      linkedZeroYAxis: true,
    }));
    await afterRender();

    assert.isTrue(cc.zeroYAxis);
    yRange = cc.chartLayout.yAxis.rangeForUnitName.get(
        'timeDurationInMs');
    assert.isAbove(0, yRange.min);
    assert.isAbove(yRange.max, 3);
  });

  test('linkedFixedXAxis', async function() {
    const cc = await fixture();
    await cc.dispatch(UPDATE('linked', {
      linkedFixedXAxis: false,
    }));
    await afterRender();

    assert.isFalse(cc.fixedXAxis);
    assert.isFalse(cc.chartLayout.fixedXAxis);
  });

  test('Error loading timeseries', async function() {
    const setupFetch = window.fetch;
    window.fetch = async(url, options) => {
      if (url === TimeseriesRequest.URL) {
        return {
          ok: false,
          status: 500,
          statusText: 'test',
        };
      }
      return await setupFetch(url, options);
    };

    const section = await fixture();
    const divs = findElements(section, e => e.matches('div.error') &&
      /Error loading timeseries for suite\/ms\/master:bot\/: 500 test/.test(
          e.textContent));
    assert.lengthOf(divs, 1);
  });
});
