/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import AlertsRequest from './alerts-request.js';
import ChromeperfApp from './chromeperf-app.js';
import DescribeRequest from './describe-request.js';
import RecentBugsRequest from './recent-bugs-request.js';
import ReportControls from './report-controls.js';
import ReportNamesRequest from './report-names-request.js';
import SessionIdRequest from './session-id-request.js';
import SessionStateRequest from './session-state-request.js';
import SheriffsRequest from './sheriffs-request.js';
import findElements from './find-elements.js';
import {UPDATE} from './simple-redux.js';
import {afterRender, animationFrame} from './utils.js';
import {assert} from 'chai';

suite('chromeperf-app', function() {
  async function fixture() {
    const app = document.createElement('chromeperf-app');
    app.statePath = 'test';
    document.body.appendChild(app);
    await afterRender();
    await afterRender();  // Again to wait for receiveSessionState.
    return app;
  }

  let originalFetch;
  let originalAuthorizationHeaders;
  let originalUserProfile;
  setup(() => {
    originalUserProfile = window.getUserProfileAsync;
    window.getUserProfileAsync = async() => {
      return {getEmail() { return 'you@there.com'; }};
    };
    originalAuthorizationHeaders = window.getAuthorizationHeaders;
    window.getAuthorizationHeaders = async() => {
      return {};
    };
    originalFetch = window.fetch;
    window.fetch = async(url, options) => {
      return {
        ok: true,
        async json() {
          if (url === RecentBugsRequest.URL) {
            return {
              bugs: [
                {
                  summary: 'uh oh',
                  id: 10,
                  status: 'WontFix',
                  owner: {name: 'you@there.com'},
                },
                {
                  summary: '42% regression in the stuff at 123:456',
                  id: 20,
                  status: 'Assigned',
                  owner: {name: 'you@there.com'},
                },
              ],
            };
          }
          if (url.startsWith(SessionStateRequest.URL)) {
            return {
              reportSection: {
                milestone: 72,
                sources: ['from session'],
              },
              showingReportSection: true,
            };
          }
          if (url === DescribeRequest.URL) {
            return {
              measurements: ['measure'],
              bots: ['master:bot'],
            };
          }
          if (url === AlertsRequest.URL) {
            return {anomalies: []};
          }
          if (url === SheriffsRequest.URL) {
            return ['ccc', 'ddd'];
          }
          if (url === ReportNamesRequest.URL) {
            return [{
              name: ReportControls.DEFAULT_NAME,
              id: 42,
              modified: new Date(),
            }];
          }
        },
      };
    };
  });
  teardown(() => {
    for (const child of document.body.children) {
      if (!child.matches('chromeperf-app')) continue;
      document.body.removeChild(child);
    }
    window.getUserProfileAsync = originalUserProfile;
    window.fetch = originalFetch;
    window.getAuthorizationHeaders = originalAuthorizationHeaders;
  });

  test('newAlerts', async function() {
    const app = await fixture();
    assert.lengthOf(app.alertsSectionIds, 0);
    app.$.new_alerts.click();
    await afterRender();
    assert.lengthOf(app.alertsSectionIds, 1);
  });

  test('closeAlerts', async function() {
    const app = await fixture();
    app.$.new_alerts.click();
    await afterRender();
    const alerts = app.shadowRoot.querySelector('alerts-section');
    alerts.dispatchEvent(new CustomEvent('close-section'));
    await afterRender();
    assert.lengthOf(app.alertsSectionIds, 0);
    // Empty alerts-sections are forgotten instantly and can't be reopened.
    assert.lengthOf(app.closedAlertsIds, 0);
  });

  test('reopenAlerts', async function() {
    const app = await fixture();
    app.$.new_alerts.click();
    await afterRender();
    const alerts = app.shadowRoot.querySelector('alerts-section');
    // Make the alerts-section not empty so that it can be reopened.
    app.dispatch(UPDATE(alerts.statePath + '.bug', {
      selectedOptions: [42],
    }));
    alerts.$.controls.dispatchEvent(new CustomEvent('sources', {
      detail: {sources: [{bug: 42}]},
    }));
    await afterRender();

    alerts.dispatchEvent(new CustomEvent('close-section'));
    await afterRender();
    assert.lengthOf(app.alertsSectionIds, 0);
    assert.lengthOf(app.closedAlertsIds, 1);

    app.$.reopen_alerts.click();
    await afterRender();
    assert.lengthOf(app.alertsSectionIds, 1);
  });

  test('newChart', async function() {
    const app = await fixture();
    assert.lengthOf(app.chartSectionIds, 0);

    app.$.new_chart.click();
    await afterRender();
    assert.lengthOf(app.chartSectionIds, 1);
  });

  test('closeChart', async function() {
    const app = await fixture();
    app.$.new_chart.click();
    await afterRender();
    await afterRender();
    const chart = app.shadowRoot.querySelector('chart-section');
    chart.dispatchEvent(new CustomEvent('close-section'));
    await afterRender();
    assert.lengthOf(app.chartSectionIds, 0);
    // Empty chart-sections are forgotten instantly and can't be reopened.
    assert.lengthOf(app.closedChartIds, 0);
  });

  test('closeAllCharts', async function() {
    const app = await fixture();
    app.$.new_chart.click();
    await afterRender();
    app.$.close_charts.click();
    await afterRender();
    assert.lengthOf(app.chartSectionIds, 0);
  });

  test('reopenCharts', async function() {
    const app = await fixture();
    app.$.new_chart.click();
    await afterRender();
    const chart = app.shadowRoot.querySelector('chart-section');
    // Make the chart-section not empty so that it can be reopened.
    await app.dispatch(UPDATE(chart.statePath + '.descriptor', {
      suite: {
        ...chart.descriptor.suite,
        selectedOptions: ['suite:name'],
      },
      measurement: {
        ...chart.descriptor.measurement,
        selectedOptions: ['ms'],
      },
      bot: {
        ...chart.descriptor.bot,
        selectedOptions: ['master:bot'],
      },
    }));
    chart.$.controls.dispatchEvent(new CustomEvent('matrix-change'));
    await afterRender();

    chart.dispatchEvent(new CustomEvent('close-section'));
    await afterRender();
    assert.lengthOf(app.chartSectionIds, 0);
    assert.lengthOf(app.closedChartIds, 1);

    app.$.reopen_chart.click();
    await afterRender();
    assert.lengthOf(app.chartSectionIds, 1);
  });

  test('restoreFromRoute session', async function() {
    const app = await fixture();
    await app.dispatch('restoreFromRoute', app.statePath, new URLSearchParams({
      session: 42,
    }));
    while (app.reduxRoutePath === '#') await animationFrame();
    assert.strictEqual('report=from+session&minRev=612437&maxRev=625896',
        app.reduxRoutePath);
  });

  test('restoreFromRoute report', async function() {
    const app = await fixture();
    await app.dispatch('restoreFromRoute', app.statePath, new URLSearchParams({
      report: 'name',
    }));
    await afterRender();
    assert.strictEqual('name', app.reportSection.source.selectedOptions[0]);
  });

  test('restoreFromRoute sheriff', async function() {
    const app = await fixture();
    await app.dispatch('restoreFromRoute', app.statePath, new URLSearchParams({
      sheriff: 'name',
    }));
    await afterRender();
    assert.strictEqual('name', app.alertsSectionsById[
        app.alertsSectionIds[0]].sheriff.selectedOptions[0]);
    assert.strictEqual('sheriff=name', app.reduxRoutePath);
  });

  test('restoreFromRoute chart', async function() {
    const app = await fixture();
    await app.dispatch('restoreFromRoute', app.statePath, new URLSearchParams({
      suite: 'suite:name',
      measurement: 'measure',
      bot: 'master:bot',
    }));
    await afterRender();
    assert.lengthOf(app.chartSectionIds, 1);
    assert.strictEqual('suite:name', app.chartSectionsById[
        app.chartSectionIds].descriptor.suite.selectedOptions[0]);
    assert.strictEqual('measure', app.chartSectionsById[
        app.chartSectionIds].descriptor.measurement.selectedOptions[0]);
    assert.strictEqual('master:bot', app.chartSectionsById[
        app.chartSectionIds].descriptor.bot.selectedOptions[0]);
  });

  test('getRecentBugs', async function() {
    const app = await fixture();
    await app.dispatch('userUpdate', app.statePath);
    const state = app.getState();
    assert.lengthOf(state.recentPerformanceBugs, 2);
    assert.strictEqual(123, state.recentPerformanceBugs[1].revisionRange.min);
    assert.strictEqual(456, state.recentPerformanceBugs[1].revisionRange.max);
  });

  test('Error loading session', async function() {
    const setupFetch = window.fetch;
    window.fetch = async(url, options) => {
      if (url.startsWith(SessionStateRequest.URL + '?')) {
        return {
          ok: false,
          status: 500,
          statusText: 'test',
        };
      }
      return await setupFetch(url, options);
    };

    const app = await fixture();
    await app.dispatch('restoreFromRoute', app.statePath, new URLSearchParams({
      session: 42,
    }));
    await afterRender();
    const divs = findElements(app, e => e.matches('div.error') &&
      /Error loading session/.test(e.textContent));
    assert.lengthOf(divs, 1);
  });

  test('Error saving session', async function() {
    const setupFetch = window.fetch;
    window.fetch = async(url, options) => {
      if (url === SessionIdRequest.URL) {
        return {
          ok: false,
          status: 500,
          statusText: 'test',
        };
      }
      return await setupFetch(url, options);
    };

    const app = await fixture();

    // Make two non-empty chart-sections so app tries to save session state.
    app.$.new_chart.click();
    await afterRender();
    let chart = app.shadowRoot.querySelector('chart-section');
    await app.dispatch(UPDATE(chart.statePath + '.descriptor', {
      suite: {
        ...chart.descriptor.suite,
        selectedOptions: ['suite:name'],
      },
      measurement: {
        ...chart.descriptor.measurement,
        selectedOptions: ['ms'],
      },
      bot: {
        ...chart.descriptor.bot,
        selectedOptions: ['master:bot'],
      },
    }));
    chart.$.controls.dispatchEvent(new CustomEvent('matrix-change'));
    await afterRender();

    app.$.new_chart.click();
    await afterRender();
    chart = findElements(app, e => e.matches('chart-section'))[1];
    await app.dispatch(UPDATE(chart.statePath + '.descriptor', {
      suite: {
        ...chart.descriptor.suite,
        selectedOptions: ['suite:name'],
      },
      measurement: {
        ...chart.descriptor.measurement,
        selectedOptions: ['ms'],
      },
      bot: {
        ...chart.descriptor.bot,
        selectedOptions: ['master:bot'],
      },
    }));
    chart.$.controls.dispatchEvent(new CustomEvent('matrix-change'));
    await afterRender();

    const divs = findElements(app, e => e.matches('div.error') &&
      /Error saving session state: 500 test/.test(e.textContent));
    assert.lengthOf(divs, 1);
  });
});
