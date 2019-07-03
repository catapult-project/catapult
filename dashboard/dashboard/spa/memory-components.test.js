/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import {MemoryComponents} from './memory-components.js';
import {STORE} from './element-base.js';
import {UPDATE} from './simple-redux.js';
import {afterRender} from './utils.js';
import {assert} from 'chai';
import {findElements} from './find-elements.js';

suite('memory-components', function() {
  const OPTIONS = {
    options: [
      // See getNumericName in memoryMetric:
      // /tracing/tracing/metrics/system_health/memory_metric.html
      'memory:chrome:aaa_process:reported_bbb:ccc:ddd_size',
      'memory:chrome:aaa_process:reported_bbb:ccc:eee_size',
      'memory:chrome:aaa_process:reported_bbb:fff:ddd_size',
      'memory:chrome:aaa_process:reported_bbb:fff:eee_size',
      'memory:chrome:aaa_process:reported_ggg:ccc:ddd_size',
      'memory:chrome:aaa_process:reported_ggg:ccc:eee_size',
      'memory:chrome:aaa_process:reported_ggg:fff:ddd_size',
      'memory:chrome:aaa_process:reported_ggg:fff:eee_size',
      'memory:chrome:hhh_process:reported_bbb:ccc:ddd_size',
      'memory:chrome:hhh_process:reported_bbb:ccc:eee_size',
      'memory:chrome:hhh_process:reported_bbb:fff:ddd_size',
      'memory:chrome:hhh_process:reported_bbb:fff:eee_size',
      'memory:chrome:hhh_process:reported_ggg:ccc:ddd_size',
      'memory:chrome:hhh_process:reported_ggg:ccc:eee_size',
      'memory:chrome:hhh_process:reported_ggg:fff:ddd_size',
      'memory:chrome:hhh_process:reported_ggg:fff:eee_size',
      'memory:webview:aaa_process:reported_bbb:ccc:ddd_size',
      'memory:webview:aaa_process:reported_bbb:ccc:eee_size',
      'memory:webview:aaa_process:reported_bbb:fff:ddd_size',
      'memory:webview:aaa_process:reported_bbb:fff:eee_size',
      'memory:webview:aaa_process:reported_ggg:ccc:ddd_size',
      'memory:webview:aaa_process:reported_ggg:ccc:eee_size',
      'memory:webview:aaa_process:reported_ggg:fff:ddd_size',
      'memory:webview:aaa_process:reported_ggg:fff:eee_size',
      'memory:webview:hhh_process:reported_bbb:ccc:ddd_size',
      'memory:webview:hhh_process:reported_bbb:ccc:eee_size',
      'memory:webview:hhh_process:reported_bbb:fff:ddd_size',
      'memory:webview:hhh_process:reported_bbb:fff:eee_size',
      'memory:webview:hhh_process:reported_ggg:ccc:ddd_size',
      'memory:webview:hhh_process:reported_ggg:ccc:eee_size',
      'memory:webview:hhh_process:reported_ggg:fff:ddd_size',
      'memory:webview:hhh_process:reported_ggg:fff:eee_size',
    ],
    selectedOptions: [
      'memory:chrome:aaa_process:reported_bbb:ccc:ddd_size',
    ],
  };

  teardown(() => {
    for (const child of document.body.children) {
      if (!child.matches('memory-components')) continue;
      document.body.removeChild(child);
    }
  });

  test('select', async function() {
    const memoryComponents = document.createElement('memory-components');
    memoryComponents.statePath = 'test';
    await STORE.dispatch(UPDATE('', {
      test: MemoryComponents.buildState(OPTIONS),
    }));
    document.body.appendChild(memoryComponents);
    await afterRender();
    await afterRender();
    let state = STORE.getState().test;
    assert.lengthOf(state.columns, 5);
    assert.strictEqual('chrome', state.columns[0].options[0].value);
    assert.strictEqual('aaa', state.columns[1].options[0].value);
    assert.strictEqual('bbb', state.columns[2].options[0].value);
    assert.strictEqual('ccc', state.columns[3].options[0].value);
    assert.strictEqual('ddd', state.columns[4].options[0].value);
    assert.strictEqual('webview', state.columns[0].options[1].value);
    assert.strictEqual('hhh', state.columns[1].options[1].value);
    assert.strictEqual('ggg', state.columns[2].options[1].value);
    assert.strictEqual('fff', state.columns[3].options[1].value);
    assert.strictEqual('eee', state.columns[4].options[1].value);
    assert.deepEqual(['chrome'], state.columns[0].selectedOptions);
    assert.deepEqual(['aaa'], state.columns[1].selectedOptions);
    assert.deepEqual(['bbb'], state.columns[2].selectedOptions);
    assert.deepEqual(['ccc'], state.columns[3].selectedOptions);
    assert.deepEqual(['ddd'], state.columns[4].selectedOptions);

    const ggg = findElements(memoryComponents, e =>
      e.matches('chops-checkbox') && /ggg/.test(e.textContent))[0];
    ggg.click();
    await afterRender();
    state = STORE.getState().test;
    assert.include(state.selectedOptions,
        'memory:chrome:aaa_process:reported_bbb:ccc:ddd_size');
    assert.include(state.selectedOptions,
        'memory:chrome:aaa_process:reported_ggg:ccc:ddd_size');
    assert.notInclude(state.selectedOptions,
        'memory:chrome:aaa_process:reported_bbb:ccc:eee_size');
    assert.notInclude(state.selectedOptions,
        'memory:chrome:aaa_process:reported_ggg:ccc:eee_size');

    const eee = findElements(memoryComponents, e =>
      e.matches('chops-checkbox') && /eee/.test(e.textContent))[0];
    eee.click();
    await afterRender();
    state = STORE.getState().test;
    assert.include(state.selectedOptions,
        'memory:chrome:aaa_process:reported_bbb:ccc:ddd_size');
    assert.include(state.selectedOptions,
        'memory:chrome:aaa_process:reported_ggg:ccc:ddd_size');
    assert.include(state.selectedOptions,
        'memory:chrome:aaa_process:reported_bbb:ccc:eee_size');
    assert.include(state.selectedOptions,
        'memory:chrome:aaa_process:reported_ggg:ccc:eee_size');

    const ddd = findElements(memoryComponents, e =>
      e.matches('chops-checkbox') && /ddd/.test(e.textContent))[0];
    ddd.click();
    await afterRender();
    state = STORE.getState().test;
    assert.notInclude(state.selectedOptions,
        'memory:chrome:aaa_process:reported_bbb:ccc:ddd_size');
    assert.notInclude(state.selectedOptions,
        'memory:chrome:aaa_process:reported_ggg:ccc:ddd_size');
    assert.include(state.selectedOptions,
        'memory:chrome:aaa_process:reported_bbb:ccc:eee_size');
    assert.include(state.selectedOptions,
        'memory:chrome:aaa_process:reported_ggg:ccc:eee_size');

    const bbb = findElements(memoryComponents, e =>
      e.matches('chops-checkbox') && /bbb/.test(e.textContent))[0];
    bbb.click();
    await afterRender();
    state = STORE.getState().test;
    assert.notInclude(state.selectedOptions,
        'memory:chrome:aaa_process:reported_bbb:ccc:ddd_size');
    assert.notInclude(state.selectedOptions,
        'memory:chrome:aaa_process:reported_ggg:ccc:ddd_size');
    assert.notInclude(state.selectedOptions,
        'memory:chrome:aaa_process:reported_bbb:ccc:eee_size');
    assert.include(state.selectedOptions,
        'memory:chrome:aaa_process:reported_ggg:ccc:eee_size');
  });
});
