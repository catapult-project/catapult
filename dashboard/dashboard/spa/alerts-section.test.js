/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import {assert} from 'chai';
import AlertsRequest from './alerts-request.js';
import AlertsSection from './alerts-section.js';
import DescribeRequest from './describe-request.js';
import ExistingBugRequest from './existing-bug-request.js';
import NewBugRequest from './new-bug-request.js';
import ReportNamesRequest from './report-names-request.js';
import SheriffsRequest from './sheriffs-request.js';
import findElements from './find-elements.js';
import {CHAIN, ENSURE, UPDATE} from './simple-redux.js';
import {afterRender} from './utils.js';

window.AUTH_CLIENT_ID = '';

suite('alerts-section', function() {
  async function fixture() {
    const section = document.createElement('alerts-section');
    section.statePath = 'test';
    await section.dispatch(CHAIN(
        UPDATE('', {
          recentPerformanceBugs: [
            {
              id: '123456',
              summary: 'bug 123456 summary',
              revisionRange: tr.b.math.Range.fromExplicitRange(123, 456),
            },
            {
              id: '234567',
              summary: 'bug 234567 summary',
              revisionRange: tr.b.math.Range.fromExplicitRange(234, 567),
            },
            {
              id: '345678',
              summary: 'bug 345678 summary',
              revisionRange: tr.b.math.Range.fromExplicitRange(345, 678),
            },
          ],
        }),
        ENSURE('test'),
        UPDATE('test', AlertsSection.buildState({}))));
    document.body.appendChild(section);
    await afterRender();
    return section;
  }

  let originalFetch;
  let existingBugBody;
  let newBugBody;
  setup(() => {
    window.IS_DEBUG = true;
    originalFetch = window.fetch;
    window.fetch = async(url, options) => {
      return {
        ok: true,
        async json() {
          if (url === DescribeRequest.URL) {
            return {};
          }
          if (url === NewBugRequest.URL) {
            newBugBody = options.body;
            return {bug_id: 57};
          }
          if (url === ReportNamesRequest.URL) {
            return [{name: 'aaa', id: 42, modified: new Date()}];
          }
          if (url === ExistingBugRequest.URL) {
            existingBugBody = options.body;
            return {};
          }
          if (url === SheriffsRequest.URL) {
            return [];
          }
          if (url === AlertsRequest.URL) {
            const improvements = Boolean(options.body.get('improvements'));
            const alerts = [];
            const measurements = ['mmm0', 'mmm1', 'mmm2'];
            const testCases = ['ccc0', 'ccc1', 'ccc2'];
            for (let i = 0; i < 10; ++i) {
              const revs = new tr.b.math.Range();
              revs.addValue(parseInt(1e6 * Math.random()));
              revs.addValue(parseInt(1e6 * Math.random()));
              alerts.push({
                bot: 'bot' + (i % 3),
                bug_components: [],
                bug_labels: [],
                descriptor: {
                  bot: 'master:bot' + (i * 3),
                  measurement: measurements[i % measurements.length],
                  statistic: 'avg',
                  testCase: testCases[i % testCases.length],
                  testSuite: 'system_health.common_desktop',
                },
                end_revision: revs.max,
                improvement: improvements && (Math.random() > 0.5),
                key: 'key' + i,
                master: 'master',
                median_after_anomaly: 100 * Math.random(),
                median_before_anomaly: 100 * Math.random(),
                start_revision: revs.min,
                test: (measurements[i % measurements.length] + '/' +
                       testCases[i % testCases.length]),
                units: measurements[i % measurements.length].startsWith(
                    'memory') ? 'sizeInBytes' : 'ms',
              });
            }
            alerts.sort((x, y) => x.start_revision - y.start_revision);
            return {
              anomalies: alerts,
            };
          }
        },
      };
    };

    localStorage.setItem('recentlyModifiedBugs', JSON.stringify([
      {id: 42, summary: 'bbb'},
    ]));
  });
  teardown(() => {
    for (const child of document.body.children) {
      if (!child.matches('alerts-section')) continue;
      document.body.removeChild(child);
    }
    window.fetch = originalFetch;
    localStorage.removeItem('recentlyModifiedBugs');
  });

  test('summary', async function() {
    assert.strictEqual('0 alerts',
        AlertsSection.summary(undefined, undefined));
    assert.strictEqual('0 alerts',
        AlertsSection.summary(true, undefined));

    assert.strictEqual('1 displayed in 1 group of 1 alert',
        AlertsSection.summary(true, [{alerts: [{}]}], 0));
    assert.strictEqual('1 displayed in 1 group of 10 alerts',
        AlertsSection.summary(true, [{alerts: [{}]}], 10));
    assert.strictEqual('2 displayed in 1 group of 2 alerts',
        AlertsSection.summary(true, [{alerts: [{}, {}]}], 0));
    assert.strictEqual('2 displayed in 2 groups of 2 alerts',
        AlertsSection.summary(true, [{alerts: [{}]}, {alerts: [{}]}], 0));

    assert.strictEqual('0 displayed in 0 groups of 0 alerts',
        AlertsSection.summary(false, [
          {triaged: {count: 1}, alerts: [{}]},
        ], 0));
    assert.strictEqual('1 displayed in 1 group of 1 alert',
        AlertsSection.summary(false, [
          {triaged: {count: 1}, alerts: [{}, {}]},
        ], 0));
    assert.strictEqual('1 displayed in 1 group of 1 alert',
        AlertsSection.summary(false, [
          {triaged: {count: 0}, alerts: [{}]},
          {triaged: {count: 1}, alerts: [{}]},
        ], 0));
  });

  test('triageNew', async function() {
    const section = await fixture();
    section.$.controls.dispatchEvent(new CustomEvent('sources', {
      detail: {sources: [
        {bug: 42},
      ]},
    }));
    await afterRender();

    const selectAll = findElements(section, e =>
      e.matches('th cp-checkbox'))[0];
    selectAll.click();
    let state = section.getState().test;
    assert.strictEqual(10, state.selectedAlertsCount);

    const button = findElements(section, e =>
      e.matches('div.button') && /New Bug/.test(e.textContent))[0];
    button.click();

    const submit = findElements(section, e =>
      e.matches('raised-button') && /SUBMIT/i.test(e.textContent))[0];
    submit.click();
    await afterRender();

    assert.deepEqual(['Pri-2', 'Type-Bug-Regression'],
        newBugBody.getAll('label'));
    assert.include(newBugBody.get('summary'), ' regression ');
    assert.include(newBugBody.get('summary'), ' at ');
    assert.strictEqual('', newBugBody.get('owner'));
    assert.strictEqual('you@chromium.org', newBugBody.get('cc'));
    assert.lengthOf(newBugBody.getAll('key'), 10);
    for (let i = 0; i < 10; ++i) {
      assert.include(newBugBody.getAll('key'), 'key' + i);
    }

    state = section.getState().test;
    assert.lengthOf(state.alertGroups, 0);
  });

  test('triageExisting', async function() {
    const section = await fixture();
    section.$.controls.dispatchEvent(new CustomEvent('sources', {
      detail: {sources: [
        {bug: 42},
      ]},
    }));
    await afterRender();

    const selectAll = findElements(section, e =>
      e.matches('th cp-checkbox'))[0];
    selectAll.click();
    let state = section.getState().test;
    assert.strictEqual(10, state.selectedAlertsCount);

    const button = findElements(section, e =>
      e.matches('div') && /Existing Bug/.test(e.textContent))[0];
    button.click();

    section.dispatch(UPDATE('test.existingBug', {bugId: '123456'}));
    await afterRender();

    const menu = findElements(section, e => e.matches('triage-existing'))[0];
    const submit = findElements(menu, e =>
      e.matches('raised-button') && /SUBMIT/i.test(e.textContent))[0];
    submit.click();
    await afterRender();

    assert.strictEqual('123456', existingBugBody.get('bug'));
    assert.lengthOf(existingBugBody.getAll('key'), 10);
    for (let i = 0; i < 10; ++i) {
      assert.include(existingBugBody.getAll('key'), 'key' + i);
    }

    state = section.getState().test;
    assert.lengthOf(state.alertGroups, 0);
  });

  test('ignore', async function() {
    const section = await fixture();
    section.$.controls.dispatchEvent(new CustomEvent('sources', {
      detail: {sources: [
        {bug: 42},
      ]},
    }));
    await afterRender();

    const selectAll = findElements(section, e =>
      e.matches('th cp-checkbox'))[0];
    selectAll.click();
    let state = section.getState().test;
    assert.strictEqual(10, state.selectedAlertsCount);

    const ignore = findElements(section, e =>
      e.matches('div') && /^\W*Ignore\W*$/i.test(e.textContent))[0];
    ignore.click();
    await afterRender();

    assert.strictEqual('-2', existingBugBody.get('bug'));
    assert.lengthOf(existingBugBody.getAll('key'), 10);
    for (let i = 0; i < 10; ++i) {
      assert.include(existingBugBody.getAll('key'), 'key' + i);
    }

    state = section.getState().test;
    assert.lengthOf(state.alertGroups, 0);
  });

  test('unassign', async function() {
    const section = await fixture();
    section.$.controls.dispatchEvent(new CustomEvent('sources', {
      detail: {sources: [
        {bug: 42},
      ]},
    }));
    await afterRender();

    const selectAll = findElements(section, e =>
      e.matches('th cp-checkbox'))[0];
    selectAll.click();
    let state = section.getState().test;
    assert.strictEqual(10, state.selectedAlertsCount);

    const unassign = findElements(section, e =>
      e.matches('div') && /^\W*Unassign\W*$/i.test(e.textContent))[0];
    unassign.click();
    await afterRender();

    assert.strictEqual('0', existingBugBody.get('bug'));
    assert.lengthOf(existingBugBody.getAll('key'), 10);
    for (let i = 0; i < 10; ++i) {
      assert.include(existingBugBody.getAll('key'), 'key' + i);
    }

    state = section.getState().test;
    assert.isBelow(0, state.alertGroups.length);
  });

  test('Error loading sheriffs', async function() {
    const setupFetch = window.fetch;
    window.fetch = async(url, options) => {
      if (url === SheriffsRequest.URL) {
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
      /Error loading sheriffs: 500 test/.test(e.textContent));
    assert.lengthOf(divs, 1);
  });

  test('Error loading report names', async function() {
    const setupFetch = window.fetch;
    window.fetch = async(url, options) => {
      if (url === ReportNamesRequest.URL) {
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
      /Error loading report names: 500 test/.test(e.textContent));
    assert.lengthOf(divs, 1);
  });

  test('Error loading alerts', async function() {
    const setupFetch = window.fetch;
    window.fetch = async(url, options) => {
      if (url === AlertsRequest.URL) {
        return {
          ok: false,
          status: 500,
          statusText: 'test',
        };
      }
      return await setupFetch(url, options);
    };

    const section = await fixture();
    section.$.controls.dispatchEvent(new CustomEvent('sources', {
      detail: {sources: [
        {bug: 42},
      ]},
    }));
    await afterRender();

    const divs = findElements(section, e => e.matches('div.error') &&
      /Error loading alerts: 500 test/.test(e.textContent));
    assert.lengthOf(divs, 1);
  });
});
