/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import {CHAIN, ENSURE, UPDATE} from './simple-redux.js';
import {DetailsTable} from './details-table.js';
import {RequestBase} from './request-base.js';
import {STORE} from './element-base.js';
import {TimeseriesRequest} from './timeseries-request.js';
import {assert} from 'chai';
import {findElements} from './find-elements.js';

import {
  afterRender,
  denormalize,
  setDebugForTesting,
  setProductionForTesting,
  timeout,
} from './utils.js';

suite('details-table', function() {
  let MS_PER_YEAR;  // tr might not be loaded yet.
  const NOW_MS = new Date().getTime();

  let originalFetch;
  setup(() => {
    setDebugForTesting(true);
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
            const minRevision = parseInt(options.body.get('min_revision') || 1);
            const maxRevision = Math.min(sequenceLength, parseInt(
                options.body.get('max_revision') || sequenceLength));
            for (let i = minRevision; i <= maxRevision; i += 1) {
              const pct = (sequenceLength - i - 1) / sequenceLength;
              const timestamp = NOW_MS - pct * MS_PER_YEAR;
              data.push({
                revision: i,
                timestamp,
                avg: 1 + (i % 3),
                count: 1,
                std: (i % 4) / 2,
                histogram: tr.v.Histogram.create('', tr.b.Unit.byName.count, [
                  1, 10, 100,
                ]).asDict(),
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
      if (!child.matches('details-table')) continue;
      document.body.removeChild(child);
    }
    window.fetch = originalFetch;
  });

  async function fixture() {
    const dt = document.createElement('details-table');
    dt.statePath = 'test';
    STORE.dispatch(CHAIN(
        UPDATE('', {
          revisionInfo: {},
          bisectMasterWhitelist: ['whitelistedMaster'],
          bisectSuiteBlacklist: ['blacklistedSuite'],
        }),
        ENSURE('test'),
        UPDATE('test', DetailsTable.buildState({}))));
    document.body.appendChild(dt);
    await afterRender();
    return dt;
  }

  test('load', async function() {
    const dt = await fixture();
    await STORE.dispatch(UPDATE('test', {
      lineDescriptors: [{
        suites: ['suite'],
        bots: ['master:bot'],
        measurement: 'ms',
        statistic: 'avg',
        cases: [],
      }],
      revisionRanges: [
        tr.b.math.Range.fromExplicitRange(2.5, 4.5),
        tr.b.math.Range.fromExplicitRange(5.5, 6.5),
      ],
    }));
    await afterRender();
    assert.lengthOf(dt.bodies, 1);
    assert.lengthOf(dt.bodies[0].linkRows, 1);
    assert.strictEqual('Upload timestamp', dt.bodies[0].linkRows[0].label);
    assert.lengthOf(dt.bodies[0].scalarRows, 3);
    assert.strictEqual('avg', dt.bodies[0].scalarRows[0].label);
    assert.lengthOf(dt.bodies[0].scalarRows[0].cells, 2);
    assert.strictEqual(1.5, dt.bodies[0].scalarRows[0].cells[0].value);
    assert.strictEqual(1, dt.bodies[0].scalarRows[0].cells[1].value);
    assert.strictEqual('count', dt.bodies[0].scalarRows[1].label);
    assert.lengthOf(dt.bodies[0].scalarRows[1].cells, 2);
    assert.strictEqual(2, dt.bodies[0].scalarRows[1].cells[0].value);
    assert.strictEqual(1, dt.bodies[0].scalarRows[1].cells[1].value);
    assert.strictEqual('std', dt.bodies[0].scalarRows[2].label);
    assert.lengthOf(dt.bodies[0].scalarRows[2].cells, 2);
  });

  test('extractCommonLinkRows', async function() {
    const bodies = [
      {
        linkRows: [
          // This should be extracted because it is common to both bodies.
          {label: 'a', cells: [
            {label: 'a0', href: 'http://a0'},
            {label: 'a1', href: 'http://a1'},
          ]},

          // This should not be extracted because one href is different between
          // the two bodies.
          {label: 'b', cells: [
            {label: 'b0', href: 'http://b0'},
            {label: 'b1', href: 'http://b1'},
          ]},

          // This should not be extracted because it is only found in one of the
          // bodies.
          {label: 'c', cells: [
            {label: 'c0', href: 'http://c0'},
            {label: 'c1', href: 'http://c1'},
          ]},
        ],
      },
      {
        linkRows: [
          {label: 'a', cells: [
            {label: 'a0', href: 'http://a0'},
            {label: 'a1', href: 'http://a1'},
          ]},
          {label: 'b', cells: [
            {label: 'b0', href: 'http://b0'},
            {label: 'b1', href: 'http://DIFFERENT'},
          ]},
        ],
      },
    ];
    const actual = DetailsTable.extractCommonLinkRows(bodies);
    const expected = [
      {label: 'a', cells: [
        {label: 'a0', href: 'http://a0'},
        {label: 'a1', href: 'http://a1'},
      ]},
    ];
    assert.deepEqual(actual, expected);
    assert.lengthOf(bodies[0].linkRows, 2);
    assert.strictEqual('b', bodies[0].linkRows[0].label);
    assert.strictEqual('c', bodies[0].linkRows[1].label);
    assert.lengthOf(bodies[1].linkRows, 1);
    assert.strictEqual('b', bodies[1].linkRows[0].label);
  });

  test('descriptorFlags', async function() {
    const flags = DetailsTable.descriptorFlags([
      {suites: ['suite'], measurement: 'measure a', bots: [], cases: ['d']},
      {suites: ['suite'], measurement: 'measure b', bots: [], cases: ['c']},
    ]);
    assert.isFalse(flags.suite);
    assert.isTrue(flags.measurement);
    assert.isFalse(flags.bot);
    assert.isTrue(flags.cases);
  });

  test('buildCell', async function() {
    const range = tr.b.math.Range.fromExplicitRange(3, 4);
    const timeserieses = [
      [
        {
          revision: 1,
          timestamp: new Date(1000),
          avg: 10,
          count: 10,
          std: 10,
          unit: tr.b.Unit.byName.count,
          revisions: {
            r_chromium: '1',
            r_arc: '1',
          },
        },
        {
          revision: 3,
          timestamp: new Date(3000),
          avg: 30,
          count: 30,
          std: 30,
          unit: tr.b.Unit.byName.count,
          revisions: {
            r_chromium: '3',
            r_arc: '3',
          },
        },
        {
          revision: 4,
          timestamp: new Date(4000),
          avg: 40,
          count: 40,
          std: 40,
          unit: tr.b.Unit.byName.count,
          revisions: {
            r_chromium: '4',
            r_arc: '4',
          }
        },
      ],
      [
        {
          revision: 2,
          timestamp: new Date(2000),
          avg: 20,
          count: 20,
          std: 20,
          unit: tr.b.Unit.byName.count,
          revisions: {
            r_chromium: '2',
            r_mojo: '2',
          },
        },
        {
          revision: 3,
          timestamp: new Date(3000),
          avg: 30,
          count: 30,
          std: 30,
          unit: tr.b.Unit.byName.count,
          revisions: {
            r_chromium: '3',
            r_mojo: '3',
          }
        },
        {
          revision: 4,
          timestamp: new Date(4000),
          avg: 40,
          count: 40,
          std: 40,
          unit: tr.b.Unit.byName.count,
          revisions: {
            r_chromium: '4',
            r_mojo: '4',
          }
        },
      ],
    ];
    const revisionInfo = {
      r_chromium: {
        name: 'Chromium Git Hash',
        url: 'https://chromium.googlesource.com/chromium/src/+log/{{R1}}..{{R2}}',
      },
      r_arc: {
        name: 'ARC Revision',
        url: 'https://chrome-internal.googlesource.com/arc/arc/+log/{{R1}}..{{R2}}',
      },
    };
    const masterWhitelist = null;
    const suiteBlacklist = null;
    const lineDescriptor = {
      suites: ['suite'],
      measurement: 'measure',
      bots: ['master:bot'],
      cases: ['case'],
      statistic: 'avg',
      buildType: 'test',
    };
    const {scalars, links, alerts, bisectCell} = DetailsTable.buildCell(
        lineDescriptor, timeserieses, range, revisionInfo,
        masterWhitelist, suiteBlacklist);

    assert.lengthOf(links, 3);
    assert.strictEqual(links.get('Chromium Git Hash').href,
        'https://chromium.googlesource.com/chromium/src/+log/2..4');
    assert.strictEqual('2 - 4', links.get('Chromium Git Hash').label);
    assert.strictEqual(links.get('ARC Revision').href,
        'https://chrome-internal.googlesource.com/arc/arc/+log/2..4');
    assert.strictEqual('2 - 4', links.get('ARC Revision').label);
    assert.strictEqual('', links.get('Upload timestamp').href);
    assert.strictEqual('1970-01-01 00:00:03 - 1970-01-01 00:00:04',
        links.get('Upload timestamp').label);

    assert.lengthOf(scalars, 3);
    assert.approximately(35.714, scalars.get('avg').value, 1e-3);
    assert.strictEqual(tr.b.Unit.byName.count, scalars.get('avg').unit);
    assert.approximately(91.807, scalars.get('std').value, 1e-3);
    assert.strictEqual(tr.b.Unit.byName.count, scalars.get('std').unit);
    assert.strictEqual(140, scalars.get('count').value);
    assert.strictEqual(tr.b.Unit.byName.count, scalars.get('count').unit);
  });

  test('anonymous cannot bisect', async function() {
    setProductionForTesting(true);
    RequestBase.getAuthorizationHeaders = () => {return {};};
    const dt = await fixture();
    STORE.dispatch(UPDATE('test', {
      lineDescriptors: [{
        suites: ['suite'],
        bots: ['master:bot'],
        measurement: 'ms',
        statistic: 'avg',
        cases: [],
      }],
      revisionRanges: [
        tr.b.math.Range.fromExplicitRange(2.5, 3.5),
      ],
    }));
    await afterRender();
    assert.isDefined(findElements(dt, e =>
      /Please sign in to start bisect jobs/.test(e.textContent))[0]);
  });

  test('single revision cannot bisect', async function() {
    setProductionForTesting(true);
    RequestBase.getAuthorizationHeaders = () => {return {};};
    const dt = await fixture();
    STORE.dispatch(UPDATE('', {
      userEmail: 'you@here.com',
      bisectMasterWhitelist: ['master'],
    }));
    STORE.dispatch(UPDATE('test', {
      lineDescriptors: [{
        suites: ['suite'],
        bots: ['master:bot'],
        measurement: 'ms',
        statistic: 'avg',
        cases: [],
      }],
      revisionRanges: [
        tr.b.math.Range.fromExplicitRange(2.5, 3.5),
      ],
    }));
    await afterRender();
    assert.isDefined(findElements(dt, e =>
      /Unable to bisect single revision/.test(e.tooltip))[0]);
  });

  test('multiple timeseries cannot bisect', async function() {
    setProductionForTesting(true);
    RequestBase.getAuthorizationHeaders = () => {return {};};
    const dt = await fixture();
    STORE.dispatch(UPDATE('', {
      userEmail: 'you@here.com',
      bisectMasterWhitelist: ['master'],
    }));
    STORE.dispatch(UPDATE('test', {
      lineDescriptors: [{
        suites: ['suiteA', 'suiteB'],
        bots: ['master:botA', 'master:botB'],
        measurement: 'ms',
        statistic: 'avg',
        cases: ['caseA', 'caseB'],
      }],
      revisionRanges: [
        tr.b.math.Range.fromExplicitRange(2.5, 3.5),
      ],
    }));
    await afterRender();
    const expected = /Unable to bisect with multiple suites, bots, cases/;
    assert.isDefined(findElements(dt, e =>
      expected.test(e.textContent))[0]);
  });

  test('ref build cannot bisect', async function() {
    setProductionForTesting(true);
    RequestBase.getAuthorizationHeaders = () => {return {};};
    const dt = await fixture();
    STORE.dispatch(UPDATE('', {userEmail: 'you@here.com'}));
    STORE.dispatch(UPDATE('test', {
      lineDescriptors: [{
        suites: ['suite'],
        bots: ['master:bot'],
        measurement: 'ms',
        statistic: 'avg',
        cases: [],
        buildType: 'ref',
      }],
      revisionRanges: [
        tr.b.math.Range.fromExplicitRange(2.5, 3.5),
      ],
    }));
    await afterRender();
    assert.isDefined(findElements(dt, e =>
      /Unable to bisect ref build/.test(e.textContent))[0]);
  });

  test('blacklisted suite cannot bisect', async function() {
    setProductionForTesting(true);
    RequestBase.getAuthorizationHeaders = () => {return {};};
    const dt = await fixture();
    STORE.dispatch(UPDATE('', {
      userEmail: 'you@here.com',
      bisectMasterWhitelist: ['master'],
      bisectSuiteBlacklist: ['suite'],
    }));
    STORE.dispatch(UPDATE('test', {
      lineDescriptors: [{
        suites: ['suite'],
        bots: ['master:bot'],
        measurement: 'ms',
        statistic: 'avg',
        cases: [],
      }],
      revisionRanges: [
        tr.b.math.Range.fromExplicitRange(2.5, 3.5),
      ],
    }));
    await afterRender();
    assert.isDefined(findElements(dt, e =>
      /Unable to bisect suite "suite"/.test(e.textContent))[0]);
  });

  test('blacklisted master cannot bisect', async function() {
    setProductionForTesting(true);
    RequestBase.getAuthorizationHeaders = () => {return {};};
    const dt = await fixture();
    STORE.dispatch(UPDATE('', {userEmail: 'you@here.com'}));
    STORE.dispatch(UPDATE('test', {
      lineDescriptors: [{
        suites: ['suite'],
        bots: ['master:bot'],
        measurement: 'ms',
        statistic: 'avg',
        cases: [],
      }],
      revisionRanges: [
        tr.b.math.Range.fromExplicitRange(2.5, 3.5),
      ],
    }));
    await afterRender();
    assert.isDefined(findElements(dt, e =>
      /Unable to bisect on master bots/.test(e.textContent))[0]);
  });

  test('bisect', async function() {
    setProductionForTesting(true);
    RequestBase.getAuthorizationHeaders = () => {return {};};
    const dt = await fixture();
    STORE.dispatch(UPDATE('', {
      userEmail: 'you@here.com',
      bisectMasterWhitelist: ['master'],
    }));
    STORE.dispatch(UPDATE('test', {
      lineDescriptors: [{
        suites: ['suite'],
        bots: ['master:bot'],
        measurement: 'ms',
        statistic: 'avg',
        cases: [],
      }],
      revisionRanges: [
        tr.b.math.Range.fromExplicitRange(2.5, 4.5),
      ],
    }));
    await afterRender();
    assert.isDefined(findElements(dt, e =>
      e.matches('bisect-dialog') && e.able)[0]);
  });

  test('histogram', async function() {
    const dt = await fixture();
    STORE.dispatch(UPDATE('test', {
      lineDescriptors: [{
        suites: ['suite'],
        bots: ['master:bot'],
        measurement: 'ms',
        statistic: 'avg',
        cases: [],
      }],
      revisionRanges: [
        tr.b.math.Range.fromExplicitRange(2.5, 4.5),
      ],
    }));
    await afterRender();
    const bars = findElements(dt, e =>
      e.matches('rect') &&
      e.getAttribute('x') === '0%' &&
      e.getAttribute('width') === '100%');
    assert.lengthOf(bars, 3);
  });
});
