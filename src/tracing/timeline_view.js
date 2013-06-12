// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview View visualizes TRACE_EVENT events using the
 * tracing.Timeline component and adds in selection summary and control buttons.
 */
base.requireStylesheet('tracing.timeline_view');

base.require('base.settings');
base.require('tracing.analysis.analysis_view');
base.require('tracing.category_filter_dialog');
base.require('tracing.filter');
base.require('tracing.find_control');
base.require('tracing.tracks.track_selector');
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

      // Create individual elements.
      this.titleEl_ = document.createElement('div');
      this.titleEl_.textContent = '^_^';
      this.titleEl_.className = 'title';

      this.controlDiv_ = document.createElement('div');
      this.controlDiv_.className = 'control';

      this.leftControlsEl_ = document.createElement('div');
      this.leftControlsEl_.className = 'controls';
      this.rightControlsEl_ = document.createElement('div');
      this.rightControlsEl_.className = 'controls category-filter';

      this.timelineContainer_ = document.createElement('div');
      this.timelineContainer_.className = 'container';

      this.analysisEl_ = new tracing.analysis.AnalysisView();
      this.analysisEl_.addEventListener(
          'requestSelectionChange',
          this.onRequestSelectionChange_.bind(this));

      this.dragEl_ = new ui.DragHandle();
      this.dragEl_.target = this.analysisEl_;

      this.findCtl_ = new tracing.FindControl();
      this.findCtl_.controller = new tracing.FindController();

      this.importErrorsButton_ = this.createImportErrorsButton_();
      this.categoryFilterButton_ = this.createCategoryFilterButton_();
      this.metadataButton_ = this.createMetadataButton_();

      // Connect everything up.
      this.rightControls.appendChild(this.createTrackSelectorButton_());
      this.rightControls.appendChild(this.importErrorsButton_);
      this.rightControls.appendChild(this.categoryFilterButton_);
      this.rightControls.appendChild(this.metadataButton_);
      this.rightControls.appendChild(this.findCtl_);
      this.controlDiv_.appendChild(this.leftControlsEl_);
      this.controlDiv_.appendChild(this.titleEl_);
      this.controlDiv_.appendChild(this.rightControlsEl_);
      this.appendChild(this.controlDiv_);

      this.appendChild(this.timelineContainer_);
      this.appendChild(this.dragEl_);

      this.appendChild(this.analysisEl_);

      this.rightControls.appendChild(this.createHelpButton_());

      // Bookkeeping.
      this.onSelectionChangedBoundToThis_ = this.onSelectionChanged_.bind(this);
      document.addEventListener('keypress', this.onKeypress_.bind(this), true);

      this.trackSelector_.connect();
    },

    createTrackSelectorButton_: function() {
      var anchor = document.createElement('div');
      anchor.className = 'track-selector-anchor';

      var button = document.createElement('button');
      button.className = 'button track-selector-button track-selector-closed';
      button.textContent = 'Track Selector';
      anchor.appendChild(button);

      button.addEventListener('click', function(event) {
        button.classList.toggle('track-selector-closed');
      }.bind(this));

      this.trackSelector_ = anchor.appendChild(
          new tracing.tracks.TrackSelector());

      return anchor;
    },

    createImportErrorsButton_: function() {
      var dlg = new ui.Overlay();
      dlg.classList.add('view-import-errors-overlay');
      dlg.autoClose = true;

      var showEl = document.createElement('div');
      showEl.className = 'button view-import-errors-button view-info-button';
      showEl.textContent = 'Import errors!';

      var textEl = document.createElement('div');
      textEl.className = 'info-button-text import-errors-dialog-text';

      var containerEl = document.createElement('div');
      containerEl.className = 'info-button-container' +
          'import-errors-dialog';

      containerEl.textContent = 'Errors occurred during import:';
      containerEl.appendChild(textEl);
      dlg.appendChild(containerEl);

      var that = this;
      function onClick() {
        dlg.visible = true;
        textEl.textContent = that.model.importErrors.join('\n');
      }
      showEl.addEventListener('click', onClick.bind(this));

      function updateVisibility() {
        if (that.model &&
            that.model.importErrors.length)
          showEl.style.display = '';
        else
          showEl.style.display = 'none';
      }
      updateVisibility();
      that.addEventListener('modelChange', updateVisibility);

      return showEl;
    },

    updateCategoryFilter_: function(categories) {
      if (!this.timeline_)
        return;
      this.timeline_.categoryFilter = new tracing.CategoryFilter(categories);
    },

    createCategoryFilterButton_: function() {
      var showEl = document.createElement('div');
      showEl.className = 'button view-info-button';
      showEl.textContent = 'Categories';

      function onClick() {
        var dlg = new tracing.CategoryFilterDialog();
        dlg.categories = this.model.categories;
        dlg.settings_key = 'categories';
        dlg.settingUpdatedCallback = this.updateCategoryFilter_.bind(this);
        dlg.visible = true;
      }

      var that = this;
      function updateVisibility() {
        showEl.style.display = that.model ? '' : 'none';
      }
      updateVisibility();
      this.addEventListener('modelChange', updateVisibility);

      showEl.addEventListener('click', onClick.bind(this));
      return showEl;
    },

    createHelpButton_: function() {
      var dlg = new ui.Overlay();
      dlg.classList.add('view-help-overlay');
      dlg.autoClose = true;
      dlg.additionalCloseKeyCodes.push('?'.charCodeAt(0));

      var showEl = document.createElement('div');
      showEl.className = 'button view-help-button';
      showEl.textContent = '?';

      var helpTextEl = document.createElement('div');
      helpTextEl.style.whiteSpace = 'pre';
      helpTextEl.style.fontFamily = 'monospace';
      dlg.appendChild(helpTextEl);

      function onClick(e) {
        dlg.visible = true;
        if (this.timeline_)
          helpTextEl.textContent = this.timeline_.keyHelp;
        else
          helpTextEl.textContent = 'No content loaded. For interesting help,' +
              ' load something.';

        // Stop event so it doesn't trigger new click listener on document.
        e.stopPropagation();
        return false;
      }

      showEl.addEventListener('click', onClick.bind(this));

      return showEl;
    },

    createMetadataButton_: function() {
      var dlg = new ui.Overlay();
      dlg.classList.add('view-metadata-overlay');
      dlg.autoClose = true;

      var showEl = document.createElement('div');
      showEl.className = 'button view-metadata-button view-info-button';
      showEl.textContent = 'Metadata';

      var textEl = document.createElement('div');
      textEl.className = 'info-button-text metadata-dialog-text';

      var containerEl = document.createElement('div');
      containerEl.className = 'info-button-container metadata-dialog';

      containerEl.textContent = 'Metadata Info:';
      containerEl.appendChild(textEl);
      dlg.appendChild(containerEl);

      var that = this;
      function onClick() {
        dlg.visible = true;

        var metadataStrings = [];

        var model = that.model;
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
        if (that.model &&
            that.model.metadata.length)
          showEl.style.display = '';
        else
          showEl.style.display = 'none';
      }
      updateVisibility();
      that.addEventListener('modelChange', updateVisibility);

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
              'selectionChange', this.onSelectionChangedBoundToThis_);
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
            'selectionChange', this.onSelectionChangedBoundToThis_);

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
