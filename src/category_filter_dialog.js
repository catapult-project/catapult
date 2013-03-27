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

    get categories() {
      return this.categories_;
    },

    set categories(c) {
      this.categories_ = c;
    },

    set isCheckedCallback(c) {
      this.isCheckedCallback_ = c;
    },

    set onChangeCallback(c) {
      this.onChangeCallback_ = c;
    },

    onVisibleChange_: function() {
      if (this.visible) {
        this.updateForm_();
      }
    },

    updateForm_: function() {
      this.categoriesEl_.innerHTML = ''; // Clear old categories

      for (var i = 0; i < this.categories_.length; i++) {
        var category = this.categories_[i];
        var inputEl = document.createElement('input');
        inputEl.type = 'checkbox';
        inputEl.id = inputEl.value = category;

        if (this.isCheckedCallback_ !== undefined)
          inputEl.checked = this.isCheckedCallback_(category);
        if (this.onChangeCallback_ !== undefined)
          inputEl.onchange = this.onChangeCallback_;

        var labelEl = document.createElement('label');
        labelEl.textContent = category;
        labelEl.setAttribute('for', category);

        var divEl = document.createElement('div');
        divEl.appendChild(inputEl);
        divEl.appendChild(labelEl);
        this.categoriesEl_.appendChild(divEl);
      }
    },
  };

  return {
    CategoryFilterDialog: CategoryFilterDialog
  };
});
