/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import AlertsControls from './alerts-controls.js';
import ReportNamesRequest from './report-names-request.js';
import SheriffsRequest from './sheriffs-request.js';
import findElements from './find-elements.js';
import {CHAIN, ENSURE, TOGGLE, UPDATE} from './simple-redux.js';
import {STORE} from './element-base.js';
import {afterRender, timeout} from './utils.js';
import {assert} from 'chai';

suite('alerts-controls', function() {
  let originalFetch;

  setup(() => {
    originalFetch = window.fetch;
    window.fetch = async(url, options) => {
      return {
        ok: true,
        async json() {
          if (url === ReportNamesRequest.URL) {
            return [{name: 'aaa', id: 42, modified: new Date()}];
          }
          if (url === SheriffsRequest.URL) {
            return ['ccc', 'ddd'];
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
      if (!child.matches('alerts-controls')) continue;
      document.body.removeChild(child);
    }
    window.fetch = originalFetch;
    localStorage.removeItem('recentlyModifiedBugs');
  });

  test('connected', async function() {
    const controls = document.createElement('alerts-controls');
    controls.statePath = 'test';
    STORE.dispatch(CHAIN(
        ENSURE('test'),
        UPDATE('test', AlertsControls.buildState({}))));
    document.body.appendChild(controls);
    await afterRender();
    await afterRender();
    assert.isDefined(findElements(controls, e => /aaa/.test(e.textContent))[0]);
    assert.isDefined(findElements(controls, e =>
      e.tagName === 'A' && e.href === 'http://crbug.com/42' &&
      e.textContent.trim() === '42')[0]);
    assert.isDefined(findElements(controls, e => /bbb/.test(e.textContent))[0]);
    assert.isDefined(findElements(controls, e => /ccc/.test(e.textContent))[0]);
    assert.isDefined(findElements(controls, e => /ddd/.test(e.textContent))[0]);
  });

  test('change', async function() {
    const controls = document.createElement('alerts-controls');
    controls.statePath = 'test';
    STORE.dispatch(CHAIN(
        ENSURE('test'),
        UPDATE('test', AlertsControls.buildState({}))));
    document.body.appendChild(controls);
    let sources;
    controls.addEventListener('sources', e => {
      sources = e.detail.sources;
    });
    await afterRender();

    findElements(controls, e =>
      e.matches('cp-checkbox') && /ccc/.test(e.textContent))[0].click();
    await afterRender();
    assert.lengthOf(sources, 1);
    assert.strictEqual('ccc', sources[0].sheriff);
    sources = [];

    const minRevision = findElements(controls, e =>
      e.id === 'min-revision')[0];
    minRevision.value = '10';
    minRevision.dispatchEvent(new CustomEvent('keyup'));
    await timeout(AlertsControls.TYPING_DEBOUNCE_MS + 10);
    assert.lengthOf(sources, 1);
    assert.strictEqual('ccc', sources[0].sheriff);
    assert.strictEqual(10, sources[0].min_end_revision);
    sources = [];

    const maxRevision = findElements(controls, e =>
      e.id === 'max-revision')[0];
    maxRevision.value = '20';
    maxRevision.dispatchEvent(new CustomEvent('keyup'));
    await timeout(AlertsControls.TYPING_DEBOUNCE_MS + 10);
    assert.lengthOf(sources, 1);
    assert.strictEqual('ccc', sources[0].sheriff);
    assert.strictEqual(10, sources[0].min_end_revision);
    assert.strictEqual(20, sources[0].max_start_revision);
    assert.isFalse(sources[0].is_improvement);
    sources = [];

    findElements(controls, e => e.matches('#improvements'))[0].click();
    await timeout(AlertsControls.TYPING_DEBOUNCE_MS + 10);
    assert.strictEqual('ccc', sources[0].sheriff);
    assert.isTrue(sources[0].is_improvement);
    assert.strictEqual(10, sources[0].min_end_revision);
    assert.strictEqual(20, sources[0].max_start_revision);

    findElements(controls, e =>
      e.matches('cp-checkbox') && /ddd/.test(e.textContent))[0].click();
    await afterRender();
    assert.lengthOf(sources, 2);
    assert.strictEqual('ccc', sources[0].sheriff);
    assert.strictEqual(10, sources[0].min_end_revision);
    assert.strictEqual(20, sources[0].max_start_revision);
    assert.strictEqual('ddd', sources[1].sheriff);
    assert.strictEqual(10, sources[1].min_end_revision);
    assert.strictEqual(20, sources[1].max_start_revision);

    findElements(controls, e =>
      e.matches('cp-checkbox') && /ccc/.test(e.textContent))[0].click();
    findElements(controls, e =>
      e.matches('cp-checkbox') && /ddd/.test(e.textContent))[0].click();
    findElements(controls, e =>
      e.matches('cp-checkbox') && /aaa/.test(e.textContent))[0].click();
    await afterRender();
    assert.lengthOf(sources, 1);
    assert.strictEqual(42, sources[0].report);
    assert.strictEqual(10, sources[0].min_end_revision);
    assert.strictEqual(20, sources[0].max_start_revision);

    findElements(controls, e =>
      e.matches('cp-checkbox') && /aaa/.test(e.textContent))[0].click();
    findElements(controls, e => e.matches('#bug'))[0].dispatchEvent(
        new CustomEvent('input-keyup', {detail: {value: '123'}}));
    await afterRender();
    findElements(controls, e =>
      e.matches('cp-checkbox') && /123/.test(e.textContent))[0].click();
    await afterRender();
    assert.lengthOf(sources, 1);
    assert.strictEqual('123', sources[0].bug_id);
    assert.strictEqual(10, sources[0].min_end_revision);
    assert.strictEqual(20, sources[0].max_start_revision);
  });
});
