// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview CategoryFilterButton extracts categories from the model
 * and shows/hides them based on settings.
 */
base.require('filter');
base.require('overlay');
base.exportTo('tracing', function() {

  var CategoryFilterDialog = tracing.ui.define('div');

  CategoryFilterDialog.prototype = {
    __proto__: tracing.ui.Overlay.prototype,

    decorate: function() {
      tracing.ui.Overlay.prototype.decorate.call(this);

      this.className = 'view-category-filter-overlay';
      this.autoClose = true;

      var containerEl = document.createElement('div');
      containerEl.className = 'category-filter-dialog';
      containerEl.textContent = 'Select active categories:';
      this.formEl_ = document.createElement('form');
      this.formEl_.className = 'category-filter-dialog-form';
      containerEl.appendChild(this.formEl_);
      this.appendChild(containerEl);

      this.categoriesEl_ = document.createElement('div');
      this.categoriesEl_.className = 'categories';
      this.formEl_.appendChild(this.categoriesEl_);

      this.addEventListener('visibleChange', this.onVisibleChange_.bind(this));

      this.onChangeCallback_ = undefined;
      this.isCheckedCallback_ = undefined;
    },

    set categories(c) {
      this.categories_ = c;
    },

    set settings_key(k) {
      this.settings_key_ = k;
    },

    set settings(s) {
      this.settings_ = s;
    },

    set settingUpdatedCallback(c) {
      this.settingUpdatedCallback_ = c;
    },

    selectedCategories: function() {
      // TODO(dsinclair): This can be made smarter by just storing an array
      // of selected categories when they're clicked.
      var inputs = this.categoriesEl_.querySelectorAll('input');
      var inputs_length = inputs.length;
      var categories = [];
      for (var i = 0; i < inputs_length; ++i) {
        var input = inputs[i];
        if (input.checked)
          categories.push(input.value);
      }
      return categories;
    },

    unselectedCategories: function() {
      var inputs = this.categoriesEl_.querySelectorAll('input');
      var inputs_length = inputs.length;
      var categories = [];
      for (var i = 0; i < inputs_length; ++i) {
        var input = inputs[i];
        if (input.checked)
          continue;
        categories.push(input.value);
      }
      return categories;
    },

    onVisibleChange_: function() {
      if (this.visible) {
        this.updateForm_();
      }
    },

    updateForm_: function() {
      this.categoriesEl_.innerHTML = ''; // Clear old categories

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
      for (var category in set) {
        categories.push(category);
      }
      categories = categories.sort();

      for (var i = 0; i < categories.length; i++) {
        var category = categories[i];
        var inputEl = document.createElement('input');
        inputEl.type = 'checkbox';
        inputEl.id = inputEl.value = category;
        inputEl.checked =
            this.settings_.get(category, 'true', this.settings_key_) === 'true';
        inputEl.onchange = this.updateSetting_.bind(this);

        var labelEl = document.createElement('label');
        labelEl.textContent = category;
        labelEl.setAttribute('for', category);

        var divEl = document.createElement('div');
        divEl.appendChild(inputEl);
        divEl.appendChild(labelEl);
        this.categoriesEl_.appendChild(divEl);
      }
    },

    updateSetting_: function(e) {
      var checkbox = e.target;
      this.settings_.set(checkbox.value, checkbox.checked, this.settings_key_);
      if (this.settingUpdatedCallback_ !== undefined)
        this.settingUpdatedCallback_();
    }
  };

  return {
    CategoryFilterDialog: CategoryFilterDialog
  };
});
