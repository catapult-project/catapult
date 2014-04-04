// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

tvcm.require('tvcm.ui');
tvcm.require('tvcm.settings');

tvcm.exportTo('tvcm.ui', function() {

  function createSpan(opt_dictionary) {
    var spanEl = document.createElement('span');
    if (opt_dictionary) {
      if (opt_dictionary.className)
        spanEl.className = opt_dictionary.className;
      if (opt_dictionary.textContent)
        spanEl.textContent = opt_dictionary.textContent;
      if (opt_dictionary.parent)
        opt_dictionary.parent.appendChild(spanEl);
      if (opt_dictionary.bold)
        spanEl.style.fontWeight = 'bold';
    }
    return spanEl;
  };

  function createDiv(opt_dictionary) {
    var divEl = document.createElement('div');
    if (opt_dictionary) {
      if (opt_dictionary.className)
        divEl.className = opt_dictionary.className;
      if (opt_dictionary.parent)
        opt_dictionary.parent.appendChild(divEl);
    }
    return divEl;
  };

  function createScopedStyle(styleContent) {
    var styleEl = document.createElement('style');
    styleEl.scoped = true;
    styleEl.innerHTML = styleContent;
    return styleEl;
  }

  function createSelector(
      targetEl, targetElProperty,
      settingsKey, defaultValue,
      items) {
    var defaultValueIndex;
    for (var i = 0; i < items.length; i++) {
      var item = items[i];
      if (item.value == defaultValue) {
        defaultValueIndex = i;
        break;
      }
    }
    if (defaultValueIndex === undefined)
      throw new Error('defaultValue must be in the items list');

    var selectorEl = document.createElement('select');
    selectorEl.addEventListener('change', onChange);
    for (var i = 0; i < items.length; i++) {
      var item = items[i];
      var optionEl = document.createElement('option');
      optionEl.textContent = item.label;
      optionEl.targetPropertyValue = item.value;
      selectorEl.appendChild(optionEl);
    }
    function onChange(e) {
      var value = selectorEl.selectedOptions[0].targetPropertyValue;
      tvcm.Settings.set(settingsKey, value);
      targetEl[targetElProperty] = value;
    }
    var oldSetter = targetEl.__lookupSetter__('selectedIndex');
    selectorEl.__defineGetter__('selectedValue', function(v) {
      return selectorEl.children[selectorEl.selectedIndex].targetPropertyValue;
    });
    selectorEl.__defineSetter__('selectedValue', function(v) {
      for (var i = 0; i < selectorEl.children.length; i++) {
        var value = selectorEl.children[i].targetPropertyValue;
        if (value == v) {
          selectorEl.selectedIndex = i;
          onChange();
          return;
        }
      }
      throw new Error('Not a valid value');
    });

    var initialValue = tvcm.Settings.get(settingsKey, defaultValue);
    var didSet = false;
    for (var i = 0; i < selectorEl.children.length; i++) {
      if (selectorEl.children[i].targetPropertyValue == initialValue) {
        didSet = true;
        targetEl[targetElProperty] = initialValue;
        selectorEl.selectedIndex = i;
        break;
      }
    }
    if (!didSet) {
      selectorEl.selectedIndex = defaultValueIndex;
      targetEl[targetElProperty] = defaultValue;
    }

    return selectorEl;
  }

  var nextCheckboxId = 1;
  function createCheckBox(targetEl, targetElProperty,
                          settingsKey, defaultValue,
                          label) {
    var buttonEl = document.createElement('input');
    buttonEl.type = 'checkbox';

    var initialValue = tvcm.Settings.get(settingsKey, defaultValue);
    buttonEl.checked = !!initialValue;
    if (targetEl)
      targetEl[targetElProperty] = initialValue;

    function onChange() {
      tvcm.Settings.set(settingsKey, buttonEl.checked);
      if (targetEl)
        targetEl[targetElProperty] = buttonEl.checked;
    }

    buttonEl.addEventListener('change', onChange);

    var id = '#checkbox-' + nextCheckboxId++;

    var spanEl = createSpan({className: 'labeled-checkbox'});
    buttonEl.setAttribute('id', id);

    var labelEl = document.createElement('label');
    labelEl.textContent = label;
    labelEl.setAttribute('for', id);
    spanEl.appendChild(buttonEl);
    spanEl.appendChild(labelEl);

    spanEl.__defineSetter__('checked', function(opt_bool) {
      buttonEl.checked = !!opt_bool;
      onChange();
    });
    spanEl.__defineGetter__('checked', function() {
      return buttonEl.checked;
    });

    return spanEl;
  }

  return {
    createSpan: createSpan,
    createDiv: createDiv,
    createScopedStyle: createScopedStyle,
    createSelector: createSelector,
    createCheckBox: createCheckBox
  };
});
