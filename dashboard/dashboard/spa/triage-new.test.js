/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import TriageNew from './triage-new.js';
import findElements from './find-elements.js';
import {CHAIN, ENSURE, UPDATE} from './simple-redux.js';
import {STORE} from './element-base.js';
import {afterRender, timeout} from './utils.js';
import {assert} from 'chai';

suite('triage-new', function() {
  async function fixture(options) {
    const tn = document.createElement('triage-new');
    tn.statePath = 'test';
    await STORE.dispatch(CHAIN(
        ENSURE('test'),
        UPDATE('test', TriageNew.buildState(options))));
    document.body.appendChild(tn);
    await afterRender();
    return tn;
  }

  test('summarize', async function() {
    assert.strictEqual('', TriageNew.summarize());
    assert.strictEqual('10% regression in aaa at 123', TriageNew.summarize([
      {
        percentDeltaValue: 0.1,
        startRevision: 123,
        endRevision: 123,
        measurement: 'aaa',
      },
    ]));
    const expected = '10%-20% regression in aaa,bbb at 123:234';
    assert.strictEqual(expected, TriageNew.summarize([
      {
        percentDeltaValue: 0.1,
        startRevision: 123,
        endRevision: 123,
        measurement: 'aaa',
      },
      {
        percentDeltaValue: 0.2,
        startRevision: 234,
        endRevision: 234,
        measurement: 'bbb',
      },
    ]));
  });

  test('collectAlertProperties', async function() {
    const expected = [
      {name: 'aaa', isEnabled: true},
      {name: 'bbb', isEnabled: true},
      {name: 'ccc', isEnabled: true},
      {name: 'Pri-2', isEnabled: true},
      {name: 'Type-Bug-Regression', isEnabled: true},
    ];
    const actual = TriageNew.collectAlertProperties([
      {bugLabels: ['aaa', 'bbb']},
      {bugLabels: ['aaa', 'ccc']},
    ], 'bugLabels');
    assert.deepEqual(expected, actual);
  });

  test('edit', async function() {
    const tn = await fixture({
      isOpen: true,
      alerts: [
        {
          bugComponents: ['component'],
          bugLabels: ['label'],
          percentDeltaValue: 0.1,
          startRevision: 10,
          endRevision: 20,
          measurement: 'measurement',
        },
      ],
    });

    tn.$.summary.value = 'summary';
    tn.$.summary.dispatchEvent(new CustomEvent('change'));
    await afterRender();
    assert.strictEqual('summary', tn.summary);

    tn.$.description.value = 'description';
    tn.$.description.dispatchEvent(new CustomEvent('keyup'));
    await afterRender();
    assert.strictEqual('description', tn.description);

    assert.isTrue(tn.labels[0].isEnabled);
    findElements(tn, e =>
      e.matches('cp-checkbox') && /label/.test(e.textContent))[0].click();
    await afterRender();
    assert.isFalse(tn.labels[0].isEnabled);

    assert.isTrue(tn.components[0].isEnabled);
    findElements(tn, e =>
      e.matches('cp-checkbox') && /component/.test(e.textContent))[0].click();
    await afterRender();
    assert.isFalse(tn.components[0].isEnabled);

    tn.$.owner.value = 'owner';
    tn.$.owner.dispatchEvent(new CustomEvent('change'));
    await afterRender();
    assert.strictEqual('owner', tn.owner);

    tn.$.cc.value = 'cc';
    tn.$.cc.dispatchEvent(new CustomEvent('change'));
    await afterRender();
    assert.strictEqual('cc', tn.cc);

    let submitEvent;
    tn.addEventListener('submit', e => {
      submitEvent = e;
    });
    tn.$.submit.click();
    await afterRender();
    assert.isDefined(submitEvent);
    assert.isFalse(tn.isOpen);

    STORE.dispatch(UPDATE(tn.statePath, {isOpen: true}));
    await afterRender();
    tn.dispatchEvent(new CustomEvent('blur'));
    await afterRender();
    assert.isFalse(tn.isOpen);

    STORE.dispatch(UPDATE(tn.statePath, {isOpen: true}));
    await afterRender();
    tn.onKeyup_({key: 'Escape'});
    await afterRender();
    assert.isFalse(tn.isOpen);
  });
});
