// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('ui');

base.exportTo('ui', function() {

  function createSpan(opt_text) {
    var spanEl = document.createElement('span');
    if (opt_text)
      spanEl.textContent = opt_text;
    return spanEl;
  };

  function createSelector(targetEl, targetElProperty,
                          items) {
    var selectorEl = document.createElement('select');
    selectorEl.addEventListener('change', onChange);
    items.forEach(function(item) {
      var optionEl = document.createElement('option');
      optionEl.textContent = item.label;
      optionEl.targetPropertyValue = item.value;
      selectorEl.appendChild(optionEl);
    });
    function onChange(e) {
      targetEl[targetElProperty] =
          selectorEl.selectedOptions[0].targetPropertyValue;
    }
    if (targetEl[targetElProperty] != items[0].value)
      throw new Error('Target class is not yet at the default state');
    return selectorEl;
  }

  var nextCheckboxId = 1;
  function createCheckBox(targetEl, targetElProperty,
                          label) {
    var buttonEl = document.createElement('input');
    buttonEl.type = 'checkbox';
    buttonEl.checked = targetEl[targetElProperty];

    buttonEl.addEventListener('change', function() {
      targetEl[targetElProperty] = buttonEl.checked;
    });

    var id = '#checkbox-' + nextCheckboxId++;

    var spanEl = createSpan();
    buttonEl.setAttribute('id', id);

    var labelEl = document.createElement('label');
    labelEl.textContent = label;
    labelEl.setAttribute('for', id);
    spanEl.appendChild(buttonEl);
    spanEl.appendChild(labelEl);
    return spanEl;
  }

  return {
    createSpan: createSpan,
    createSelector: createSelector,
    createCheckBox: createCheckBox,
  };
});
