// Copyright (c) 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

tvcm.require('tvcm.range');

tvcm.requireStylesheet('tracing.timeline_view_side_panel');

tvcm.exportTo('tracing', function() {
  /**
   * @constructor
   */
  var TimelineViewSidePanel = tvcm.ui.define('x-timeline-view-panel');

  var panelConstructors = [];

  TimelineViewSidePanel.getPanelConstructors = function() {
    return panelConstructors;
  }

  TimelineViewSidePanel.registerPanelSubtype = function(panelConstructor) {
    if (panelConstructor.supportsModel === undefined)
      throw new Error('Panel constructors must provide a ' +
                      'supportsModel function');
    if (panelConstructor.textLabel === undefined)
      throw new Error('Panel constructors must provide a ' +
                      'textLabel strig');
    panelConstructors.push(panelConstructor);
  }

  TimelineViewSidePanel.unregisterPanelSubtype = function(panelConstructor) {
    var i = panelConstructors.indexOf(panelConstructor);
    if (i == -1)
      throw new Error('Panel not registered');
    panelConstructors.splice(i, 1);
  }

  TimelineViewSidePanel.prototype = {
    __proto__: HTMLUnknownElement.prototype,

    decorate: function() {
    }
  };

  /**
   * @constructor
   */
  var TimelineViewSidePanelContainer = tvcm.ui.define(
      'x-timeline-view-side-panel-container');

  TimelineViewSidePanelContainer.prototype = {
    __proto__: HTMLUnknownElement.prototype,

    decorate: function() {
      this.activePanelContainer_ = document.createElement(
          'active-panel-container');
      this.tabStrip_ = document.createElement('tab-strip');
      this.appendChild(this.activePanelContainer_);
      this.appendChild(this.tabStrip_);
      this.model_ = undefined;
      this.rangeOfInterest_ = new tvcm.Range();
    },

    get model() {
      return model_;
    },

    set model(model) {
      this.model_ = model;
      this.updateContents_();
    },

    get expanded() {
      this.hasAttribute('expanded');
    },

    get activePanel() {
      if (this.activePanelContainer_.children.length === 0)
        return undefined;
      return this.activePanelContainer_.children[0];
    },

    get activePanelConstructor() {
      if (this.activePanel)
        return this.activePanel.constructor;
      return undefined;
    },

    set activePanelConstructor(panelConstructor) {
      if (this.model_ === undefined)
        throw new Error('Cannot activate panel without a model');
      if (panelConstructor && !panelConstructor.supportsModel(this.model_))
        throw new Error('Cannot activate panel: it doesn\'t ' +
                        'support this model');

      if (this.activePanelConstructor) {
        this.getLabelForConstructor_(
            this.activePanelConstructor).removeAttribute('selected');
      }
      this.activePanelContainer_.textContent = '';

      if (panelConstructor === undefined) {
        this.removeAttribute('expanded');
        return;
      }

      var panelEl = new panelConstructor();
      panelEl.rangeOfInterest = this.rangeOfInterest_;
      panelEl.selection = this.selection_;
      panelEl.model = this.model_;
      this.activePanelContainer_.appendChild(panelEl);

      this.getLabelForConstructor_(
          panelConstructor).setAttribute('selected', true);

      this.setAttribute('expanded', true);
    },

    getLabelForConstructor_: function(panelConstructor) {
      for (var i = 0; i < this.tabStrip_.children.length; i++) {
        if (this.tabStrip_.children[i].panelConstructor == panelConstructor)
          return this.tabStrip_.children[i];
      }
      return undefined;
    },

    updateContents_: function() {
      var previouslyActivePanelConstructor = this.activePanelConstructor;

      this.tabStrip_.textContent = '';
      var supportedPanelConstructors = [];

      panelConstructors.forEach(function(panelConstructor) {
        var labelEl = document.createElement('tab-strip-label');
        labelEl.textContent = panelConstructor.textLabel;
        labelEl.panelConstructor = panelConstructor;

        var supported = panelConstructor.supportsModel(this.model_);
        if (this.model_ && supported.supported) {
          supportedPanelConstructors.push(panelConstructor);
          labelEl.setAttribute('enabled', true);
          labelEl.addEventListener('click', function() {
            if (this.activePanelConstructor === panelConstructor)
              this.activePanelConstructor = undefined;
            else
              this.activePanelConstructor = panelConstructor;
          }.bind(this));
        } else {
          labelEl.title = 'Not supported for the current trace: ' +
              supported.reason;
        }
        this.tabStrip_.appendChild(labelEl);
      }, this);


      // Restore the active panel, or collapse
      if (previouslyActivePanelConstructor &&
          supportedPanelConstructors.indexOf(
              previouslyActivePanelConstructor) != -1) {
        this.activePanelConstructor = previouslyActivePanelConstructor;
        this.setAttribute('expanded', true);
      } else {
        this.activePanelContainer_.textContent = '';
        this.removeAttribute('expanded');
      }
    },

    get selection() {
      return selection_;
    },

    set selection(selection) {
      this.selection_ = selection;
      if (this.activePanel)
        this.activePanel.selection = selection;
    },

    get rangeOfInterest() {
      return this.rangeOfInterest_;
    },

    set rangeOfInterest(range) {
      if (range == undefined)
        throw new Error('Must not be undefined');
      this.rangeOfInterest_ = range;
      if (this.activePanel)
        this.activePanel.rangeOfInterest = range;
    }
  };



  return {
    TimelineViewSidePanel: TimelineViewSidePanel,
    TimelineViewSidePanelContainer: TimelineViewSidePanelContainer
  };
});
