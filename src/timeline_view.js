// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview TimelineView visualizes TRACE_EVENT events using the
 * tracing.Timeline component and adds in selection summary and control buttons.
 */
base.requireStylesheet('timeline_view');

base.require('timeline');
base.require('timeline_analysis');
base.require('timeline_category_filter_dialog');
base.require('timeline_filter');
base.require('timeline_find_control');
base.require('overlay');
base.require('trace_event_importer');
base.require('linux_perf_importer');
base.require('settings');

base.exportTo('tracing', function() {

  /**
   * TimelineView
   * @constructor
   * @extends {HTMLDivElement}
   */
  var TimelineView = base.ui.define('div');

  TimelineView.prototype = {
    __proto__: HTMLDivElement.prototype,

    decorate: function() {
      this.classList.add('timeline-view');

      // Create individual elements.
      this.titleEl_ = document.createElement('div');
      this.titleEl_.textContent = 'Tracing: ';
      this.titleEl_.className = 'title';

      this.controlDiv_ = document.createElement('div');
      this.controlDiv_.className = 'control';

      this.leftControlsEl_ = document.createElement('div');
      this.leftControlsEl_.className = 'controls';
      this.rightControlsEl_ = document.createElement('div');
      this.rightControlsEl_.className = 'controls';

      var spacingEl = document.createElement('div');
      spacingEl.className = 'spacer';

      this.timelineContainer_ = document.createElement('div');
      this.timelineContainer_.className = 'timeline-container';

      var analysisContainer_ = document.createElement('div');
      analysisContainer_.className = 'analysis-container';

      this.analysisEl_ = new tracing.TimelineAnalysisView();

      this.dragEl_ = new TimelineDragHandle();
      this.dragEl_.target = analysisContainer_;

      this.findCtl_ = new tracing.TimelineFindControl();
      this.findCtl_.controller = new tracing.TimelineFindController();

      this.importErrorsButton_ = this.createImportErrorsButton_();
      this.categoryFilterButton_ = this.createCategoryFilterButton_();
      this.categoryFilterButton_.callback =
          this.updateCategoryFilterFromSettings_.bind(this);
      this.metadataButton_ = this.createMetadataButton_();

      // Connect everything up.
      this.rightControls.appendChild(this.importErrorsButton_);
      this.rightControls.appendChild(this.categoryFilterButton_);
      this.rightControls.appendChild(this.metadataButton_);
      this.rightControls.appendChild(this.findCtl_);
      this.controlDiv_.appendChild(this.titleEl_);
      this.controlDiv_.appendChild(this.leftControlsEl_);
      this.controlDiv_.appendChild(spacingEl);
      this.controlDiv_.appendChild(this.rightControlsEl_);
      this.appendChild(this.controlDiv_);

      this.appendChild(this.timelineContainer_);
      this.appendChild(this.dragEl_);

      analysisContainer_.appendChild(this.analysisEl_);
      this.appendChild(analysisContainer_);

      this.rightControls.appendChild(this.createHelpButton_());

      // Bookkeeping.
      this.onSelectionChangedBoundToThis_ = this.onSelectionChanged_.bind(this);
      document.addEventListener('keypress', this.onKeypress_.bind(this), true);
    },

    createImportErrorsButton_: function() {
      var dlg = new tracing.Overlay();
      dlg.classList.add('timeline-view-import-errors-overlay');
      dlg.autoClose = true;

      var showEl = document.createElement('div');
      showEl.className = 'timeline-button timeline-view-import-errors-button' +
          ' timeline-view-info-button';
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

    createCategoryFilterButton_: function() {
      // Set by the embedder of the help button that we create in this function.
      var callback;

      var showEl = document.createElement('div');
      showEl.className = 'timeline-button timeline-view-info-button';
      showEl.textContent = 'Categories';
      showEl.__defineSetter__('callback', function(value) {
        callback = value;
      });


      var that = this;
      function onClick() {
        var dlg = new tracing.TimelineCategoryFilterDialog();
        dlg.model = that.model;
        dlg.settings = that.settings;
        dlg.settingUpdatedCallback = callback;
        dlg.visible = true;
      }

      function updateVisibility() {
        if (that.model)
          showEl.style.display = '';
        else
          showEl.style.display = 'none';
      }
      updateVisibility();
      that.addEventListener('modelChange', updateVisibility);

      showEl.addEventListener('click', onClick.bind(this));
      return showEl;
    },

    createHelpButton_: function() {
      var dlg = new tracing.Overlay();
      dlg.classList.add('timeline-view-help-overlay');
      dlg.autoClose = true;
      dlg.additionalCloseKeyCodes.push('?'.charCodeAt(0));

      var showEl = document.createElement('div');
      showEl.className = 'timeline-button timeline-view-help-button';
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
      var dlg = new tracing.Overlay();
      dlg.classList.add('timeline-view-metadata-overlay');
      dlg.autoClose = true;

      var showEl = document.createElement('div');
      showEl.className = 'timeline-button timeline-view-metadata-button' +
          ' timeline-view-info-button';
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
          metadataStrings.push(JSON.stringify(model.metadata[data].name) +
              ': ' + JSON.stringify(model.metadata[data].value));
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

    get title() {
      return this.titleEl_.textContent.substring(
          this.titleEl_.textContent.length - 2);
    },

    set title(text) {
      this.titleEl_.textContent = text + ':';
    },

    set traceData(traceData) {
      this.model = new tracing.TimelineModel(traceData);
    },

    get model() {
      if (this.timeline_)
        return this.timeline_.model;
      return undefined;
    },

    set model(model) {
      var modelInstanceChanged = model != this.model;
      var modelValid = model && model.minTimestamp !== undefined;

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
        this.timeline_ = new tracing.Timeline();
        this.timeline_.focusElement =
            this.focusElement_ ? this.focusElement_ : this.parentElement;
        this.timelineContainer_.appendChild(this.timeline_);
        this.findCtl_.controller.timeline = this.timeline_;
        this.timeline_.addEventListener(
            'selectionChange', this.onSelectionChangedBoundToThis_);
        this.updateCategoryFilterFromSettings_();
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
        this.querySelector('.timeline-view-help-button').click();
        e.preventDefault();
      }
    },

    beginFind: function() {
      if (this.findInProgress_)
        return;
      this.findInProgress_ = true;
      var dlg = tracing.TimelineFindControl();
      dlg.controller = new tracing.TimelineFindController();
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
          new tracing.TimelineSelection();
      this.analysisEl_.selection = selection;
      this.timelineContainer_.scrollTop = oldScrollTop;
    },

    updateCategoryFilterFromSettings_: function() {
      if (!this.timeline_)
        return;

      // Get the disabled categories from settings.
      var categories = this.settings.keys('categories');
      var disabledCategories = [];
      for (var i = 0; i < categories.length; i++) {
        if (this.settings.get(categories[i], 'true', 'categories') == 'false')
          disabledCategories.push(categories[i]);
      }

      this.timeline_.categoryFilter =
          new tracing.TimelineCategoryFilter(disabledCategories);
    }
  };

  /**
   * Timeline Drag Handle
   * Detects when user clicks handle determines new height of container based
   * on user's vertical mouse move and resizes the target.
   * @constructor
   * @extends {HTMLDivElement}
   * You will need to set target to be the draggable element
   */
  var TimelineDragHandle = base.ui.define('div');

  TimelineDragHandle.prototype = {
    __proto__: HTMLDivElement.prototype,

    decorate: function() {
      this.className = 'timeline-drag-handle';
      this.lastMousePosY = 0;
      this.dragAnalysis = this.dragAnalysis.bind(this);
      this.onMouseUp = this.onMouseUp.bind(this);
      this.addEventListener('mousedown', this.onMouseDown);
    },

    dragAnalysis: function(e) {
      // Compute the difference in height position.
      var dy = this.lastMousePosY - e.clientY;
      // If style is not set, start off with computed height.
      if (!this.target.style.height)
        this.target.style.height = window.getComputedStyle(this.target).height;
      // Calculate new height of the container.
      this.target.style.height = parseInt(this.target.style.height) + dy + 'px';
      this.lastMousePosY = e.clientY;
    },

    onMouseDown: function(e) {
      this.lastMousePosY = e.clientY;
      document.addEventListener('mousemove', this.dragAnalysis);
      document.addEventListener('mouseup', this.onMouseUp);
      e.stopPropagation();
      return false;
    },

    onMouseUp: function(e) {
      document.removeEventListener('mousemove', this.dragAnalysis);
      document.removeEventListener('mouseup', this.onMouseUp);
    }
  };

  return {
    TimelineView: TimelineView
  };
});
