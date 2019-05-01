/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import {assert} from 'chai';
import ExpandButton from './expand-button.js';
import {get} from '@polymer/polymer/lib/utils/path.js';
import {UPDATE} from './simple-redux.js';

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
    expandButton.dispatch(UPDATE(
        expandButton.statePath, ExpandButton.buildState({})));
    assert.isFalse(expandButton.isExpanded);
    assert.isFalse(get(
        expandButton.getState(), `${expandButton.statePath}.isExpanded`));
    expandButton.click();
    assert.isTrue(expandButton.isExpanded);
    assert.isTrue(get(
        expandButton.getState(), `${expandButton.statePath}.isExpanded`));
    expandButton.click();
    assert.isFalse(expandButton.isExpanded);
    assert.isFalse(get(
        expandButton.getState(), `${expandButton.statePath}.isExpanded`));
  });

  test('getIcon', async function() {
    assert.strictEqual('cp:more', ExpandButton.getIcon(false, false, false));
    assert.strictEqual('cp:less', ExpandButton.getIcon(false, false, true));
    assert.strictEqual('cp:right', ExpandButton.getIcon(false, true, false));
    assert.strictEqual('cp:left', ExpandButton.getIcon(false, true, true));
    assert.strictEqual('cp:less', ExpandButton.getIcon(true, false, false));
    assert.strictEqual('cp:more', ExpandButton.getIcon(true, false, true));
    assert.strictEqual('cp:left', ExpandButton.getIcon(true, true, false));
    assert.strictEqual('cp:right', ExpandButton.getIcon(true, true, true));
  });
});
