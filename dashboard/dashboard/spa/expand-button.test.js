/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import {ExpandButton} from './expand-button.js';
import {STORE} from './element-base.js';
import {UPDATE} from './simple-redux.js';
import {assert} from 'chai';
import {get} from 'dot-prop-immutable';

suite('expand-button', function() {
  teardown(() => {
    for (const child of document.body.children) {
      if (!child.matches('expand-button')) continue;
      document.body.removeChild(child);
    }
  });

  test('click toggles isExpanded', async function() {
    const expandButton = document.createElement('expand-button');
    expandButton.statePath = 'clickToggles';
    document.body.appendChild(expandButton);
    STORE.dispatch(UPDATE(
        expandButton.statePath, ExpandButton.buildState({})));
    assert.isFalse(expandButton.isExpanded);
    assert.isFalse(get(
        STORE.getState(), `${expandButton.statePath}.isExpanded`));
    expandButton.click();
    assert.isTrue(expandButton.isExpanded);
    assert.isTrue(get(
        STORE.getState(), `${expandButton.statePath}.isExpanded`));
    expandButton.click();
    assert.isFalse(expandButton.isExpanded);
    assert.isFalse(get(
        STORE.getState(), `${expandButton.statePath}.isExpanded`));
  });

  test('getIcon', async function() {
    assert.strictEqual('more', ExpandButton.getIcon(false, false, false));
    assert.strictEqual('less', ExpandButton.getIcon(false, false, true));
    assert.strictEqual('right', ExpandButton.getIcon(false, true, false));
    assert.strictEqual('left', ExpandButton.getIcon(false, true, true));
    assert.strictEqual('less', ExpandButton.getIcon(true, false, false));
    assert.strictEqual('more', ExpandButton.getIcon(true, false, true));
    assert.strictEqual('left', ExpandButton.getIcon(true, true, false));
    assert.strictEqual('right', ExpandButton.getIcon(true, true, true));
  });
});
