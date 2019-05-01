/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import {assert} from 'chai';
import MenuInput from './menu-input.js';
import OptionGroup from './option-group.js';
import TagFilter from './tag-filter.js';
import findElements from './find-elements.js';
import {UPDATE} from './simple-redux.js';
import {afterRender} from './utils.js';

suite('tag-filter', function() {
  teardown(() => {
    for (const child of document.body.children) {
      if (!child.matches('tag-filter')) continue;
      document.body.removeChild(child);
    }
  });

  test('filter', async function() {
    const tagFilter = document.createElement('tag-filter');
    tagFilter.statePath = 'test';
    await tagFilter.dispatch(UPDATE('', {
      test: {
        ...MenuInput.buildState({
          label: 'Test',
          options: new Set([
            'aaa',
            'bbb',
            'ccc',
            'ddd',
            'eee',
          ]),
        }),
        tags: {
          options: OptionGroup.groupValues(new Set([
            'xxx',
            'yyy',
          ])),
          map: new Map([
            ['xxx', ['aaa', 'ccc']],
            ['yyy', ['bbb', 'ddd']],
          ]),
          selectedOptions: [],
          query: '',
        },
      },
    }));
    document.body.appendChild(tagFilter);
    await afterRender();

    const xxx = findElements(tagFilter, e =>
      e.matches('cp-checkbox') && /xxx/.test(e.textContent))[0];
    xxx.$.native.click();
    await afterRender();
    let state = tagFilter.getState().test;
    assert.deepEqual(['aaa', 'ccc'],
        state.options[0].options.map(o => o.value));
    assert.deepEqual(['aaa', 'ccc'], state.selectedOptions);

    xxx.$.native.click();
    await afterRender();
    state = tagFilter.getState().test;
    assert.deepEqual(['aaa', 'bbb', 'ccc', 'ddd', 'eee'],
        state.options[0].options.map(o => o.value));
    assert.deepEqual([], state.selectedOptions);

    const yyy = findElements(tagFilter, e =>
      e.matches('cp-checkbox') && /yyy/.test(e.textContent))[0];
    yyy.$.native.click();
    await afterRender();
    state = tagFilter.getState().test;
    assert.deepEqual(['bbb', 'ddd'],
        state.options[0].options.map(o => o.value));
    assert.deepEqual(['bbb', 'ddd'], state.selectedOptions);

    xxx.$.native.click();
    await afterRender();
    state = tagFilter.getState().test;
    assert.deepEqual(['aaa', 'bbb', 'ccc', 'ddd'],
        state.options[0].options.map(o => o.value));
    assert.deepEqual(['aaa', 'bbb', 'ccc', 'ddd'], state.selectedOptions);
  });
});
