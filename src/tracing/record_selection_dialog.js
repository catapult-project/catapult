// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview RecordSelectionDialog presents the available categories
 * to be enabled/disabled during tracing.
 */
base.require('tracing.filter');
base.require('ui.overlay');
base.requireStylesheet('tracing.record_selection_dialog');
base.exportTo('tracing', function() {

  var RecordSelectionDialog = ui.define('div');

  RecordSelectionDialog.prototype = {
    __proto__: ui.Overlay.prototype,

    decorate: function() {
      ui.Overlay.prototype.decorate.call(this);

      this.className = 'record-dialog-overlay';
      this.autoClose = true;

      var containerEl = document.createElement('div');
      containerEl.className = 'record-selection-dialog';
      this.appendChild(containerEl);

      this.formEl_ = document.createElement('form');
      containerEl.appendChild(this.formEl_);

      var tableEl = document.createElement('table');
      this.formEl_.appendChild(tableEl);

      var rowEl = document.createElement('tr');
      tableEl.appendChild(rowEl);

      var enabledCategoriesEl = document.createElement('td');
      enabledCategoriesEl.className = 'default-enabled-categories';
      rowEl.appendChild(enabledCategoriesEl);

      var categoriesHeaderEl = document.createElement('div');
      categoriesHeaderEl.innerHTML = 'Record&nbsp;Categories';
      enabledCategoriesEl.appendChild(categoriesHeaderEl);

      this.enabledCategoriesContainerEl_ = document.createElement('div');
      this.enabledCategoriesContainerEl_.className = 'categories';
      enabledCategoriesEl.appendChild(this.enabledCategoriesContainerEl_);
      this.createGroupSelectButtons_(categoriesHeaderEl,
                                     this.enabledCategoriesContainerEl_);

      var disabledCategoriesEl = document.createElement('td');
      disabledCategoriesEl.className = 'default-disabled-categories';
      rowEl.appendChild(disabledCategoriesEl);

      var disabledCategoriesHeaderEl = document.createElement('div');
      disabledCategoriesHeaderEl.innerHTML =
          '<div>Disabled&nbsp;by&nbsp;Default&nbsp;Categories</div>';
      disabledCategoriesEl.appendChild(disabledCategoriesHeaderEl);

      this.disabledCategoriesContainerEl_ = document.createElement('div');
      this.disabledCategoriesContainerEl_.className = 'categories';
      disabledCategoriesEl.appendChild(this.disabledCategoriesContainerEl_);
      this.createGroupSelectButtons_(disabledCategoriesHeaderEl,
                                     this.disabledCategoriesContainerEl_);

      var opts = document.createElement('div');
      opts.className = 'options';
      containerEl.appendChild(opts);

      this.buttonEl_ = document.createElement('button');
      this.buttonEl_.innerText = 'Record';
      this.buttonEl_.className = 'record-categories';
      this.buttonEl_.onclick = this.onRecord_.bind(this);
      opts.appendChild(this.buttonEl_);

      this.continuousTracingBn_ = document.createElement('input');
      this.continuousTracingBn_.type = 'checkbox';
      this.continuousTracingBn_.value = 'continuousTracing';
      this.continuousTracingBn_.checked = true;
      this.continuousTracingBn_.onchange = this.updateDlgSetting_.bind(this);

      var continuousTracingLabelEl = document.createElement('label');
      continuousTracingLabelEl.textContent = 'Continuous tracing';
      continuousTracingLabelEl.appendChild(this.continuousTracingBn_);
      opts.appendChild(continuousTracingLabelEl);

      this.systemTracingBn_ = document.createElement('input');
      this.systemTracingBn_.type = 'checkbox';
      this.systemTracingBn_.value = 'systemTracing';
      this.systemTracingBn_.checked = false;
      this.systemTracingBn_.onchange = this.updateDlgSetting_.bind(this);

      this.systemTracingLabelEl_ = document.createElement('label');
      this.systemTracingLabelEl_.textContent = 'System events';
      this.systemTracingLabelEl_.appendChild(this.systemTracingBn_);
      this.systemTracingLabelEl_.style.display = 'none';
      opts.appendChild(this.systemTracingLabelEl_);

      this.addEventListener('visibleChange', this.onVisibleChange_.bind(this));
    },

    updateDlgSetting_: function(e) {
      var checkbox = e.target;
      this.settings_.set(checkbox.value, checkbox.checked, 'record_dlg');
    },

    set categories(c) {
      this.categories_ = c;
    },

    set settings_key(k) {
      this.settings_key_ = k;
    },

    set settings(s) {
      this.settings_ = s;

      this.continuousTracingBn_.checked =
          this.settings_.get('continuousTracing',
              true, 'record_dlg');
      this.systemTracingBn_.checked =
          this.settings_.get('systemTracing',
              false, 'record_dlg');
    },

    set recordCallback(cb) {
      this.recordCallback_ = cb;
    },

    set showSystemTracing(isEnabled) {
      if ((this.settings_ === undefined) ||
          (this.settings_.get('systemTracing',
                              undefined,
                              'record_dlg') === undefined)) {
        this.systemTracingBn_.checked = isEnabled;
      }

      this.systemTracingLabelEl_.style.display =
          isEnabled ? 'inline-block' : 'none';
    },

    isContinuousTracingEnabled: function() {
      return this.continuousTracingBn_.checked;
    },

    isSystemTracingEnabled: function() {
      return this.systemTracingBn_.checked;
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

    onRecord_: function() {
      this.visible = false;
      this.recordCallback_();
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
      if (this.visible) {
        this.updateForm_();
      }
    },

    buildInputs_: function(inputs, checkedDefault, parent) {
      var inputs_length = inputs.length;
      for (var i = 0; i < inputs_length; i++) {
        var category = inputs[i];

        var inputEl = document.createElement('input');
        inputEl.type = 'checkbox';
        inputEl.id = category;
        inputEl.value = category;

        inputEl.checked = this.settings_.get(
            category, checkedDefault, this.settings_key_);
        inputEl.onclick = this.updateSetting_.bind(this);

        var labelEl = document.createElement('label');
        labelEl.textContent = category;
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

      this.buttonEl_.focus();

      // Dedup the categories. We may have things in settings that are also
      // returned when we query the category list.
      var set = {};
      var allCategories =
          this.categories_.concat(this.settings_.keys(this.settings_key_));
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
      this.settings_.set(checkbox.value, checkbox.checked, this.settings_key_);
    },

    createGroupSelectButtons_: function(parent, container) {
      var groupEl = document.createElement('div');
      groupEl.className = 'group-selectors';
      groupEl.innerText = 'Select';
      parent.appendChild(groupEl);

      var flipInputs = function(dir) {
        var inputs = container.querySelectorAll('input');
        for (var i = 0; i < inputs.length; i++) {
          if (inputs[i].checked === dir)
            continue;
          // click() is used so the settings will be correclty stored. Setting
          // checked does not trigger the onclick (or onchange) callback.
          inputs[i].click();
        }
      };

      var allBtn = document.createElement('button');
      allBtn.innerText = 'All';
      allBtn.className = 'all-btn';
      allBtn.onclick = function(evt) {
        flipInputs(true);
        evt.preventDefault();
      };
      groupEl.appendChild(allBtn);

      var noneBtn = document.createElement('button');
      noneBtn.innerText = 'None';
      noneBtn.className = 'none-btn';
      noneBtn.onclick = function(evt) {
        flipInputs(false);
        evt.preventDefault();
      };
      groupEl.appendChild(noneBtn);
    }
  };

  return {
    RecordSelectionDialog: RecordSelectionDialog
  };
});
