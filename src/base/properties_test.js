// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('base.properties');
base.require('ui');

base.unittest.testSuite('base.properties', function() {
  test('defineProperties', function() {
    var stateChanges = [];

    var ASpan = ui.define('span');
    ASpan.prototype = {
      __proto__: HTMLSpanElement.prototype,

      jsProp_: [],

      decorate: function() {
        this.prop_ = false;
        this.addEventListener('propChange', function(event) {
          stateChanges.push('Internal ' + event.oldValue +
              ' to ' + event.newValue);
        }, true);
      },

      get prop() {
        return this.prop_;
      },

      set prop(newValue) {
        base.setPropertyAndDispatchChange(this, 'prop', newValue);
      }
    };

    var aSpan = new ASpan();

    aSpan.addEventListener('propChange', function(event) {
      stateChanges.push(event.oldValue + ' to ' + event.newValue);
    });

    assertFalse(aSpan.prop);

    aSpan.prop = true;
    assertTrue(aSpan.prop);
    assertTrue(stateChanges.length === 2);
    assertTrue(stateChanges[0] === 'Internal false to true');
    assertTrue(stateChanges[1] === 'false to true');

    aSpan.prop = false;
    assertFalse(aSpan.prop);
    assertTrue(stateChanges[3] === 'true to false');
  });
});
