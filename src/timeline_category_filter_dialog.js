// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview TimelineCategoryFilterButton extracts categories from the model
 * and shows/hides them based on settings.
 */
base.require('timeline_filter');
base.require('overlay');
base.exportTo('tracing', function() {

  var TimelineCategoryFilterDialog = base.ui.define('div');

  TimelineCategoryFilterDialog.prototype = {
    __proto__: tracing.Overlay.prototype,

    decorate: function() {
      tracing.Overlay.prototype.decorate.call(this);

      this.className = 'timeline-view-category-filter-overlay';
      this.autoClose = true;

      var containerEl = document.createElement('div');
      containerEl.className = 'category-filter-dialog';
      containerEl.textContent = 'Select active categories:';
      this.formEl_ = document.createElement('form');
      this.formEl_.className = 'category-filter-dialog-form';
      containerEl.appendChild(this.formEl_);
      this.appendChild(containerEl);

      this.addEventListener('visibleChange', this.onVisibleChange_.bind(this));
    },

    get model() {
      return this.model_;
    },

    set model(m) {
      this.model_ = m;
    },

    get settings() {
      return this.settings_;
    },

    set settings(s) {
      this.settings_ = s;
    },

    set settingUpdatedCallback(c) {
      this.settingUpdatedCallback_ = c;
    },

    onVisibleChange_: function() {
      if (this.visible) {
        this.updateForm_();
      }
    },

    updateForm_: function() {
      // Clear and update the form every time the dialog is shown, in case
      // the model or settings have changed with new categories.
      this.formEl_.innerHTML = ''; // Clear old categories
      var categories = this.model_.categories;
      categories.concat(this.settings_.keys('categories'));
      for (var i = 0; i < categories.length; i++) {
        var category = categories[i];
        var inputEl = document.createElement('input');
        inputEl.type = 'checkbox';
        inputEl.id = inputEl.value = category;
        inputEl.checked =
            this.settings_.get(category, 'true', 'categories') == 'true';
        inputEl.onchange = this.updateSetting_.bind(this);
        var labelEl = document.createElement('label');
        labelEl.textContent = category;
        labelEl.setAttribute('for', category);
        this.formEl_.appendChild(inputEl);
        this.formEl_.appendChild(labelEl);
        this.formEl_.appendChild(document.createElement('br'));
      }
    },

    updateSetting_: function(e) {
      var checkbox = e.target;
      this.settings_.set(checkbox.value, checkbox.checked, 'categories');
      this.settingUpdatedCallback_();
    }
  };


  return {
    TimelineCategoryFilterDialog: TimelineCategoryFilterDialog
  };
});
