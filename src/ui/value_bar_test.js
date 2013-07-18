// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.requireStylesheet('ui.value_bar');
base.require('base.unittest');
base.require('base.bbox2');
base.require('ui.dom_helpers');
base.require('ui.value_bar');
base.require('ui.value_display');

base.unittest.testSuite('ui.value_bar', function() {

  function synClick(element) {
    var event = new MouseEvent('click', {});
    element.dispatchEvent(event);
  }

  function createValueBar(testFramework) {
    var container = ui.createDiv();
    container.style.position = 'relative';
    container.style.height = '200px';

    var valueBar = new ui.ValueBar();
    valueBar.style['-webkit-flex-direction'] = 'column';

    testFramework.addHTMLOutput(container);
    container.appendChild(valueBar);

    return valueBar;
  }

  test('vertical', function() {
    var valueBar = createValueBar(this);

    // Test public change event api
    var changeEventsTested = 0;
    valueBar.addEventListener('lowestValueChange', function(event) {
      assertEquals(event.newValue, valueBar.lowestValue);
      changeEventsTested++;
    });

    valueBar.addEventListener('highestValueChange', function(event) {
      assertEquals(event.newValue, valueBar.highestValue);
      changeEventsTested++;
    });

    valueBar.addEventListener('valueChange', function(event) {
      assertEquals(event.newValue, valueBar.value);
      changeEventsTested++;
    });

    valueBar.addEventListener('previewValueChange', function(event) {
      assertEquals(event.newValue, valueBar.previewValue);
      changeEventsTested++;
    });

    valueBar.lowestValue = 0.2;
    assertEquals(valueBar.lowestValue, 0.2);

    valueBar.highestValue = 3.0;
    assertEquals(valueBar.highestValue, 3.0);

    valueBar.value = 1.0;
    assertEquals(valueBar.value, 1.0);

    valueBar.previewValue = 0.5;
    assertEquals(valueBar.previewValue, 0.5);

    // Verify that all change events fired.
    assertEquals(changeEventsTested, 4);
  });

  test('rangeControl', function() {
    var valueBar = createValueBar(this);

    var controlRange = valueBar.rangeControlPixelRange;
    assertEquals(valueBar.fractionalValue_(0), 0);
    assertEquals(valueBar.fractionalValue_(controlRange), 1);

    assertEquals(valueBar.pixelByValue_(0), 0);
    assertEquals(valueBar.pixelByValue_(1), controlRange);

    var lowestValueButton = valueBar.querySelector('.lowest-value-control');
    synClick(lowestValueButton);
    assertEquals(valueBar.value, valueBar.lowestValue);

    var highestValueButton = valueBar.querySelector('.highest-value-control');
    synClick(highestValueButton);
    assertEquals(valueBar.value, valueBar.highestValue);
  });

  test('valueDisplay', function() {
    var valueBar = createValueBar(this);
    var valueDisplay = new ui.ValueDisplay();
    valueDisplay.style.position = 'absolute';
    valueDisplay.style.left = '60px';
    valueDisplay.style.width = '200px';
    valueDisplay.style.display = '-webkit-flex';
    valueDisplay['-webkit-flex-direction'] = 'column';
    valueDisplay.valueBar = valueBar;
    valueBar.parentElement.appendChild(valueDisplay);

    valueBar.lowestValue = 0.2;
    var lowestValueButton = valueBar.querySelector('.lowest-value-control');
    synClick(lowestValueButton);
    assertEquals('0.20 (\u2192 0.20)', valueDisplay.textContent);

    valueBar.highestValue = 3.0;
    var highestValueButton = valueBar.querySelector('.highest-value-control');
    synClick(highestValueButton);
    assertEquals('3.00 (\u2192 3.00)', valueDisplay.textContent);
  });

  test('horizontal', function() {
    var container = ui.createDiv();
    container.style.position = 'relative';
    container.style.height = '200px';

    var valueBar = new ui.ValueBar();
    valueBar.style['-webkit-flex-direction'] = 'row';

    this.addHTMLOutput(container);
    container.appendChild(valueBar);
    valueBar.vertical = false;

    valueBar.lowestValue = -70;
    assertEquals(valueBar.lowestValue, -70);

    valueBar.highestValue = 70;
    assertEquals(valueBar.highestValue, 70);

    valueBar.value = 0.0;
    assertEquals(valueBar.value, 0.0);

    valueBar.previewValue = 0.5;
    assertEquals(valueBar.previewValue, 0.5);

    var controlRange = valueBar.rangeControlPixelRange;
    assertEquals(valueBar.fractionalValue_(0), 0);
    assertEquals(valueBar.fractionalValue_(controlRange), 1);

    assertEquals(valueBar.pixelByValue_(0), 0);
    assertEquals(valueBar.pixelByValue_(1), controlRange);
  });

  test('overrideContent', function() {
    var container = ui.createDiv();
    container.style.position = 'relative';
    container.style.height = '200px';

    var ABBar = ui.define('ab-bar');
    ABBar.prototype = {
      __proto__: ui.ValueBar.prototype,
      updateLowestValueElement: function(element) {
        element.style.fontSize = '25px';
        element.textContent = 'A';
      },
      updateHighestValueElement: function(element) {
        element.style.fontSize = '25px';
        element.textContent = 'B';
      }
    };
    var aBBar = new ABBar();
    assertEquals('AB', aBBar.textContent);
  });
});
