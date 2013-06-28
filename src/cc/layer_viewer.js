// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview LayerViewer coordinates graphical and analysis views of layers.
 */

base.requireStylesheet('cc.layer_viewer');

base.require('base.raf');
base.require('base.settings');
base.require('cc.constants');
base.require('cc.layer_tree_quad_stack_viewer');
base.require('tracing.analysis.util');
base.require('ui.drag_handle');

base.exportTo('cc', function() {
  var constants = cc.constants;

  /**
   * @constructor
   */
  var LayerViewer = ui.define('layer-viewer');

  LayerViewer.prototype = {
    __proto__: HTMLUnknownElement.prototype,

    decorate: function() {
      this.layerTreeQuadStackViewer_ = new cc.LayerTreeQuadStackViewer();
      this.dragBar_ = new ui.DragHandle();
      this.analysisEl_ = document.createElement('layer-viewer-analysis');

      this.dragBar_.target = this.analysisEl_;

      this.appendChild(this.layerTreeQuadStackViewer_);
      this.appendChild(this.dragBar_);
      this.appendChild(this.analysisEl_);

      this.layerTreeQuadStackViewer_.addEventListener('selectionChange',
          this.layerTreeQuadStackViewerSelectionChanged_.bind(this));
    },

    get layerTreeImpl() {
      return this.layerTreeQuadStackViewer_.layerTreeImpl;
    },

    set layerTreeImpl(newValue) {
      return this.layerTreeQuadStackViewer_.layerTreeImpl = newValue;
    },

    get selection() {
      return this.layerTreeQuadStackViewer_.selection;
    },

    set selection(newValue) {
      this.layerTreeQuadStackViewer_.selection = newValue;
    },

    layerTreeQuadStackViewerSelectionChanged_: function(event) {
      var selection = event.newValue;
      if (selection) {
        this.dragBar_.style.display = '';
        this.analysisEl_.style.display = '';
        this.analysisEl_.textContent = '';
        var analysis = selection.createAnalysis();
        this.analysisEl_.appendChild(analysis);
      } else {
        this.dragBar_.style.display = 'none';
        this.analysisEl_.style.display = 'none';
        var analysis = this.analysisEl_.firstChild;
        if (analysis)
          this.analysisEl_.removeChild(analysis);
        this.layerTreeQuadStackViewer_.style.height =
            window.getComputedStyle(this).height;
      }
    }
  };
  return {
    LayerViewer: LayerViewer
  };
});
