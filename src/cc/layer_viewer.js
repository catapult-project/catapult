// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.requireStylesheet('cc.layer_viewer');

base.require('base.raf');
base.require('cc.constants');
base.require('cc.picture');
base.require('tracing.analysis.generic_object_view');
base.require('tracing.analysis.util');
base.require('ui.quad_stack');

base.exportTo('cc', function() {
  var constants = cc.constants;
  var tsRound = tracing.analysis.tsRound;

  /**
   * @constructor
   */
  var LayerViewer = ui.define('layer-viewer');

  LayerViewer.prototype = {
    __proto__: HTMLUnknownElement.prototype,

    decorate: function() {
      this.layer_ = undefined;

      this.controls_ = document.createElement('top-controls');
      this.quadStack_ = new ui.QuadStack();
      this.appendChild(this.controls_);
      this.appendChild(this.quadStack_);

      this.statusEL_ = this.controls_.appendChild(ui.createSpan(''));
      this.statusEL_.textContent = 'Selected layer';
      if (!cc.PictureSnapshot.CanRasterize()) {
        var tmp = this.statusEL_.appendChild(ui.createSpan('[WARNING!!!]'));
        tmp.style.paddingLeft = '10px';
        tmp.style.paddingRight = '10px';
        tmp.style.color = 'red';
        tmp.style.fontWeight = 'bold';
        tmp.title = cc.PictureSnapshot.HowToEnableRasterizing();
      }

      this.warningEL_ = this.controls_.appendChild(ui.createSpan(''));
      this.warningEL_.textContent = '';

      this.scale_ = 0.0625;
      var scaleSelector = ui.createSelector(
          this, 'scale',
          [{label: '6.25%', value: 0.0625},
           {label: '12.5%', value: 0.125},
           {label: '25%', value: 0.25},
           {label: '50%', value: 0.5},
           {label: '75%', value: 0.75},
           {label: '100%', value: 1},
           {label: '200%', value: 2}
          ]);
      scaleSelector.selectedIndex = 3;
      this.scale_ = 0.5;
      this.controls_.appendChild(scaleSelector);

      this.showOtherLayers_ = true;
      var showOtherLayersCheckbox = ui.createCheckBox(
          this, 'showOtherLayers', 'Show other layers');
      this.controls_.appendChild(showOtherLayersCheckbox);

      this.showInvalidations_ = true;
      var showInvalidationsCheckbox = ui.createCheckBox(
          this, 'showInvalidations', 'Show invalidations');
      this.controls_.appendChild(showInvalidationsCheckbox);

      this.showContents_ = true;
      var showContentsCheckbox = ui.createCheckBox(
          this, 'showContents', 'Show contents');
      this.controls_.appendChild(showContentsCheckbox);
    },

    get layer() {
      return this.layer_;
    },

    set layer(layer) {
      this.layer_ = layer;
      this.scheduleUpdateContents_();
    },

    get scale() {
      return this.scale_;
    },

    set scale(scale) {
      this.scale_ = scale;
      this.scheduleUpdateContents_();
    },

    get showOtherLayers() {
      return this.showOtherLayers_;
    },

    set showOtherLayers(show) {
      this.showOtherLayers_ = show;
      this.updateContents_();
    },

    get showContents() {
      return this.showContents_;
    },

    set showContents(show) {
      this.showContents_ = show;
      this.updateContents_();
    },

    get showInvalidations() {
      return this.showInvalidations_;
    },

    set showInvalidations(show) {
      this.showInvalidations_ = show;
      this.updateContents_();
    },

    set highlightedTile(tileSnapshot) {
      this.highlightedTile_ = tileSnapshot;
      this.updateContents_();
    },

    scheduleUpdateContents_: function() {
      if (this.updateContentsPending_)
        return;
      this.updateContentsPending_ = true;
      base.requestAnimationFrameInThisFrameIfPossible(
        this.updateContents_, this);
    },

    updateContents_: function() {
      this.updateContentsPending_ = false;
      this.warningEL_.textContent = '';

      if (!this.layer_) {
        this.quadStack_.quads = [];
        return;
      }

      var selectedLayer = this.layer_;
      var showOtherLayers = this.showOtherLayers_;

      var layerTreeImpl = selectedLayer.layerTreeImpl;
      var lthi = layerTreeImpl.layerTreeHostImpl;
      var lthiInstance = lthi.objectInstance;
      var layers = [];
      if (showOtherLayers)
        layers = layerTreeImpl.renderSurfaceLayerList;
      else
        layers = [selectedLayer];

      // Figure out if we can draw the quads yet...
      if (this.showContents_) {
        var hadMissingPicture = false;
        for (var i = 0; i < layers.length; i++) {
          var layer = layers[i];
          for (var ir = layer.pictures.length - 1; ir >= 0; ir--) {
            var picture = layer.pictures[ir];
            if (picture.image ||
                !cc.PictureSnapshot.CanRasterize() ||
                !picture.layerRect)
              continue;
            picture.beginRenderingImage(
                this.scheduleUpdateContents_.bind(this));
            hadMissingPicture = true;
          }
        }
        if (hadMissingPicture)
          return;
      }

      // Generate the quads for the view.
      var quads = [];
      for (var i = 0; i < layers.length; i++) {
        var layer = layers[i];
        var layerQuad;
        layerQuad = layer.layerQuad.clone();

        // Generate image quads for the layer
        var hasMissing = false;
        for (var ir = layer.pictures.length - 1; ir >= 0; ir--) {
          var picture = layer.pictures[ir];
          if (!picture.layerRect) {
            hasMissing = true;
            continue;
          }
          var unitRect = picture.layerRect.asUVRectInside(layer.bounds);
          var iq = layerQuad.projectUnitRect(unitRect);

          if (picture.image && this.showContents_)
            iq.backgroundImage = picture.image;
          else
            iq.backgroundColor = 'rgba(0,0,0,0.1)';

          iq.stackingGroupId = i;
          quads.push(iq);
        }

        if (hasMissing)
          this.warningEL_.textContent = 'Missing pictures';

        // Generate the invalidation rect quads.
        if (this.showInvalidations_) {
          for (var ir = 0; ir < layer.invalidation.rects.length; ir++) {
            var rect = layer.invalidation.rects[ir];
            var unitRect = rect.asUVRectInside(layer.bounds);
            var iq = layerQuad.projectUnitRect(unitRect);
            iq.backgroundColor = 'rgba(255, 0, 0, 0.1)';
            iq.borderColor = 'rgba(255, 0, 0, 1)';
            iq.stackingGroupId = i;
            quads.push(iq);
          }
        }

        // Push the layer quad last.
        layerQuad.borderColor = 'rgba(0,0,0,0.75)';
        layerQuad.stackingGroupId = i;
        quads.push(layerQuad);
        if (selectedLayer == layer && showOtherLayers)
          layerQuad.upperBorderColor = 'rgb(156,189,45)';
      }

      if (this.highlightedTile_) {
        var whichTree = layerTreeImpl.whichTree;
        var priority = whichTree == constants.ACTIVE_TREE ?
            this.highlightedTile_.args.activePriority :
            this.highlightedTile_.args.pendingPriority;
        var quad = priority.currentScreenQuad;
        var quadForDrawing = quad.clone();
        quadForDrawing.backgroundColor = 'rgba(0, 255, 0, 0.2)';
        quadForDrawing.borderColor = 'rgba(0, 255, 0, 1)';
        quadForDrawing.stackingGroupId = i;
        quads.push(quadForDrawing);
      }

      this.quadStack_.quads = quads;
      this.quadStack_.viewport = new ui.QuadViewViewport(
          lthiInstance.allLayersBBox, this.scale_);
      this.quadStack_.deviceViewportSizeForFrame = lthi.deviceViewportSize;
    }
  };

  return {
    LayerViewer: LayerViewer
  };
});
