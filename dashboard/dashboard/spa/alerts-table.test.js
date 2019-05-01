/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import {assert} from 'chai';
import AlertsTable from './alerts-table.js';
import findElements from './find-elements.js';
import {ENSURE, UPDATE} from './simple-redux.js';
import {afterRender} from './utils.js';

suite('alerts-table', function() {
  async function fixture(options = {}) {
    const table = document.createElement('alerts-table');
    table.statePath = 'test';
    await table.dispatch(ENSURE('test'));
    await table.dispatch(UPDATE('test', AlertsTable.buildState(options)));
    document.body.appendChild(table);
    await afterRender();
    return table;
  }

  teardown(() => {
    for (const child of document.body.children) {
      if (!child.matches('alerts-table')) continue;
      document.body.removeChild(child);
    }
  });

  test('placeholder', async function() {
    const table = await fixture();
    const baseTable = findElements(table, e => e.matches('table'))[0];
    assert.strictEqual('rgb(128, 128, 128)', getComputedStyle(
        baseTable).color);
    const dashes = findElements(table, e =>
      e.innerText && e.innerText.trim() === AlertsTable.DASHES);
    assert.lengthOf(dashes, 35);
  });

  test('allTriaged newAlerts', async function() {
    const table = await fixture({
      alertGroups: [
        {
          isSelected: false,
          triaged: {
            count: 2,
            isExpanded: false,
          },
          alerts: [
            {
              bugId: -1,
              revisions: '123-456',
              testSuite: 'test suite',
              measurement: 'aaa',
              master: 'master',
              bot: 'bot',
              testCase: 'test case',
              deltaValue: -1,
              deltaUnit: tr.b.Unit.byName.countDelta_biggerIsBetter,
              percentDeltaValue: -1,
              percentDeltaUnit:
                tr.b.Unit.byName.normalizedPercentageDelta_biggerIsBetter,
            },
            {
              bugId: -1,
              revisions: '123-456',
              testSuite: 'test suite',
              measurement: 'bbb',
              master: 'master',
              bot: 'bot',
              testCase: 'test case',
              deltaValue: -1,
              deltaUnit: tr.b.Unit.byName.countDelta_biggerIsBetter,
              percentDeltaValue: -1,
              percentDeltaUnit:
                tr.b.Unit.byName.normalizedPercentageDelta_biggerIsBetter,
            },
          ],
        },
      ],
    });
    assert.isDefined(findElements(table, e =>
      e.matches('iron-icon[icon="cp-big:cat"]'))[0]);
  });

  test('allTriaged showingTriaged', async function() {
    const table = await fixture({
      showingTriaged: true,
      alertGroups: [],
    });
    assert.isDefined(findElements(table,
        e => e.matches('iron-icon[icon="cp-big:cat"]'))[0]);
  });

  test('sort', async function() {
    const table = await fixture({
      alertGroups: [
        {
          isSelected: false,
          triaged: {
            count: 0,
            isExpanded: false,
          },
          alerts: [
            {
              bugId: '',
              revisions: '123-456',
              testSuite: 'test suite',
              measurement: 'ccc',
              master: 'master',
              bot: 'bot',
              testCase: 'test case',
              deltaValue: -1,
              deltaUnit: tr.b.Unit.byName.countDelta_biggerIsBetter,
              percentDeltaValue: -1,
              percentDeltaUnit:
                tr.b.Unit.byName.normalizedPercentageDelta_biggerIsBetter,
            },
          ],
        },
        {
          isSelected: false,
          triaged: {
            count: 0,
            isExpanded: false,
          },
          alerts: [
            {
              bugId: '',
              revisions: '123-456',
              testSuite: 'test suite',
              measurement: 'aaa',
              master: 'master',
              bot: 'bot',
              testCase: 'test case',
              deltaValue: -1,
              deltaUnit: tr.b.Unit.byName.countDelta_biggerIsBetter,
              percentDeltaValue: -1,
              percentDeltaUnit:
                tr.b.Unit.byName.normalizedPercentageDelta_biggerIsBetter,
            },
          ],
        },
        {
          isSelected: false,
          triaged: {
            count: 0,
            isExpanded: false,
          },
          alerts: [
            {
              bugId: '',
              revisions: '123-456',
              testSuite: 'test suite',
              measurement: 'bbb',
              master: 'master',
              bot: 'bot',
              testCase: 'test case',
              deltaValue: -1,
              deltaUnit: tr.b.Unit.byName.countDelta_biggerIsBetter,
              percentDeltaValue: -1,
              percentDeltaUnit:
                tr.b.Unit.byName.normalizedPercentageDelta_biggerIsBetter,
            },
          ],
        },
      ],
    });

    const measurementColumn = findElements(table, e =>
      e.matches('column-head[name="measurement"]'))[0];
    measurementColumn.click();
    await afterRender();
    let state = table.getState().test;
    assert.strictEqual('aaa', state.alertGroups[0].alerts[0].measurement);
    assert.strictEqual('bbb', state.alertGroups[1].alerts[0].measurement);
    assert.strictEqual('ccc', state.alertGroups[2].alerts[0].measurement);

    measurementColumn.click();
    await afterRender();
    state = table.getState().test;
    assert.strictEqual('ccc', state.alertGroups[0].alerts[0].measurement);
    assert.strictEqual('bbb', state.alertGroups[1].alerts[0].measurement);
    assert.strictEqual('aaa', state.alertGroups[2].alerts[0].measurement);
  });

  test('shouldDisplayAlert', async function() {
    assert.isTrue(AlertsTable.shouldDisplayAlert(
        true, false, {}, -1, false));
    assert.isTrue(AlertsTable.shouldDisplayAlert(
        false, true, {isExpanded: true}, -1, false));
    assert.isTrue(AlertsTable.shouldDisplayAlert(
        false, true, {isExpanded: false}, 0, false));
    assert.isFalse(AlertsTable.shouldDisplayAlert(
        false, false, {alerts: []}, 0, false));
    assert.isTrue(AlertsTable.shouldDisplayAlert(
        false, false, {isExpanded: true, alerts: [{}]}, 0, false));
    assert.isFalse(AlertsTable.shouldDisplayAlert(false, false, {
      isExpanded: true,
      alerts: [
        {bugId: 42},
        {},
      ],
    }, 0, false));
    assert.isTrue(AlertsTable.shouldDisplayAlert(false, false, {
      isExpanded: true,
      alerts: [
        {bugId: 42},
        {},
      ],
    }, 1, false));
    assert.isFalse(AlertsTable.shouldDisplayAlert(
        false, false, {alerts: [{bugId: 42}]}, 0, false));
    assert.isTrue(AlertsTable.shouldDisplayAlert(
        false, false, {alerts: [{bugId: 42}]}, 0, true));
    assert.isFalse(AlertsTable.shouldDisplayAlert(false, false, {
      alerts: [
        {bugId: 42},
        {},
      ],
    }, 0, false));
    assert.isTrue(AlertsTable.shouldDisplayAlert(false, false, {
      alerts: [
        {bugId: 42},
        {},
      ],
    }, 1, false));
  });

  test('shouldDisplayExpandGroupButton', async function() {
    assert.isTrue(AlertsTable.shouldDisplayExpandGroupButton(
        {alerts: [{}, {}]}, 0, true));
    assert.isFalse(AlertsTable.shouldDisplayExpandGroupButton(
        {alerts: [{}, {}]}, 1, true));
    assert.isFalse(AlertsTable.shouldDisplayExpandGroupButton(
        {alerts: [{}]}, 0, true));
    assert.isTrue(AlertsTable.shouldDisplayExpandGroupButton(
        {alerts: [{}, {}], triaged: {count: 0}}, 0, false));
    assert.isFalse(AlertsTable.shouldDisplayExpandGroupButton(
        {alerts: [{bugId: 42}, {}], triaged: {count: 1}}, 1, false));
    assert.isTrue(AlertsTable.shouldDisplayExpandGroupButton(
        {alerts: [{bugId: 42}, {}, {}], triaged: {count: 1}}, 1, false));
    assert.isFalse(AlertsTable.shouldDisplayExpandGroupButton(
        {alerts: [{bugId: 42}, {}, {}], triaged: {count: 1}}, 0, false));
  });

  test('shouldDisplayExpandTriagedButton', async function() {
    assert.isFalse(AlertsTable.shouldDisplayExpandTriagedButton(
        true, {triaged: {count: 1}}, 0));
    assert.isFalse(AlertsTable.shouldDisplayExpandTriagedButton(
        false, {triaged: {count: 0}}, 0));
    assert.isTrue(AlertsTable.shouldDisplayExpandTriagedButton(
        false, {triaged: {count: 1}, alerts: [
          {}, {bugId: 42},
        ]}, 0));
    assert.isTrue(AlertsTable.shouldDisplayExpandTriagedButton(
        false, {triaged: {count: 1}, alerts: [
          {bugId: 42}, {},
        ]}, 1));
  });

  test('shouldDisplaySelectedCount newAlerts', async function() {
    const table = await fixture({
      alertGroups: [
        {
          isSelected: false,
          triaged: {
            count: 0,
            isExpanded: false,
          },
          alerts: [
            {
              isSelected: true,
              bugId: -1,
              revisions: '123-456',
              testSuite: 'test suite',
              measurement: 'aaa',
              master: 'master',
              bot: 'bot',
              testCase: 'test case',
              deltaValue: -1,
              deltaUnit: tr.b.Unit.byName.countDelta_biggerIsBetter,
              percentDeltaValue: -1,
              percentDeltaUnit:
                tr.b.Unit.byName.normalizedPercentageDelta_biggerIsBetter,
            },
            {
              bugId: '',
              revisions: '123-456',
              testSuite: 'test suite',
              measurement: 'bbb',
              master: 'master',
              bot: 'bot',
              testCase: 'test case',
              deltaValue: -1,
              deltaUnit: tr.b.Unit.byName.countDelta_biggerIsBetter,
              percentDeltaValue: -1,
              percentDeltaUnit:
                tr.b.Unit.byName.normalizedPercentageDelta_biggerIsBetter,
            },
          ],
        },
      ],
    });

    const selectedCounts = findElements(table, e =>
      e.tagName === 'CP-CHECKBOX' && e.textContent.trim() === '1/2');
    assert.lengthOf(selectedCounts, 1);
    const row = selectedCounts[0].parentElement.parentElement;
    const tbody = row.parentElement;
    assert.strictEqual(row, tbody.children[1]);
  });

  test('shouldDisplaySelectedCount showingTriaged', async function() {
    const table = await fixture({
      showingTriaged: true,
      alertGroups: [
        {
          isSelected: false,
          triaged: {
            count: 0,
            isExpanded: false,
          },
          alerts: [
            {
              isSelected: true,
              bugId: -1,
              revisions: '123-456',
              testSuite: 'test suite',
              measurement: 'aaa',
              master: 'master',
              bot: 'bot',
              testCase: 'test case',
              deltaValue: -1,
              deltaUnit: tr.b.Unit.byName.countDelta_biggerIsBetter,
              percentDeltaValue: -1,
              percentDeltaUnit:
                tr.b.Unit.byName.normalizedPercentageDelta_biggerIsBetter,
            },
            {
              bugId: -1,
              revisions: '123-456',
              testSuite: 'test suite',
              measurement: 'bbb',
              master: 'master',
              bot: 'bot',
              testCase: 'test case',
              deltaValue: -1,
              deltaUnit: tr.b.Unit.byName.countDelta_biggerIsBetter,
              percentDeltaValue: -1,
              percentDeltaUnit:
                tr.b.Unit.byName.normalizedPercentageDelta_biggerIsBetter,
            },
          ],
        },
      ],
    });

    const selectedCounts = findElements(table, e =>
      e.tagName === 'CP-CHECKBOX' && e.textContent.trim() === '1/2');
    assert.lengthOf(selectedCounts, 1);
    const row = selectedCounts[0].parentElement.parentElement;
    const tbody = row.parentElement;
    assert.strictEqual(row, tbody.children[0]);
  });

  test('isAlertIgnored', async function() {
    const table = await fixture({
      showingTriaged: true,
      alertGroups: [
        {
          isSelected: false,
          triaged: {
            count: 0,
            isExpanded: false,
          },
          alerts: [
            {
              bugId: -1,
              revisions: '123-456',
              testSuite: 'test suite',
              measurement: 'measurement',
              master: 'master',
              bot: 'bot',
              testCase: 'test case',
              deltaValue: -1,
              deltaUnit: tr.b.Unit.byName.countDelta_biggerIsBetter,
              percentDeltaValue: -1,
              percentDeltaUnit:
                tr.b.Unit.byName.normalizedPercentageDelta_biggerIsBetter,
            },
          ],
        },
      ],
    });
    assert.isDefined(findElements(table, e =>
      e.tagName === 'TD' && e.textContent.trim() === 'ignored')[0]);
  });

  test('selectAlert single', async function() {
    const table = await fixture({
      alertGroups: [
        {
          triaged: {count: 0, isExpanded: false},
          alerts: [
            {
              bugId: '',
              revisions: '123-456',
              testSuite: 'test suite',
              measurement: 'measurement',
              master: 'master',
              bot: 'bot',
              testCase: 'test case',
              deltaValue: -1,
              deltaUnit: tr.b.Unit.byName.countDelta_biggerIsBetter,
              percentDeltaValue: -1,
              percentDeltaUnit:
                tr.b.Unit.byName.normalizedPercentageDelta_biggerIsBetter,
            },
          ],
        },
      ],
    });
    const tbody = findElements(table, e => e.matches('tbody'))[0];
    const checkbox = findElements(tbody, e => e.matches('cp-checkbox'))[0];
    checkbox.click();
    await afterRender();
    assert.isTrue(table.getState().test.alertGroups[0].alerts[0].isSelected);
  });

  test('selectAlert toggleAll', async function() {
    const table = await fixture({
      alertGroups: [
        {
          triaged: {count: 0, isExpanded: false},
          alerts: [
            {
              bugId: '',
              revisions: '123-456',
              testSuite: 'test suite',
              measurement: 'aaa',
              master: 'master',
              bot: 'bot',
              testCase: 'test case',
              deltaValue: -1,
              deltaUnit: tr.b.Unit.byName.countDelta_biggerIsBetter,
              percentDeltaValue: -1,
              percentDeltaUnit:
                tr.b.Unit.byName.normalizedPercentageDelta_biggerIsBetter,
            },
            {
              bugId: '',
              revisions: '123-456',
              testSuite: 'test suite',
              measurement: 'bbb',
              master: 'master',
              bot: 'bot',
              testCase: 'test case',
              deltaValue: -1,
              deltaUnit: tr.b.Unit.byName.countDelta_biggerIsBetter,
              percentDeltaValue: -1,
              percentDeltaUnit:
                tr.b.Unit.byName.normalizedPercentageDelta_biggerIsBetter,
            },
          ],
        },
      ],
    });
    const tbody = findElements(table, e => e.matches('tbody'))[0];
    const checkbox = findElements(tbody, e => e.matches('cp-checkbox'))[0];
    checkbox.click();
    await afterRender();
    assert.isTrue(table.getState().test.alertGroups[0].alerts[0].isSelected);
    assert.isTrue(table.getState().test.alertGroups[0].alerts[1].isSelected);
  });

  test('selectAlert shiftKey', async function() {
    const table = await fixture({
      alertGroups: [
        {
          isExpanded: true,
          triaged: {count: 0, isExpanded: false},
          alerts: [
            {
              key: 'a',
              isSelected: false,
              bugId: '',
              revisions: '123-456',
              testSuite: 'test suite',
              measurement: 'aaa',
              master: 'master',
              bot: 'bot',
              testCase: 'test case',
              deltaValue: -1,
              deltaUnit: tr.b.Unit.byName.countDelta_biggerIsBetter,
              percentDeltaValue: -1,
              percentDeltaUnit:
                tr.b.Unit.byName.normalizedPercentageDelta_biggerIsBetter,
            },
            {
              key: 'b',
              isSelected: false,
              bugId: '',
              revisions: '123-456',
              testSuite: 'test suite',
              measurement: 'bbb',
              master: 'master',
              bot: 'bot',
              testCase: 'test case',
              deltaValue: -1,
              deltaUnit: tr.b.Unit.byName.countDelta_biggerIsBetter,
              percentDeltaValue: -1,
              percentDeltaUnit:
                tr.b.Unit.byName.normalizedPercentageDelta_biggerIsBetter,
            },
            {
              key: 'c',
              isSelected: false,
              bugId: '',
              revisions: '123-456',
              testSuite: 'test suite',
              measurement: 'ccc',
              master: 'master',
              bot: 'bot',
              testCase: 'test case',
              deltaValue: -1,
              deltaUnit: tr.b.Unit.byName.countDelta_biggerIsBetter,
              percentDeltaValue: -1,
              percentDeltaUnit:
                tr.b.Unit.byName.normalizedPercentageDelta_biggerIsBetter,
            },
            {
              key: 'd',
              isSelected: false,
              bugId: '',
              revisions: '123-456',
              testSuite: 'test suite',
              measurement: 'ddd',
              master: 'master',
              bot: 'bot',
              testCase: 'test case',
              deltaValue: -1,
              deltaUnit: tr.b.Unit.byName.countDelta_biggerIsBetter,
              percentDeltaValue: -1,
              percentDeltaUnit:
                tr.b.Unit.byName.normalizedPercentageDelta_biggerIsBetter,
            },
            {
              key: 'e',
              isSelected: false,
              bugId: '',
              revisions: '123-456',
              testSuite: 'test suite',
              measurement: 'eee',
              master: 'master',
              bot: 'bot',
              testCase: 'test case',
              deltaValue: -1,
              deltaUnit: tr.b.Unit.byName.countDelta_biggerIsBetter,
              percentDeltaValue: -1,
              percentDeltaUnit:
                tr.b.Unit.byName.normalizedPercentageDelta_biggerIsBetter,
            },
          ],
        },
      ],
    });
    const checkboxes = findElements(
        findElements(table, e => e.matches('tbody'))[0],
        e => e.matches('cp-checkbox'));
    checkboxes[1].click();
    checkboxes[3].$.native.dispatchEvent(new CustomEvent('change', {
      detail: {shiftKey: true},
    }));
    await afterRender();
    assert.isFalse(table.getState().test.alertGroups[0].alerts[0].isSelected);
    assert.isTrue(table.getState().test.alertGroups[0].alerts[1].isSelected);
    assert.isTrue(table.getState().test.alertGroups[0].alerts[2].isSelected);
    assert.isTrue(table.getState().test.alertGroups[0].alerts[3].isSelected);
    assert.isFalse(table.getState().test.alertGroups[0].alerts[4].isSelected);
  });
});
