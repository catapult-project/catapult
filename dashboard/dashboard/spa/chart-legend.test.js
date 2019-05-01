/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import {assert} from 'chai';
import './chart-legend.js';
import findElements from './find-elements.js';
import {afterRender} from './utils.js';

suite('chart-legend', function() {
  teardown(() => {
    for (const child of document.body.children) {
      if (!child.matches('chart-legend')) continue;
      document.body.removeChild(child);
    }
  });

  test('recursive', async function() {
    const chartLegend = document.createElement('chart-legend');
    document.body.appendChild(chartLegend);
    chartLegend.items = [
      {label: 'A', color: 'red'},
      {label: 'B', children: [
        {label: 'C', color: 'green'},
        {label: 'D', children: [
          {label: 'E', color: 'blue'},
        ]},
      ]},
    ];
    await afterRender();

    const aLeaf = findElements(chartLegend, e => /A/.test(e.textContent))[0];
    const cLeaf = findElements(chartLegend, e => /C/.test(e.textContent))[0];
    const eLeaf = findElements(chartLegend, e => /E/.test(e.textContent))[0];
    assert.strictEqual('red', aLeaf.style.color);
    assert.strictEqual('green', cLeaf.style.color);
    assert.strictEqual('blue', eLeaf.style.color);

    const aRect = aLeaf.getBoundingClientRect();
    const cRect = cLeaf.getBoundingClientRect();
    const eRect = eLeaf.getBoundingClientRect();
    assert.isBelow(aRect.left, cRect.left);
    assert.isBelow(cRect.left, eRect.left);
  });

  test('leafClick', async function() {
    const chartLegend = document.createElement('chart-legend');
    document.body.appendChild(chartLegend);
    chartLegend.items = [
      {label: 'A', color: 'red'},
    ];
    let leafClickEvent;
    chartLegend.addEventListener('leaf-click', event => {
      leafClickEvent = event;
    });
    await afterRender();
    const leaf = chartLegend.shadowRoot.querySelector('.leaf');
    leaf.click();
    assert.strictEqual(chartLegend.items[0], leafClickEvent.detail);
  });
});
