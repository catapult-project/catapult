// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.requireStylesheet('ui.value_bar');
base.require('base.unittest');
base.require('base.bbox2');
base.require('ui.dom_helpers');
base.require('ui.text_end_value_bar');

base.unittest.testSuite('ui.text_end_value_bar', function() {

  function synClick(element) {
    var event = new MouseEvent('click', {});
    element.dispatchEvent(event);
  }

  test('instantiate', function() {
    var container = ui.createDiv();
    container.style.position = 'relative';
    container.style.height = '200px';

    var valueBar = new ui.TextEndValueBar();
    valueBar.style['-webkit-flex-direction'] = 'column';

    this.addHTMLOutput(container);
    container.appendChild(valueBar);

    valueBar.lowestValueProperties = {
      style: {
        'fontSize': '24px',
      },
      textContent: 'Z'
    };
    valueBar.highestValueProperties = {
      style: {
        'fontSize': '24px',
      },
      textContent: 'Y'
    };
    assertEquals('ZY', valueBar.textContent);
  });
});
