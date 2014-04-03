// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview View visualizes TRACE_EVENT events using the
 * tracing.Timeline component and adds in selection summary and control buttons.
 */
tvcm.requireStylesheet('tvcm.ui.common');
tvcm.requireStylesheet('tracing.timeline_view');
tvcm.requireTemplate('tracing.timeline_view');

tvcm.require('tvcm.utils');
tvcm.require('tvcm.settings');
tvcm.require('tracing.analysis.analysis_view');
tvcm.require('tracing.find_control');
tvcm.require('tracing.timeline_track_view');
tvcm.require('tvcm.ui.dom_helpers');
tvcm.require('tvcm.ui.overlay');
tvcm.require('tvcm.ui.drag_handle');

tvcm.require('tracing.analysis.cpu_slice_view');
tvcm.require('tracing.analysis.thread_time_slice_view');
tvcm.require('tracing.time_summary_side_panel');
tvcm.require('tracing.timeline_view_side_panel');

tvcm.exportTo('tracing', function() {

  /**
   * View
   * @constructor
   * @extends {HTMLUnknownElement}
   */
  var TimelineView = tvcm.ui.define('x-timeline-view');

  TimelineView.prototype = {
    __proto__: HTMLUnknownElement.prototype,

    decorate: function() {
      var node = tvcm.instantiateTemplate('#timeline-view-template');
      this.appendChild(node);

      this.titleEl_ = this.querySelector('.title');
      this.leftControlsEl_ = this.querySelector('#left-controls');
      this.rightControlsEl_ = this.querySelector('#right-controls');
      this.timelineViewSidePanelContainer_ = this.querySelector(
          'x-timeline-view-side-panel-container');
      this.trackViewContainer_ = this.querySelector('track-view-container');

      tvcm.ui.decorate(this.timelineViewSidePanelContainer_,
                       tracing.TimelineViewSidePanelContainer);

      this.findCtl_ = new tracing.FindControl();
      this.findCtl_.controller = new tracing.FindController();

      this.rightControls.appendChild(this.createMetadataButton_());
      this.rightControls.appendChild(this.findCtl_);
      this.rightControls.appendChild(this.createHelpButton_());

      this.dragEl_ = this.querySelector('x-drag-handle');
      tvcm.ui.decorate(this.dragEl_, tvcm.ui.DragHandle);

      this.analysisEl_ = this.querySelector('#analysis');
      tvcm.ui.decorate(this.analysisEl_, tracing.analysis.AnalysisView);

      this.appendChild(this.analysisEl_);
      this.addEventListener('requestSelectionChange',
                            this.onRequestSelectionChange_.bind(this));

      // Bookkeeping.
      this.onSelectionChanged_ = this.onSelectionChanged_.bind(this);
      document.addEventListener('keydown', this.onKeyDown_.bind(this), true);
      document.addEventListener('keypress', this.onKeypress_.bind(this), true);

      this.dragEl_.target = this.analysisEl_;
    },

    createHelpButton_: function() {
      var node = tvcm.instantiateTemplate('#help-btn-template');
      var showEl = node.querySelector('.view-help-button');
      var helpTextEl = node.querySelector('.view-help-text');

      var dlg = new tvcm.ui.Overlay();
      dlg.title = 'chrome://tracing Help';
      dlg.classList.add('view-help-overlay');
      dlg.appendChild(node);

      function onClick(e) {
        dlg.visible = !dlg.visible;

        var mod = tvcm.isMac ? 'cmd ' : 'ctrl';
        var spans = helpTextEl.querySelectorAll('span.mod');
        for (var i = 0; i < spans.length; i++) {
          spans[i].textContent = mod;
        }

        // Stop event so it doesn't trigger new click listener on document.
        e.stopPropagation();
        return false;
      }
      showEl.addEventListener('click', onClick.bind(this));

      return showEl;
    },

    createMetadataButton_: function() {
      var node = tvcm.instantiateTemplate('#metadata-btn-template');
      var showEl = node.querySelector('.view-metadata-button');
      var textEl = node.querySelector('.info-button-text');

      var dlg = new tvcm.ui.Overlay();
      dlg.title = 'Metadata for trace';
      dlg.classList.add('view-metadata-overlay');
      dlg.appendChild(node);

      function onClick(e) {
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

        e.stopPropagation();
        return false;
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

    get model() {
      if (this.trackView_)
        return this.trackView_.model;
      return undefined;
    },

    set model(model) {
      var modelInstanceChanged = model != this.model;
      var modelValid = model && !model.bounds.isEmpty;

      // Remove old trackView if the model has completely changed.
      if (modelInstanceChanged) {
        this.trackViewContainer_.textContent = '';
        if (this.trackView_) {
          this.trackView_.removeEventListener(
              'selectionChange', this.onSelectionChanged_);
          this.trackView_.detach();
          this.trackView_ = undefined;
          this.findCtl_.controller.trackView = undefined;
        }
        this.timelineViewSidePanelContainer_.model = undefined;
      }

      // Create new trackView if needed.
      if (modelValid && !this.trackView_) {
        this.trackView_ = new tracing.TimelineTrackView();
        this.trackView_.focusElement =
            this.focusElement_ ? this.focusElement_ : this.parentElement;
        this.trackViewContainer_.appendChild(this.trackView_);
        this.findCtl_.controller.timeline = this.trackView_;
        this.trackView_.addEventListener(
            'selectionChange', this.onSelectionChanged_);
        this.analysisEl_.clearSelectionHistory();
      }

      // Set the model.
      if (modelValid) {
        this.trackView_.model = model;
        this.timelineViewSidePanelContainer_.model = model;
      }
      tvcm.dispatchSimpleEvent(this, 'modelChange');

      // Do things that are selection specific
      if (modelInstanceChanged)
        this.onSelectionChanged_();
    },

    get timeline() {
      return this.trackView_;
    },

    get settings() {
      if (!this.settings_)
        this.settings_ = new tvcm.Settings();
      return this.settings_;
    },

    /**
     * Sets the element whose focus state will determine whether
     * to respond to keybaord input.
     */
    set focusElement(value) {
      this.focusElement_ = value;
      if (this.trackView_)
        this.trackView_.focusElement = value;
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
     * @return {boolean} Whether the current view is attached to the
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

    onKeyDown_: function(e) {
      if (!this.listenToKeys_)
        return;

      if (e.keyCode === 27) { // ESC
        this.focus();
        e.preventDefault();
      }
    },

    onKeypress_: function(e) {
      if (!this.listenToKeys_)
        return;

      if (e.keyCode === '/'.charCodeAt(0)) {
        if (this.findCtl_.hasFocus())
          this.focus();
        else
          this.findCtl_.focus();
        e.preventDefault();
      } else if (e.keyCode === '?'.charCodeAt(0)) {
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
      dlg.controller.trackView = this.trackView;
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
      var oldScrollTop = this.trackViewContainer_.scrollTop;

      var selection = this.trackView_ ?
          this.trackView_.selectionOfInterest :
          new tracing.Selection();
      this.analysisEl_.selection = selection;
      this.trackViewContainer_.scrollTop = oldScrollTop;
    },

    onRequestSelectionChange_: function(e) {
      this.trackView_.selection = e.selection;
      e.stopPropagation();
    }
  };

  return {
    TimelineView: TimelineView
  };
});
