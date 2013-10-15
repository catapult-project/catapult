// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview LayerView coordinates graphical and analysis views of layers.
 */

base.requireStylesheet('cc.layer_view');

base.require('base.raf');
base.require('base.settings');
base.require('cc.constants');
base.require('cc.layer_tree_quad_stack_view');
base.require('cc.picture');
base.require('tracing.analysis.util');
base.require('ui.drag_handle');

base.exportTo('cc', function() {
  var constants = cc.constants;

  /**
   * @constructor
   */
  var LayerView = ui.define('layer-view');

  LayerView.prototype = {
    __proto__: HTMLUnknownElement.prototype,

    decorate: function() {
      this.layerTreeQuadStackView_ = new cc.LayerTreeQuadStackView();
      this.dragBar_ = new ui.DragHandle();
      this.analysisEl_ = document.createElement('layer-view-analysis');

      this.dragBar_.target = this.analysisEl_;

      this.appendChild(this.layerTreeQuadStackView_);
      this.appendChild(this.dragBar_);
      this.appendChild(this.analysisEl_);

      this.layerTreeQuadStackView_.addEventListener('selectionChange',
          function() {
            this.layerTreeQuadStackViewSelectionChanged_();
          }.bind(this));
      this.layerTreeQuadStackViewSelectionChanged_();
    },

    get layerTreeImpl() {
      return this.layerTreeQuadStackView_.layerTreeImpl;
    },

    set layerTreeImpl(newValue) {
      return this.layerTreeQuadStackView_.layerTreeImpl = newValue;
    },

    set whichTree(newValue) {
      return this.layerTreeQuadStackView_.whichTree = newValue;
    },

    set isRenderPassQuads(newValue) {
      return this.layerTreeQuadStackView_.isRenderPassQuads = newValue;
    },

    get selection() {
      return this.layerTreeQuadStackView_.selection;
    },

    set selection(newValue) {
      this.layerTreeQuadStackView_.selection = newValue;
    },

    regenerateContent: function() {
      this.layerTreeQuadStackView_.regenerateContent();
    },

    layerTreeQuadStackViewSelectionChanged_: function() {
      var selection = this.layerTreeQuadStackView_.selection;
      if (selection) {
        this.dragBar_.style.display = '';
        this.analysisEl_.style.display = '';
        this.analysisEl_.textContent = '';

        var layer = selection.layer;
        if (layer && layer.args && layer.args.pictures) {
          this.analysisEl_.appendChild(
              this.createPictureBtn_(layer.args.pictures));
        }

        var analysis = selection.createAnalysis();
        this.analysisEl_.appendChild(analysis);
      } else {
        this.dragBar_.style.display = 'none';
        this.analysisEl_.style.display = 'none';
        var analysis = this.analysisEl_.firstChild;
        if (analysis)
          this.analysisEl_.removeChild(analysis);
        this.layerTreeQuadStackView_.style.height =
            window.getComputedStyle(this).height;
      }
    },

    createPictureBtn_: function(pictures) {
      if (!(pictures instanceof Array))
        pictures = [pictures];

      var link = new tracing.analysis.AnalysisLink();
      link.innerText = 'View in Picture Debugger';
      link.selectionGenerator = function() {
        var layeredPicture = new cc.LayeredPicture(pictures);
        var snapshot = new cc.PictureSnapshot(layeredPicture);
        snapshot.picture = layeredPicture;

        var selection = new tracing.Selection();
        selection.push(snapshot);
        return selection;
      };
      return link;
    }
  };

  return {
    LayerView: LayerView
  };
});
