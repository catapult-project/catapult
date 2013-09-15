// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview RecordSelectionDialog presents the available categories
 * to be enabled/disabled during tracing.
 */
base.requireTemplate('tracing.record_selection_dialog');

base.require('base.utils');
base.require('tracing.filter');
base.require('ui.overlay');
base.require('ui.dom_helpers');

base.exportTo('tracing', function() {
  var RecordSelectionDialog = ui.define('div');

  RecordSelectionDialog.prototype = {
    __proto__: ui.Overlay.prototype,

    decorate: function() {
      ui.Overlay.prototype.decorate.call(this);
      this.title = 'Record a new trace...';

      this.classList.add('record-dialog-overlay');

      var node = base.instantiateTemplate('#record-selection-dialog-template');
      this.appendChild(node);

      this.recordButtonEl_ = document.createElement('button');
      this.recordButtonEl_.textContent = 'Record';
      this.recordButtonEl_.addEventListener(
          'click',
          this.onRecordButtonClicked_.bind(this));
      this.recordButtonEl_.style.fontSize = '110%';
      this.rightButtons.appendChild(this.recordButtonEl_);

      this.continuousTracingBn_ = ui.createCheckBox(
          undefined, undefined,
          'recordSelectionDialog.useContinuousTracing', true,
          'Continuous tracing');
      this.systemTracingBn_ = ui.createCheckBox(
          undefined, undefined,
          'recordSelectionDialog.useSystemTracing', true,
          'System tracing');
      this.samplingTracingBn_ = ui.createCheckBox(
          undefined, undefined,
          'recordSelectionDialog.useSampling', false,
          'State sampling');
      this.leftButtons.appendChild(this.continuousTracingBn_);
      this.leftButtons.appendChild(this.systemTracingBn_);
      this.leftButtons.appendChild(this.samplingTracingBn_);

      this.enabledCategoriesContainerEl_ =
          this.querySelector('.default-enabled-categories .categories');

      this.disabledCategoriesContainerEl_ =
          this.querySelector('.default-disabled-categories .categories');

      this.createGroupSelectButtons_(
          this.querySelector('.default-enabled-categories'));
      this.createGroupSelectButtons_(
          this.querySelector('.default-disabled-categories'));

      this.addEventListener('visibleChange', this.onVisibleChange_.bind(this));
    },

    set supportsSystemTracing(s) {
      if (s) {
        this.systemTracingBn_.style.display = undefined;
      } else {
        this.systemTracingBn_.style.display = 'none';
        this.useSystemTracing = false;
      }
    },

    get useContinuousTracing() {
      return this.continuousTracingBn_.checked;
    },
    set useContinuousTracing(value) {
      this.continuousTracingBn_.checked = !!value;
    },

    get useSystemTracing() {
      return this.systemTracingBn_.checked;
    },
    set useSystemTracing(value) {
      this.systemTracingBn_.checked = !!value;
    },
    get useSampling() {
      return this.samplingTracingBn_.checked;
    },
    set useSampling(value) {
      this.samplingTracingBn_.checked = !!value;
    },

    set categories(c) {
      this.categories_ = c;
    },

    set settings_key(k) {
      this.settings_key_ = k;
    },

    set settings(s) {
      throw new Error('Dont use this!');
    },

    categoryFilter: function() {
      var categories = this.unselectedCategories_();
      var categories_length = categories.length;
      var negated_categories = [];
      for (var i = 0; i < categories_length; ++i) {
        // Skip any category with a , as it will cause issues when we negate.
        // Both sides should have been added as separate categories, these can
        // only come from settings.
        if (categories[i].match(/,/))
          continue;
        negated_categories.push('-' + categories[i]);
      }
      categories = negated_categories.join(',');

      var disabledCategories = this.enabledDisabledByDefaultCategories_();
      disabledCategories = disabledCategories.join(',');

      var results = [];
      if (categories !== '')
        results.push(categories);
      if (disabledCategories !== '')
        results.push(disabledCategories);

      return results.join(',');
    },

    clickRecordButton: function() {
      this.recordButtonEl_.click();
    },

    onRecordButtonClicked_: function() {
      this.visible = false;
      base.dispatchSimpleEvent(this, 'recordclicked');
      return false;
    },

    collectInputs_: function(inputs, isChecked) {
      var inputs_length = inputs.length;
      var categories = [];
      for (var i = 0; i < inputs_length; ++i) {
        var input = inputs[i];
        if (input.checked === isChecked)
          categories.push(input.value);
      }
      return categories;
    },

    unselectedCategories_: function() {
      var inputs =
          this.enabledCategoriesContainerEl_.querySelectorAll('input');
      return this.collectInputs_(inputs, false);
    },

    enabledDisabledByDefaultCategories_: function() {
      var inputs =
          this.disabledCategoriesContainerEl_.querySelectorAll('input');
      return this.collectInputs_(inputs, true);
    },

    onVisibleChange_: function() {
      if (this.visible)
        this.updateForm_();
    },

    buildInputs_: function(inputs, checkedDefault, parent) {
      var inputs_length = inputs.length;
      for (var i = 0; i < inputs_length; i++) {
        var category = inputs[i];

        var inputEl = document.createElement('input');
        inputEl.type = 'checkbox';
        inputEl.id = category;
        inputEl.value = category;

        inputEl.checked = base.Settings.get(
            category, checkedDefault, this.settings_key_);
        inputEl.onclick = this.updateSetting_.bind(this);

        var labelEl = document.createElement('label');
        labelEl.textContent = category.replace('disabled-by-default-', '');
        labelEl.setAttribute('for', category);

        var divEl = document.createElement('div');
        divEl.appendChild(inputEl);
        divEl.appendChild(labelEl);

        parent.appendChild(divEl);
      }
    },

    updateForm_: function() {
      this.enabledCategoriesContainerEl_.innerHTML = ''; // Clear old categories
      this.disabledCategoriesContainerEl_.innerHTML = '';

      this.recordButtonEl_.focus();

      // Dedup the categories. We may have things in settings that are also
      // returned when we query the category list.
      var set = {};
      var allCategories =
          this.categories_.concat(base.Settings.keys(this.settings_key_));
      var allCategoriesLength = allCategories.length;
      for (var i = 0; i < allCategoriesLength; ++i) {
        set[allCategories[i]] = true;
      }

      var categories = [];
      var disabledCategories = [];
      for (var category in set) {
        if (category.indexOf('disabled-by-default-') == 0)
          disabledCategories.push(category);
        else
          categories.push(category);
      }
      disabledCategories = disabledCategories.sort();
      categories = categories.sort();

      this.buildInputs_(categories, true, this.enabledCategoriesContainerEl_);

      if (disabledCategories.length > 0) {
        this.disabledCategoriesContainerEl_.hidden = false;
        this.buildInputs_(disabledCategories, false,
            this.disabledCategoriesContainerEl_);
      }
    },

    updateSetting_: function(e) {
      var checkbox = e.target;
      base.Settings.set(checkbox.value, checkbox.checked, this.settings_key_);
    },

    createGroupSelectButtons_: function(parent) {
      var flipInputs = function(dir) {
        var inputs = parent.querySelectorAll('input');
        for (var i = 0; i < inputs.length; i++) {
          if (inputs[i].checked === dir)
            continue;
          // click() is used so the settings will be correclty stored. Setting
          // checked does not trigger the onclick (or onchange) callback.
          inputs[i].click();
        }
      };

      var allBtn = parent.querySelector('.all-btn');
      allBtn.onclick = function(evt) {
        flipInputs(true);
        evt.preventDefault();
      };

      var noneBtn = parent.querySelector('.none-btn');
      noneBtn.onclick = function(evt) {
        flipInputs(false);
        evt.preventDefault();
      };
    }
  };

  return {
    RecordSelectionDialog: RecordSelectionDialog
  };
});
