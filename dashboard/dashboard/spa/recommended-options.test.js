/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import RecommendedOptions from './recommended-options.js';
import {STORE} from './element-base.js';
import {UPDATE} from './simple-redux.js';
import {afterRender} from './utils.js';
import {assert} from 'chai';

suite('recommended-options', function() {
  async function fixture() {
    const rec = document.createElement('recommended-options');
    rec.statePath = 'test';
    document.body.appendChild(rec);
    await afterRender();
    return rec;
  }

  setup(() => {
    localStorage.removeItem(RecommendedOptions.STORAGE_KEY);
  });

  teardown(() => {
    for (const child of document.body.children) {
      if (!child.matches('recommended-options')) continue;
      document.body.removeChild(child);
    }
  });

  test('getRecommendations', async function() {
    const now = new Date().getTime();
    localStorage.setItem(RecommendedOptions.STORAGE_KEY, JSON.stringify({
      aaa: [
        new Date(now - 1 - RecommendedOptions.OLD_MS),
        new Date(now - 2 - RecommendedOptions.OLD_MS),
        new Date(now - 3 - RecommendedOptions.OLD_MS),
      ],
      bbb: [
        new Date(now - RecommendedOptions.OLD_MS + 1000),
      ],
      ccc: [
        new Date(now - 1),
      ],
    }));
    const rec = await fixture();
    rec.ready();
    STORE.dispatch(UPDATE('', {
      test: RecommendedOptions.buildState({
        options: ['aaa', 'bbb', 'ccc'],
      }),
    }));
    await afterRender();
    const state = STORE.getState().test;
    assert.deepEqual(['ccc', 'bbb'], state.recommended.optionValues);
  });

  test('select', async function() {
    // localStorage is updated when the user selects an option.
    const rec = await fixture();
    STORE.dispatch(UPDATE('', {
      test: RecommendedOptions.buildState({
        options: ['aaa', 'bbb', 'ccc'],
        selectedOptions: [],
      }),
    }));
    await afterRender();
    STORE.dispatch(UPDATE('test', {selectedOptions: ['aaa']}));
    await afterRender();
    let optionRecommendations = JSON.parse(localStorage.getItem(
        RecommendedOptions.STORAGE_KEY));
    assert.lengthOf(optionRecommendations.aaa, 1);

    // localStorage is not updated when the user selects a whole group of
    // options.
    STORE.dispatch(UPDATE('test', {selectedOptions: ['bbb', 'ccc']}));
    await afterRender();
    optionRecommendations = JSON.parse(localStorage.getItem(
        RecommendedOptions.STORAGE_KEY));
    assert.lengthOf(optionRecommendations.aaa, 1);
  });

  test('recommendOptions', async function() {
    // recommended options change when optionValues change.
    const now = new Date().getTime();
    localStorage.setItem(RecommendedOptions.STORAGE_KEY, JSON.stringify({
      aaa: [
        new Date(now - 1 - RecommendedOptions.OLD_MS),
        new Date(now - 2 - RecommendedOptions.OLD_MS),
        new Date(now - 3 - RecommendedOptions.OLD_MS),
      ],
      bbb: [
        new Date(now - RecommendedOptions.OLD_MS + 1000),
      ],
      ccc: [
        new Date(now - 1),
      ],
    }));
    const rec = await fixture();
    STORE.dispatch(UPDATE('', {
      optionRecommendations: undefined,
    }));
    await afterRender();
    rec.ready();
    STORE.dispatch(UPDATE('', {
      test: RecommendedOptions.buildState({
        options: ['aaa', 'bbb', 'ccc'],
      }),
    }));
    let state = STORE.getState().test;
    assert.deepEqual(['ccc', 'bbb'], state.recommended.optionValues);

    STORE.dispatch(UPDATE('test', {optionValues: ['ddd', 'ccc']}));
    await afterRender();
    state = STORE.getState().test;
    assert.deepEqual(['ccc'], state.recommended.optionValues);
  });
});
