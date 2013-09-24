// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview View visualizes TRACE_EVENT events using the
 * tracing.Timeline component and adds in selection summary and control buttons.
 */
base.requireStylesheet('ui.trace_viewer');
base.requireStylesheet('tracing.timeline_view');
base.requireTemplate('tracing.timeline_view');

base.require('base.utils');
base.require('base.settings');
base.require('tracing.analysis.analysis_view');
base.require('tracing.find_control');
base.require('tracing.timeline_track_view');
base.require('ui.dom_helpers');
base.require('ui.overlay');
base.require('ui.drag_handle');

base.require('tracing.analysis.cpu_slice_view');
base.require('tracing.analysis.thread_time_slice_view');

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

      this.findCtl_ = new tracing.FindControl();
      this.findCtl_.controller = new tracing.FindController();

      this.showFlowEvents_ = false;
      this.rightControls.appendChild(ui.createCheckBox(
          this, 'showFlowEvents',
          'tracing.TimelineView.showFlowEvents', false,
          'Flow events'));

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
      document.addEventListener('keydown', this.onKeyDown_.bind(this), true);
      document.addEventListener('keypress', this.onKeypress_.bind(this), true);

      this.dragEl_.target = this.analysisEl_;
    },

    get showFlowEvents() {
      return this.showFlowEvents_;
    },

    set showFlowEvents(showFlowEvents) {
      this.showFlowEvents_ = showFlowEvents;
      if (!this.timeline_)
        return;
      this.timeline_.viewport.showFlowEvents = showFlowEvents;
    },

    createHelpButton_: function() {
      var node = base.instantiateTemplate('#help-btn-template');
      var showEl = node.querySelector('.view-help-button');
      var helpTextEl = node.querySelector('.view-help-text');

      var dlg = new ui.Overlay();
      dlg.title = 'chrome://tracing Help';
      dlg.classList.add('view-help-overlay');
      dlg.appendChild(node);

      function onClick(e) {
        dlg.visible = !dlg.visible;

        var mod = base.isMac ? 'cmd ' : 'ctrl';
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
      var node = base.instantiateTemplate('#metadata-btn-template');
      var showEl = node.querySelector('.view-metadata-button');
      var textEl = node.querySelector('.info-button-text');

      var dlg = new ui.Overlay();
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
        this.timeline_.viewport.showFlowEvents = this.showFlowEvents;
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
          this.timeline_.selectionOfInterest :
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
