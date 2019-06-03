/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import ReportControls from './report-controls.js';
import ReportNamesRequest from './report-names-request.js';
import findElements from './find-elements.js';
import {CHAIN, ENSURE, UPDATE} from './simple-redux.js';
import {STORE} from './element-base.js';
import {afterRender} from './utils.js';
import {assert} from 'chai';

suite('report-controls', function() {
  async function fixture() {
    const controls = document.createElement('report-controls');
    controls.statePath = 'test';
    await STORE.dispatch(CHAIN(
        ENSURE('test'),
        UPDATE('test', ReportControls.buildState({}))));
    document.body.appendChild(controls);
    await afterRender();
    return controls;
  }

  let originalFetch;

  setup(() => {
    originalFetch = window.fetch;
    window.fetch = async(url, options) => {
      return {
        ok: true,
        async json() {
          if (url === ReportNamesRequest.URL) {
            return [
              {
                name: 'Chromium Performance Overview',
                id: 10,
                modified: new Date(),
              },
              {name: 'aaa', id: 42, modified: new Date()},
            ];
          }
        },
      };
    };
  });
  teardown(() => {
    for (const child of document.body.children) {
      if (!child.matches('report-controls')) continue;
      document.body.removeChild(child);
    }
    window.fetch = originalFetch;
  });

  test('connected', async function() {
    // ReportNamesRequest
    const controls = await fixture();
    assert.isDefined(findElements(controls, e =>
      new RegExp(ReportControls.DEFAULT_NAME).test(e.textContent))[0]);
    assert.isDefined(findElements(controls, e =>
      /aaa/.test(e.textContent))[0]);
  });

  test('milestones', async function() {
    const controls = await fixture();
    assert.strictEqual(ReportControls.CHROMIUM_MILESTONES[
        ReportControls.CURRENT_MILESTONE], controls.minRevision);
    assert.strictEqual('latest', controls.maxRevision);

    controls.shadowRoot.querySelector('#prev-mstone').click();
    await afterRender();
    assert.strictEqual(ReportControls.CHROMIUM_MILESTONES[
        ReportControls.CURRENT_MILESTONE - 1], controls.minRevision);
    assert.strictEqual(ReportControls.CHROMIUM_MILESTONES[
        ReportControls.CURRENT_MILESTONE], controls.maxRevision);

    controls.shadowRoot.querySelector('#next-mstone').click();
    await afterRender();
    assert.strictEqual(ReportControls.CHROMIUM_MILESTONES[
        ReportControls.CURRENT_MILESTONE], controls.minRevision);
    assert.strictEqual('latest', controls.maxRevision);
  });

  test('alerts', async function() {
    const controls = await fixture();
    let options;
    controls.addEventListener('alerts', e => {
      options = e.detail.options;
    });
    controls.shadowRoot.querySelector('#alerts').click();
    assert.strictEqual(ReportControls.CHROMIUM_MILESTONES[
        ReportControls.CURRENT_MILESTONE], controls.minRevision);
    assert.strictEqual('latest', options.maxRevision);
    assert.deepEqual([ReportControls.DEFAULT_NAME], options.reports);
    assert.isTrue(options.showingTriaged);
  });
});
