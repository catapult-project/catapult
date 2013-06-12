// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

base.require('ui');

'use strict';

base.unittest.testSuite('base', function() {
  test('defineProperties', function() {
    var ASpan = ui.define('span');

    ASpan.prototype = {
      __proto__: HTMLSpanElement.prototype,

      jsProp_: [],

      decorate: function() {
        this.boolProp = false;
      }
    };

    var propName = 'boolProp';
    base.defineProperty(ASpan, propName, base.PropertyKind.BOOL_ATTR);

    base.defineProperty(ASpan, 'jsProp', base.PropertyKind.JS);

    var aSpan = new ASpan();

    var stateChanges;
    aSpan.addEventListener('boolPropChange', function(event) {
      stateChanges = event.oldValue + ' to ' + event.newValue;
    });

    aSpan.boolProp = true;
    assertTrue(stateChanges === 'false to true');
    aSpan.boolProp = false;
    assertTrue(stateChanges === 'true to false');

    aSpan.addEventListener('jsPropChange', function(event) {
      stateChanges = event.oldValue + ' to ' + event.newValue;
    });

    aSpan.jsProp = 'obfuscated';

    assertTrue(stateChanges === 'undefined to obfuscated');
    assertTrue(aSpan.jsProp_ instanceof Array);

    aSpan.addEventListener('jsPropChange', function(event) {
      event.throwError(new Error('flub'));
    });

    var caught = false;
    try {
      aSpan.jsProp = 'anything';
    } catch (exc) {
      caught = true;
    }
    assertTrue(caught);

  });
});
