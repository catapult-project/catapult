/* Copyright 2019 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import {BisectDialog} from './bisect-dialog.js';
import {CHAIN, ENSURE, UPDATE} from './simple-redux.js';
import {NewPinpointRequest} from './new-pinpoint-request.js';
import {STORE} from './element-base.js';
import {afterRender, timeout, setDebugForTesting} from './utils.js';
import {assert} from 'chai';

suite('bisect-dialog', function() {
  async function fixture() {
    const bd = document.createElement('bisect-dialog');
    bd.statePath = 'test';
    STORE.dispatch(CHAIN(
        ENSURE('test'),
        UPDATE('test', BisectDialog.buildState({
          alertKeys: ['alert key'],
          budId: 'bug',
          suite: 'suite',
          measurement: 'measure',
          bot: 'master:bot',
          case: 'test case',
          statistic: 'avg',
          startRevision: 10,
          endRevision: 20,
        }))));
    document.body.appendChild(bd);
    await afterRender();
    return bd;
  }

  let newPinpointBody;
  let originalFetch;
  setup(() => {
    setDebugForTesting(true);

    originalFetch = window.fetch;
    window.fetch = async(url, options) => {
      return {
        ok: true,
        async json() {
          if (url === NewPinpointRequest.URL) {
            newPinpointBody = new Map(options.body);
            return {jobId: 'decafbad'};
          }
        },
      };
    };
  });

  teardown(() => {
    for (const child of document.body.children) {
      if (!child.matches('bisect-dialog')) continue;
      document.body.removeChild(child);
    }
    window.fetch = originalFetch;
  });

  test('submit', async function() {
    const bd = await fixture();
    bd.shadowRoot.querySelector('#open').click();
    await afterRender();

    bd.shadowRoot.querySelector('#patch').dispatchEvent(
        new CustomEvent('change', {detail: {value: 'patch'}}));
    bd.shadowRoot.querySelector('#start_revision').dispatchEvent(
        new CustomEvent('change', {detail: {value: '5'}}));
    bd.shadowRoot.querySelector('#end_revision').dispatchEvent(
        new CustomEvent('change', {detail: {value: '25'}}));
    bd.shadowRoot.querySelector('#bug_id').dispatchEvent(
        new CustomEvent('change', {detail: {value: '321'}}));
    bd.shadowRoot.querySelector('#mode').dispatchEvent(
        new CustomEvent('selected-changed', {detail: {value: 'functional'}}));

    bd.shadowRoot.querySelector('#start').click();
    await afterRender();

    assert.strictEqual('5', newPinpointBody.get('start_commit'));
    assert.strictEqual('25', newPinpointBody.get('end_commit'));
    assert.strictEqual('["alert key"]', newPinpointBody.get('alerts'));
    assert.strictEqual('master:bot', newPinpointBody.get('bot'));
    assert.strictEqual('measure', newPinpointBody.get('measurement'));
    assert.strictEqual('patch', newPinpointBody.get('pin'));
    assert.strictEqual('functional', newPinpointBody.get('bisect_mode'));
    assert.strictEqual('suite', newPinpointBody.get('suite'));
    assert.strictEqual('test case', newPinpointBody.get('case'));
    assert.strictEqual('321', newPinpointBody.get('bug_id'));
  });
});
