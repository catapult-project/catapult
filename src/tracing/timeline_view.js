// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview View visualizes TRACE_EVENT events using the
 * tracing.Timeline component and adds in selection summary and control buttons.
 */
base.requireStylesheet('tracing.timeline_view');
base.requireTemplate('tracing.timeline_view');

base.require('base.utils');
base.require('base.settings');
base.require('tracing.analysis.analysis_view');
base.require('tracing.category_filter_dialog');
base.require('tracing.filter');
base.require('tracing.find_control');
base.require('tracing.timeline_track_view');
base.require('ui.overlay');
base.require('ui.drag_handle');

base.exportTo('tracing', function() {

  /**
   * View
   * @constructor
   * @extends {HTMLDivElement}
   */
  var TimelineView = ui.define('div');

  TimelineView.prototype = {
    __proto__: HTMLDivElement.prototype,

    decorate: function() {
      this.classList.add('timeline-view');

      var node = base.instantiateTemplate('#timeline-view-template');
      this.appendChild(node);

      this.titleEl_ = this.querySelector('.title');
      this.leftControlsEl_ = this.querySelector('#left-controls');
      this.rightControlsEl_ = this.querySelector('#right-controls');
      this.timelineContainer_ = this.querySelector('.container');

      this.categoryFilterButton_ = this.createCategoryFilterButton_();
      this.categoryFilterButton_.callback =
          this.updateCategoryFilter_.bind(this);

      this.findCtl_ = new tracing.FindControl();
      this.findCtl_.controller = new tracing.FindController();

      this.rightControls.appendChild(this.createImportErrorsButton_());
      this.rightControls.appendChild(this.categoryFilterButton_);
      this.rightControls.appendChild(this.createMetadataButton_());
      this.rightControls.appendChild(this.findCtl_);
      this.rightControls.appendChild(this.createHelpButton_());

      this.dragEl_ = new ui.DragHandle();
      this.appendChild(this.dragEl_);

      this.analysisEl_ = new tracing.analysis.AnalysisView();
      this.analysisEl_.addEventListener(
          'requestSelectionChange',
          this.onRequestSelectionChange_.bind(this));
      this.appendChild(this.analysisEl_);

      // Bookkeeping.
      this.onSelectionChanged_ = this.onSelectionChanged_.bind(this);
      document.addEventListener('keypress', this.onKeypress_.bind(this), true);

      this.dragEl_.target = this.analysisEl_;
    },

    createImportErrorsButton_: function() {
      var node = base.instantiateTemplate('#import-errors-btn-template');
      var showEl = node.querySelector('.view-import-errors-button');
      var containerEl = node.querySelector('.info-button-container');
      var textEl = containerEl.querySelector('.info-button-text');

      var dlg = new ui.Overlay();
      dlg.classList.add('view-import-errors-overlay');
      dlg.obeyCloseEvents = true;
      dlg.appendChild(containerEl);

      function onClick() {
        dlg.visible = true;
        textEl.textContent = this.model.importErrors.join('\n');
      }
      showEl.addEventListener('click', onClick.bind(this));

      function updateVisibility() {
        showEl.style.display =
            (this.model && this.model.importErrors.length) ? '' : 'none';
      }
      var updateVisibility_ = updateVisibility.bind(this);
      updateVisibility_();
      this.addEventListener('modelChange', updateVisibility_);

      return showEl;
    },

    updateCategoryFilter_: function(categories) {
      if (!this.timeline_)
        return;
      this.timeline_.categoryFilter = new tracing.CategoryFilter(categories);
    },

    createCategoryFilterButton_: function() {
      var node = base.instantiateTemplate('#category-filter-btn-template');
      var showEl = node.querySelector('.view-info-button');

      function onClick() {
        var dlg = new tracing.CategoryFilterDialog();
        dlg.categories = this.model.categories;
        dlg.settings_key = 'categories';
        dlg.settingUpdatedCallback = this.updateCategoryFilter_.bind(this);
        dlg.visible = true;
      }
      showEl.addEventListener('click', onClick.bind(this));

      function updateVisibility() {
        showEl.style.display = this.model ? '' : 'none';
      }
      var updateVisibility_ = updateVisibility.bind(this);
      updateVisibility_();
      this.addEventListener('modelChange', updateVisibility_);

      return showEl;
    },

    createHelpButton_: function() {
      var node = base.instantiateTemplate('#help-btn-template');
      var showEl = node.querySelector('.view-help-button');
      var helpTextEl = node.querySelector('.view-help-text');

      var dlg = new ui.Overlay();
      dlg.classList.add('view-help-overlay');
      dlg.obeyCloseEvents = true;
      dlg.additionalCloseKeyCodes.push('?'.charCodeAt(0));
      dlg.appendChild(helpTextEl);

      function onClick(e) {
        dlg.visible = true;

        helpTextEl.textContent = this.timeline_ ? this.timeline_.keyHelp :
            'No content loaded. For interesting help, load something.';

        // Stop event so it doesn't trigger new click listener on document.
        e.stopPropagation();
        return false;
      }
      showEl.addEventListener('click', onClick.bind(this));

      return showEl;
    },

    createMetadataButton_: function() {
      var node = base.instantiateTemplate('#metadata-btn-template');
      var showEl = node.querySelector('.view-metadata-button');
      var containerEl = node.querySelector('.info-button-container');
      var textEl = containerEl.querySelector('.info-button-text');

      var dlg = new ui.Overlay();
      dlg.classList.add('view-metadata-overlay');
      dlg.obeyCloseEvents = true;
      dlg.appendChild(containerEl);

      function onClick() {
        dlg.visible = true;

        var metadataStrings = [];

        var model = this.model;
        for (var data in model.metadata) {
          var meta = model.metadata[data];
          var name = JSON.stringify(meta.name);
          var value = JSON.stringify(meta.value, undefined, ' ');

          metadataStrings.push(name + ': ' + value);
        }
        textEl.textContent = metadataStrings.join('\n');
      }
      showEl.addEventListener('click', onClick.bind(this));

      function updateVisibility() {
        showEl.style.display =
            (this.model && this.model.metadata.length) ? '' : 'none';
      }
      var updateVisibility_ = updateVisibility.bind(this);
      updateVisibility_();
      this.addEventListener('modelChange', updateVisibility_);

      return showEl;
    },

    get leftControls() {
      return this.leftControlsEl_;
    },

    get rightControls() {
      return this.rightControlsEl_;
    },

    get viewTitle() {
      return this.titleEl_.textContent.substring(
          this.titleEl_.textContent.length - 2);
    },

    set viewTitle(text) {
      if (text === undefined) {
        this.titleEl_.textContent = '';
        this.titleEl_.hidden = true;
        return;
      }
      this.titleEl_.hidden = false;
      this.titleEl_.textContent = text;
    },

    set traceData(traceData) {
      this.model = new tracing.TraceModel(traceData);
    },

    get model() {
      if (this.timeline_)
        return this.timeline_.model;
      return undefined;
    },

    set model(model) {
      var modelInstanceChanged = model != this.model;
      var modelValid = model && !model.bounds.isEmpty;

      // Remove old timeline if the model has completely changed.
      if (modelInstanceChanged) {
        this.timelineContainer_.textContent = '';
        if (this.timeline_) {
          this.timeline_.removeEventListener(
              'selectionChange', this.onSelectionChanged_);
          this.timeline_.detach();
          this.timeline_ = undefined;
          this.findCtl_.controller.timeline = undefined;
        }
      }

      // Create new timeline if needed.
      if (modelValid && !this.timeline_) {
        this.timeline_ = new tracing.TimelineTrackView();
        this.timeline_.focusElement =
            this.focusElement_ ? this.focusElement_ : this.parentElement;
        this.timelineContainer_.appendChild(this.timeline_);
        this.findCtl_.controller.timeline = this.timeline_;
        this.timeline_.addEventListener(
            'selectionChange', this.onSelectionChanged_);

        this.analysisEl_.clearSelectionHistory();
      }

      // Set the model.
      if (modelValid)
        this.timeline_.model = model;
      base.dispatchSimpleEvent(this, 'modelChange');

      // Do things that are selection specific
      if (modelInstanceChanged)
        this.onSelectionChanged_();
    },

    get timeline() {
      return this.timeline_;
    },

    get settings() {
      if (!this.settings_)
        this.settings_ = new base.Settings();
      return this.settings_;
    },

    /**
     * Sets the element whose focus state will determine whether
     * to respond to keybaord input.
     */
    set focusElement(value) {
      this.focusElement_ = value;
      if (this.timeline_)
        this.timeline_.focusElement = value;
    },

    /**
     * @return {Element} The element whose focused state determines
     * whether to respond to keyboard inputs.
     * Defaults to the parent element.
     */
    get focusElement() {
      if (this.focusElement_)
        return this.focusElement_;
      return this.parentElement;
    },

    /**
     * @return {boolean} Whether the current timeline is attached to the
     * document.
     */
    get isAttachedToDocument_() {
      var cur = this;
      while (cur.parentNode)
        cur = cur.parentNode;
      return cur == this.ownerDocument;
    },

    get listenToKeys_() {
      if (!this.isAttachedToDocument_)
        return;
      if (!this.focusElement_)
        return true;
      if (this.focusElement.tabIndex >= 0)
        return document.activeElement == this.focusElement;
      return true;
    },

    onKeypress_: function(e) {
      if (!this.listenToKeys_)
        return;

      if (event.keyCode == '/'.charCodeAt(0)) { // / key
        this.findCtl_.focus();
        event.preventDefault();
        return;
      } else if (e.keyCode == '?'.charCodeAt(0)) {
        this.querySelector('.view-help-button').click();
        e.preventDefault();
      }
    },

    beginFind: function() {
      if (this.findInProgress_)
        return;
      this.findInProgress_ = true;
      var dlg = tracing.FindControl();
      dlg.controller = new tracing.FindController();
      dlg.controller.timeline = this.timeline;
      dlg.visible = true;
      dlg.addEventListener('close', function() {
        this.findInProgress_ = false;
      }.bind(this));
      dlg.addEventListener('findNext', function() {
      });
      dlg.addEventListener('findPrevious', function() {
      });
    },

    onSelectionChanged_: function(e) {
      var oldScrollTop = this.timelineContainer_.scrollTop;

      var selection = this.timeline_ ?
          this.timeline_.selection :
          new tracing.Selection();
      this.analysisEl_.selection = selection;
      this.timelineContainer_.scrollTop = oldScrollTop;
    },

    onRequestSelectionChange_: function(e) {
      this.timeline_.selection = e.selection;
      e.stopPropagation();
    }
  };

  return {
    TimelineView: TimelineView
  };
});
