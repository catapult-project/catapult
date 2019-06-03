/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import ResultChannelSender from './result-channel-sender.js';
import {TimeseriesRequest, LEVEL_OF_DETAIL} from './timeseries-request.js';
import {assert} from 'chai';
import {denormalize, timeout, setDebugForTesting} from './utils.js';

suite('TimeseriesRequest', function() {
  let originalFetch;
  setup(() => {
    originalFetch = window.fetch;
  });
  teardown(() => {
    window.fetch = originalFetch;
  });

  test('reader', async function() {
    setDebugForTesting(false);
    window.fetch = async(url, options) => {
      return {
        ok: true,
        async json() {
          return {
            units: 'ms',
            data: [[1, 3]],
          };
        }
      };
    };

    const request = new TimeseriesRequest({
      levelOfDetail: LEVEL_OF_DETAIL.XY,
    });
    const reader = request.reader();

    const sender = new ResultChannelSender(request.channelName);
    sender.send((async function* () {
      yield {
        units: 'ms',
        data: [{
          revision: 5,
          timestamp: 6,
          avg: 7,
          count: 8,
        }],
      };
    })());

    const results = [];
    for await (const result of reader) {
      results.push(result);
    }
    assert.deepEqual(results, [
      [
        {
          unit: tr.b.Unit.byName.timeDurationInMs,
          revision: 1,
          avg: 3,
          count: 1,
        },
      ],
      [
        {
          unit: tr.b.Unit.byName.timeDurationInMs,
          revision: 5,
          timestamp: new Date(6),
          avg: 7,
          count: 8,
        },
      ],
    ]);
  });

  test('xy', () => {
    const request = new TimeseriesRequest({
      levelOfDetail: LEVEL_OF_DETAIL.XY,
    });
    const expectedColumns = 'revision,avg';
    assert.strictEqual(request.body_.get('columns'), expectedColumns);
  });

  test('alerts', () => {
    const request = new TimeseriesRequest({
      levelOfDetail: LEVEL_OF_DETAIL.ALERTS,
    });
    const expectedColumns = 'revision,alert';
    assert.strictEqual(request.body_.get('columns'), expectedColumns);
  });

  test('annotations', () => {
    const request = new TimeseriesRequest({
      levelOfDetail: LEVEL_OF_DETAIL.ANNOTATIONS,
    });
    const expectedColumns =
      'alert,avg,count,diagnostics,revision,revisions,timestamp';
    assert.strictEqual(request.body_.get('columns'), expectedColumns);
  });

  test('details', async function() {
    const request = new TimeseriesRequest({
      levelOfDetail: LEVEL_OF_DETAIL.DETAILS,
    });
    const expectedColumns = 'revision,timestamp,avg,std,count,' +
      'revisions,annotations,alert';
    assert.strictEqual(request.body_.get('columns'), expectedColumns);
  });

  test('postProcess TBM2 annotations', async() => {
    const unit = tr.b.Unit.byName.timeDurationInMs;
    window.fetch = async(url, options) => {
      return {
        ok: true,
        async json() {
          const diagnostics = {
            [tr.v.d.RESERVED_NAMES.DEVICE_IDS]: new tr.v.d.GenericSet([
              'device a']).asDict(),
          };
          const revisions = {
            r_v8: 12345,
          };
          const data = [
            {
              revision: 1,
              timestamp: 1000,
              avg: 10,
              count: 1,
              diagnostics,
              revisions,
            },
          ];
          return {
            units: unit.jsonName,
            data: denormalize(
                data, options.body.get('columns').split(',')),
          };
        }
      };
    };
    const request = new TimeseriesRequest({
      levelOfDetail: LEVEL_OF_DETAIL.ANNOTATIONS,
    });
    const response = await request.response;
    assert.lengthOf(response, 1);
    assert.strictEqual(unit, response[0].unit);
    assert.strictEqual(1, response[0].revision);
    assert.strictEqual(1000, response[0].timestamp.getTime());
    assert.strictEqual(10, response[0].avg);
    assert.strictEqual(1, response[0].count);
    assert.instanceOf(response[0].diagnostics, tr.v.d.DiagnosticMap);
    assert.strictEqual('device a', tr.b.getOnlyElement(
        response[0].diagnostics.get(tr.v.d.RESERVED_NAMES.DEVICE_IDS)));
    assert.strictEqual(12345, response[0].revisions.r_v8);
  });

  test('postProcess xy legacy unit', async() => {
    window.fetch = async(url, options) => {
      return {
        ok: true,
        async json() {
          const data = [
            {revision: 1, avg: 10, count: 1},
          ];
          return {
            units: 'kb',
            data: denormalize(
                data, options.body.get('columns').split(',')),
          };
        }
      };
    };
    const request = new TimeseriesRequest({
      levelOfDetail: LEVEL_OF_DETAIL.XY,
    });
    const response = await request.response;
    assert.lengthOf(response, 1);
    assert.strictEqual(tr.b.Unit.byName.sizeInBytes, response[0].unit);
    assert.strictEqual(1, response[0].revision);
    assert.strictEqual(10240, response[0].avg);
    assert.strictEqual(1, response[0].count);
  });
});
