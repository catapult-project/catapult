/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import ChartBase from './chart-base.js';
import findElements from './find-elements.js';
import {ENSURE, UPDATE} from './simple-redux.js';
import {STORE} from './element-base.js';
import {afterRender, animationFrame} from './utils.js';
import {assert} from 'chai';

suite('chart-base', function() {
  setup(() => {
    // Mocha sets min-width: 900px inside #subsuites, but only 500px outside it,
    // which makes it difficult to see the chart in 'lines'. Reset those
    // min-widths so that the chart can expand to an appropriate size.
    document.body.style.margin = 0;
    document.body.style.minWidth = 0;
    document.documentElement.style.minWidth = 0;
  });

  teardown(() => {
    for (const child of document.body.children) {
      if (!child.matches('chart-base')) continue;
      document.body.removeChild(child);
    }
  });

  test('mouse-leave-main', async function() {
    const chart = document.createElement('chart-base');
    chart.style.maxWidth = '550px';
    chart.statePath = 'test';
    await STORE.dispatch(ENSURE('test'));
    document.body.appendChild(chart);
    await STORE.dispatch(UPDATE('test', ChartBase.buildState({
      showTooltip: true,
      lines: [
        {
          path: 'M0,0 L100,100',
          color: 'red',
          strokeWidth: 1,
          shadePoints: '0,50 50,100 100,50',
          shadeFill: 'hsla(0, 50%, 50%, 0.5)',
          data: [
            {xPct: 0, yPct: 0},
            {xPct: 100, yPct: 100},
          ],
        },
      ],
    })));
    chart.$.main.style.setProperty('--mouse', 'inside');
    let mouseLeftEvents = 0;
    chart.addEventListener('mouse-leave-main', e => {
      ++mouseLeftEvents;
    });
    let getTooltipEvents = 0;
    chart.addEventListener('get-tooltip', e => {
      ++getTooltipEvents;
    });

    // onMouseMoveMain_ debounces after an animationFrame, so wait for 2 frames
    // to make sure the debounce happens.

    const mouseEvent = new CustomEvent('mousemove');
    mouseEvent.x = 0;
    mouseEvent.y = 0;
    chart.$.main.dispatchEvent(mouseEvent);
    assert.strictEqual(0, mouseLeftEvents);
    assert.strictEqual(0, getTooltipEvents);
    await animationFrame();
    await animationFrame();
    assert.strictEqual(0, mouseLeftEvents);
    assert.strictEqual(1, getTooltipEvents);

    mouseEvent.x = 500;
    mouseEvent.y = 500;
    chart.$.main.dispatchEvent(mouseEvent);
    chart.$.main.dispatchEvent(mouseEvent);
    chart.$.main.dispatchEvent(mouseEvent);
    assert.strictEqual(0, mouseLeftEvents);
    assert.strictEqual(1, getTooltipEvents);
    await animationFrame();
    await animationFrame();
    assert.strictEqual(0, mouseLeftEvents);
    assert.strictEqual(2, getTooltipEvents);

    chart.$.main.style.setProperty('--mouse', 'outside');
    await animationFrame();
    await animationFrame();
    assert.strictEqual(1, mouseLeftEvents);
    assert.strictEqual(2, getTooltipEvents);
  });

  test('boldLine', async function() {
    const chart = document.createElement('chart-base');
    chart.statePath = 'test';
    await STORE.dispatch(ENSURE('test'));
    document.body.appendChild(chart);
    await STORE.dispatch(UPDATE('test', ChartBase.buildState({
      lines: [
        {
          path: 'M0,0 L100,100',
          color: 'red',
          strokeWidth: 1,
          shadePoints: '0,50 50,100 100,50',
          shadeFill: 'hsla(0, 50%, 50%, 0.5)',
          data: [
            {xPct: 50, yPct: 50, icon: 'cp:error', iconColor: 'blue'},
          ],
        },
        {
          path: 'M0,100 L100,0',
          color: 'green',
          strokeWidth: 1,
          shadePoints: '0,50 100,50 50,0',
          shadeFill: 'hsla(100, 50%, 50%, 0.5)',
        },
      ],
      xAxis: {
        brushes: [{xPct: '20%'}, {xPct: '80%'}],
        showTickLines: true,
        height: '20px',
        ticks: [
          {xPct: '10%', text: '10%'},
          {xPct: '50%', text: '50%'},
          {xPct: '90%', text: '90%'},
        ],
      },
      yAxis: {
        showTickLines: true,
        width: '50px',
        ticks: [
          {yPct: '10%', text: '10%'},
          {yPct: '50%', text: '50%'},
          {yPct: '90%', text: '90%'},
        ],
      },
      tooltip: {
        isVisible: true,
        color: 'purple',
        left: '50%',
        top: '50%',
        rows: [
          {name: 'left top', value: 'right top', color: 'red'},
          {name: 'center', colspan: 2, color: 'green'},
          {name: 'left bottom', value: 'right bottom', color: 'blue'},
        ],
      },
    })));
    await afterRender();

    STORE.dispatch({
      type: ChartBase.reducers.boldLine.name,
      statePath: 'test',
      lineIndex: 0,
    });
    await afterRender();
    // boldLine moves the selected line to the end of `lines` so it is drawn
    // over top of the other lines.
    assert.strictEqual(chart.lines[0].color, 'green');
    assert.strictEqual(chart.lines[1].color, 'red');
    assert.strictEqual(chart.lines[0].strokeWidth, 1);
    assert.strictEqual(chart.lines[1].strokeWidth, 2);

    STORE.dispatch({
      type: ChartBase.reducers.boldLine.name,
      statePath: 'test',
      lineIndex: 0,
    });
    await afterRender();
    assert.strictEqual(chart.lines[0].color, 'red');
    assert.strictEqual(chart.lines[1].color, 'green');
    assert.strictEqual(chart.lines[0].strokeWidth, 1);
    assert.strictEqual(chart.lines[1].strokeWidth, 2);

    STORE.dispatch({
      type: ChartBase.reducers.boldLine.name,
      statePath: 'test',
    });
    await afterRender();
    assert.strictEqual(chart.lines[0].strokeWidth, 1);
    assert.strictEqual(chart.lines[1].strokeWidth, 1);
  });

  test('lines', async function() {
    const chart = document.createElement('chart-base');
    chart.statePath = 'test';
    await STORE.dispatch(ENSURE('test'));
    document.body.appendChild(chart);
    await STORE.dispatch(UPDATE('test', ChartBase.buildState({
      lines: [
        {
          path: 'M0,0 L100,100',
          color: 'red',
          strokeWidth: 1,
          shadePoints: '0,50 50,100 100,50',
          shadeFill: 'hsla(0, 50%, 50%, 0.5)',
          data: [
            {xPct: 50, yPct: 50, icon: 'cp:error', iconColor: 'blue'},
          ],
        },
        {
          path: 'M0,100 L100,0',
          color: 'green',
          strokeWidth: 1,
          shadePoints: '0,50 100,50 50,0',
          shadeFill: 'hsla(100, 50%, 50%, 0.5)',
        },
      ],
      xAxis: {
        brushes: [{xPct: '20%'}, {xPct: '80%'}],
        showTickLines: true,
        height: '20px',
        ticks: [
          {xPct: '10%', text: '10%'},
          {xPct: '50%', text: '50%'},
          {xPct: '90%', text: '90%'},
        ],
      },
      yAxis: {
        showTickLines: true,
        width: '50px',
        ticks: [
          {yPct: '10%', text: '10%'},
          {yPct: '50%', text: '50%'},
          {yPct: '90%', text: '90%'},
        ],
      },
      tooltip: {
        isVisible: true,
        color: 'purple',
        left: '50%',
        top: '50%',
        rows: [
          {name: 'left top', value: 'right top', color: 'red'},
          {name: 'center', colspan: 2, color: 'green'},
          {name: 'left bottom', value: 'right bottom', color: 'blue'},
        ],
      },
    })));
    await afterRender();

    assert.strictEqual('50%', chart.$.tooltip.style.left);
    assert.strictEqual('50%', chart.$.tooltip.style.top);
    assert.strictEqual('purple',
        chart.$.tooltip.querySelector('table').style.borderColor);
    assert.strictEqual('flex', getComputedStyle(chart.$.tooltip).display);

    assert.isDefined(findElements(chart, e =>
      e.tagName === 'foreignObject' &&
      e.className.baseVal === 'icon' &&
      e.getAttribute('x') === '50%' &&
      e.getAttribute('y') === '50%')[0]);

    assert.isDefined(findElements(chart, e =>
      e.tagName === 'IRON-ICON' &&
      e.icon === 'cp:error' &&
      e.style.color === 'blue')[0]);

    assert.isDefined(findElements(chart, e =>
      e.tagName === 'polygon' &&
      e.getAttribute('points') === '0,50 50,100 100,50' &&
      e.getAttribute('fill') === 'hsla(0, 50%, 50%, 0.5)')[0]);
    assert.isDefined(findElements(chart, e =>
      e.tagName === 'polygon' &&
      e.getAttribute('points') === '0,50 100,50 50,0' &&
      e.getAttribute('fill') === 'hsla(100, 50%, 50%, 0.5)')[0]);

    assert.isDefined(findElements(chart, e =>
      e.tagName === 'path' &&
      e.getAttribute('d') === 'M0,0 L100,100' &&
      e.getAttribute('stroke') === 'red')[0]);
    assert.isDefined(findElements(chart, e =>
      e.tagName === 'path' &&
      e.getAttribute('d') === 'M0,100 L100,0' &&
      e.getAttribute('stroke') === 'green')[0]);

    assert.isDefined(findElements(chart, e =>
      e.tagName === 'text' &&
      e.getAttribute('y') === '10%' &&
      e.getAttribute('x') === '50px' &&
      e.textContent.trim() === '10%')[0]);
    assert.isDefined(findElements(chart, e =>
      e.tagName === 'text' &&
      e.getAttribute('y') === '50%' &&
      e.getAttribute('x') === '50px' &&
      e.textContent.trim() === '50%')[0]);
    assert.isDefined(findElements(chart, e =>
      e.tagName === 'text' &&
      e.getAttribute('y') === '90%' &&
      e.getAttribute('x') === '50px' &&
      e.textContent.trim() === '90%')[0]);

    assert.isDefined(findElements(chart, e =>
      e.tagName === 'text' &&
      e.getAttribute('y') === '100%' &&
      e.getAttribute('x') === '10%' &&
      e.textContent.trim() === '10%')[0]);
    assert.isDefined(findElements(chart, e =>
      e.tagName === 'text' &&
      e.getAttribute('y') === '100%' &&
      e.getAttribute('x') === '50%' &&
      e.textContent.trim() === '50%')[0]);
    assert.isDefined(findElements(chart, e =>
      e.tagName === 'text' &&
      e.getAttribute('y') === '100%' &&
      e.getAttribute('x') === '90%' &&
      e.textContent.trim() === '90%')[0]);

    assert.isDefined(findElements(chart, e =>
      e.tagName === 'rect' &&
      e.getAttribute('y') === '0' &&
      e.getAttribute('x') === '0%' &&
      e.getAttribute('height') === '100%' &&
      e.getAttribute('width') === '20%')[0]);
    assert.isDefined(findElements(chart, e =>
      e.tagName === 'rect' &&
      e.getAttribute('y') === '0' &&
      e.getAttribute('x') === '80%' &&
      e.getAttribute('height') === '100%' &&
      e.getAttribute('width') === '20%')[0]);

    assert.isDefined(findElements(chart, e =>
      e.tagName === 'line' &&
      e.getAttribute('x1') === '0' &&
      e.getAttribute('x2') === '100%' &&
      e.getAttribute('y1') === '10%' &&
      e.getAttribute('y2') === '10%')[0]);
    assert.isDefined(findElements(chart, e =>
      e.tagName === 'line' &&
      e.getAttribute('x1') === '0' &&
      e.getAttribute('x2') === '100%' &&
      e.getAttribute('y1') === '50%' &&
      e.getAttribute('y2') === '50%')[0]);
    assert.isDefined(findElements(chart, e =>
      e.tagName === 'line' &&
      e.getAttribute('x1') === '0' &&
      e.getAttribute('x2') === '100%' &&
      e.getAttribute('y1') === '90%' &&
      e.getAttribute('y2') === '90%')[0]);

    assert.isDefined(findElements(chart, e =>
      e.tagName === 'line' &&
      e.getAttribute('x1') === '10%' &&
      e.getAttribute('x2') === '10%' &&
      e.getAttribute('y1') === '0' &&
      e.getAttribute('y2') === '100%')[0]);
    assert.isDefined(findElements(chart, e =>
      e.tagName === 'line' &&
      e.getAttribute('x1') === '50%' &&
      e.getAttribute('x2') === '50%' &&
      e.getAttribute('y1') === '0' &&
      e.getAttribute('y2') === '100%')[0]);
    assert.isDefined(findElements(chart, e =>
      e.tagName === 'line' &&
      e.getAttribute('x1') === '90%' &&
      e.getAttribute('x2') === '90%' &&
      e.getAttribute('y1') === '0' &&
      e.getAttribute('y2') === '100%')[0]);
  });

  test('antiBrushes empty', async function() {
    assert.deepEqual([], ChartBase.antiBrushes());
    assert.deepEqual([], ChartBase.antiBrushes([]));
  });

  test('antiBrushes odd', async function() {
    assert.throws(() => ChartBase.antiBrushes([{}]));
    assert.throws(() => ChartBase.antiBrushes([{}, {}, {}]));
  });

  test('antiBrushes 0-100', async function() {
    assert.deepEqual([], ChartBase.antiBrushes([
      {xPct: 0}, {xPct: 100},
    ]));
  });

  test('antiBrushes 20-80', async function() {
    assert.deepEqual([
      {start: '0%', length: '20%'},
      {start: '80%', length: '20%'},
    ], ChartBase.antiBrushes([
      {xPct: 20}, {xPct: 80},
    ]));
  });

  test('antiBrushes 20-100', async function() {
    assert.deepEqual([
      {start: '0%', length: '20%'},
    ], ChartBase.antiBrushes([
      {xPct: 20}, {xPct: 100},
    ]));
  });

  test('antiBrushes 0-80', async function() {
    assert.deepEqual([{start: '80%', length: '20%'}], ChartBase.antiBrushes(
        [{xPct: 0}, {xPct: 80}]));
  });
});
