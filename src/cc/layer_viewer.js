// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';
/**
 * @fileoverview LayerViewer coordinates graphical and analysis views of layers
 */

base.requireStylesheet('cc.layer_viewer');

base.require('base.raf');
base.require('base.settings');
base.require('cc.constants');
base.require('cc.picture');
base.require('cc.selection');
base.require('cc.quad_stack_viewer');
base.require('tracing.analysis.util');
base.require('ui.drag_handle');
base.require('ui.overlay');
base.require('ui.info_bar');
base.require('ui.dom_helpers');

base.exportTo('cc', function() {
  var constants = cc.constants;

  /**
   * @constructor
   */
  var LayerViewer = ui.define('layer-viewer');

  LayerViewer.prototype = {
    __proto__: HTMLUnknownElement.prototype,

    decorate: function() {
      this.layerTreeImpl_ = undefined;
      this.selection_ = undefined;

      this.controls_ = document.createElement('top-controls');
      this.infoBar_ = new ui.InfoBar();
      this.quadStackViewer_ = new cc.QuadStackViewer();
      this.dragBar_ = new ui.DragHandle();
      this.analysisEl_ = document.createElement('layer-viewer-analysis');

      this.dragBar_.target = this.analysisEl_;

      this.appendChild(this.controls_);
      this.appendChild(this.infoBar_);
      this.appendChild(this.quadStackViewer_);
      this.appendChild(this.dragBar_);
      this.appendChild(this.analysisEl_);

      var scaleSelector = ui.createSelector(
          this, 'scale',
          'layerViewer.scale', 0.375,
          [{label: '6.25%', value: 0.0625},
           {label: '12.5%', value: 0.125},
           {label: '25%', value: 0.25},
           {label: '37.5%', value: 0.375},
           {label: '50%', value: 0.5},
           {label: '75%', value: 0.75},
           {label: '100%', value: 1},
           {label: '200%', value: 2}
          ]);
      this.controls_.appendChild(scaleSelector);

      var showOtherLayersCheckbox = ui.createCheckBox(
          this.quadStackViewer_, 'showOtherLayers',
          'layerViewer.showOtherLayers', true,
          'Show other layers');
      this.controls_.appendChild(showOtherLayersCheckbox);

      var showInvalidationsCheckbox = ui.createCheckBox(
          this.quadStackViewer_, 'showInvalidations',
          'layerViewer.showInvalidations', true,
          'Show invalidations');
      this.controls_.appendChild(showInvalidationsCheckbox);

      var showContentsCheckbox = ui.createCheckBox(
          this.quadStackViewer_, 'showContents',
          'layerViewer.showContents', true,
          'Show contents');
      this.controls_.appendChild(showContentsCheckbox);

      this.quadStackViewer_.addEventListener('selectionChange',
          this.updateAnalysisContents_.bind(this));
      this.quadStackViewer_.addEventListener('messagesChange',
          this.onInfoBarMessages_.bind(this));
    },

    get layerTreeImpl() {
      return this.quadStackViewer_.layerTreeImpl;
    },

    set layerTreeImpl(layerTreeImpl) {
      this.quadStackViewer_.layerTreeImpl = layerTreeImpl;
    },

    updateAnalysisContents_: function() {
      if (this.selection_) {
        this.dragBar_.style.display = '';
        this.analysisEl_.style.display = '';
        this.analysisEl_.textContent = '';
        var analysis = this.selection_.createAnalysis();
        this.analysisEl_.appendChild(analysis);
      } else {
        this.dragBar_.style.display = 'none';
        this.analysisEl_.style.display = 'none';
        this.analysisEl_.textContent = '';
      }
    },

    onInfoBarMessages_: function(event) {
      var infoBarMessages = event.newValue;
      if (infoBarMessages.length) {
        this.infoBar_.removeAllButtons();
        this.infoBar_.message = 'Some problems were encountered...';
        this.infoBar_.addButton('More info...', function() {
          var overlay = new ui.Overlay();
          overlay.textContent = '';
          infoBarMessages.forEach(function(message) {
            var title = document.createElement('h3');
            title.textContent = message.header;

            var details = document.createElement('div');
            details.textContent = message.details;

            overlay.appendChild(title);
            overlay.appendChild(details);
          });
          overlay.visible = true;
          overlay.autoClose = true;
        });
        this.infoBar_.visible = true;
      } else {
        this.infoBar_.removeAllButtons();
        this.infoBar_.message = '';
        this.infoBar_.visible = false;
      }
    }
  };

  return {
    LayerViewer: LayerViewer
  };
});
