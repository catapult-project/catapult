/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import {OptionGroup} from './option-group.js';
import {STORE} from './element-base.js';
import {UPDATE} from './simple-redux.js';
import {afterRender} from './utils.js';
import {assert} from 'chai';
import {findElements} from './find-elements.js';

suite('option-group', function() {
  async function fixture() {
    const optionGroup = document.createElement('option-group');
    optionGroup.statePath = 'test';
    optionGroup.rootStatePath = 'test';
    STORE.dispatch(UPDATE('', {
      test: OptionGroup.buildState(OPTIONS),
    }));
    document.body.appendChild(optionGroup);
    await afterRender();
    return optionGroup;
  }

  teardown(() => {
    for (const child of document.body.children) {
      if (!child.matches('option-group')) continue;
      document.body.removeChild(child);
    }
  });

  const OPTIONS = {
    options: new Set([
      'aaa',
      'bbb:ccc',
      'bbb:ddd',
      'bbb:ddd:eee',
      'bbb:ddd:fff',
    ]),
  };

  test('groupValues', async function() {
    const actual = OptionGroup.groupValues([
      'aaa',
      'bbb:ccc',
      'bbb:ddd',
      'bbb:ddd:eee',
      'bbb:ddd:fff',
    ]);
    const expected = [
      {
        'label': 'aaa',
        'value': 'aaa',
        'valueLowerCase': 'aaa',
      },
      {
        'isExpanded': false,
        'label': 'bbb',
        'options': [
          {
            'label': 'ccc',
            'value': 'bbb:ccc',
            'valueLowerCase': 'bbb:ccc',
          },
          {
            'isExpanded': false,
            'label': 'ddd',
            'options': [
              {
                'label': 'eee',
                'value': 'bbb:ddd:eee',
                'valueLowerCase': 'bbb:ddd:eee',
              },
              {
                'label': 'fff',
                'value': 'bbb:ddd:fff',
                'valueLowerCase': 'bbb:ddd:fff',
              },
            ],
            'value': 'bbb:ddd',
            'valueLowerCase': 'bbb:ddd',
          },
        ],
      },
    ];
    assert.deepEqual(actual, expected);
  });

  test('select simple', async function() {
    const optionGroup = await fixture();
    const checkbox = findElements(optionGroup, e =>
      e.matches('chops-checkbox') && /aaa/.test(e.textContent))[0];
    checkbox.click();
    await afterRender();
    assert.deepEqual(['aaa'], STORE.getState().test.selectedOptions);
  });

  test('deselect simple', async function() {
    const optionGroup = await fixture();
    STORE.dispatch(UPDATE('test', {selectedOptions: ['aaa']}));
    const checkbox = findElements(optionGroup, e =>
      e.matches('chops-checkbox') && /aaa/.test(e.textContent))[0];
    checkbox.click();
    await afterRender();
    assert.deepEqual([], STORE.getState().test.selectedOptions);
  });

  test('select all descendents', async function() {
    const optionGroup = await fixture();
    const bLeaf = findElements(optionGroup, e =>
      e.matches('chops-checkbox') && /bbb/.test(e.textContent))[0];
    bLeaf.click();
    await afterRender();
    assert.deepEqual(['bbb:ccc', 'bbb:ddd', 'bbb:ddd:eee', 'bbb:ddd:fff'],
        STORE.getState().test.selectedOptions);
  });

  test('deselect all descendents', async function() {
    const optionGroup = await fixture();
    STORE.dispatch(UPDATE('test', {selectedOptions: [
      'bbb:ccc', 'bbb:ddd', 'bbb:ddd:eee', 'bbb:ddd:fff',
    ]}));
    const checkbox = findElements(optionGroup, e =>
      e.matches('chops-checkbox') && /ddd/.test(e.textContent))[0];
    checkbox.click();
    await afterRender();
    assert.deepEqual(['bbb:ccc'], STORE.getState().test.selectedOptions);
  });

  test('select tri-state single', async function() {
    const optionGroup = await fixture();
    STORE.dispatch(UPDATE('test', {selectedOptions: []}));
    const checkbox = findElements(optionGroup, e =>
      e.matches('chops-checkbox') && /ddd/.test(e.textContent))[0];
    checkbox.click();
    await afterRender();
    assert.deepEqual(['bbb:ddd'], STORE.getState().test.selectedOptions);
  });

  test('select tri-state all descendents', async function() {
    const optionGroup = await fixture();
    STORE.dispatch(UPDATE('test', {selectedOptions: ['bbb:ddd']}));
    const checkbox = findElements(optionGroup, e =>
      e.matches('chops-checkbox') && /ddd/.test(e.textContent))[0];
    checkbox.click();
    await afterRender();
    assert.deepEqual(['bbb:ddd', 'bbb:ddd:eee', 'bbb:ddd:fff'],
        STORE.getState().test.selectedOptions);
  });
});
