// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview Graphical view of  LayerTreeImpl, with controls for
 * type of layer content shown and info bar for content-loading warnings.
 */

base.requireStylesheet('cc.layer_tree_quad_stack_viewer');

base.require('base.properties');
base.require('base.raf');
base.require('cc.constants');
base.require('cc.picture');
base.require('ui.quad_stack_viewer');
base.require('ui.info_bar');


base.exportTo('cc', function() {
  var constants = {
    // The ratio of quad stack pixels to world pixels before CSS scaling.
    QUAD_STACK_SCALE: 0.5
  };

  /**
   * @constructor
   */
  var LayerTreeQuadStackViewer = ui.define('layer-tree-quad-stack-viewer');

  LayerTreeQuadStackViewer.prototype = {
    __proto__: HTMLDivElement.prototype,

    decorate: function() {
      this.pictureAsCanvas_ = {}; // Maps picture.guid to PictureAsCanvas.
      this.quads_ = [];
      this.messages_ = [];
      this.controls_ = document.createElement('top-controls');
      this.infoBar_ = new ui.InfoBar();
      this.quadStackViewer_ = new ui.QuadStackViewer();

      this.appendChild(this.controls_);
      this.appendChild(this.infoBar_);
      this.appendChild(this.quadStackViewer_);

      var scaleSelector = ui.createSelector(
          this.quadStackViewer_, 'scale',
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
          this, 'showOtherLayers',
          'layerViewer.showOtherLayers', true,
          'Show other layers');
      this.controls_.appendChild(showOtherLayersCheckbox);

      var showInvalidationsCheckbox = ui.createCheckBox(
          this, 'showInvalidations',
          'layerViewer.showInvalidations', true,
          'Show invalidations');
      this.controls_.appendChild(showInvalidationsCheckbox);

      var showContentsCheckbox = ui.createCheckBox(
          this, 'showContents',
          'layerViewer.showContents', true,
          'Show contents');
      this.controls_.appendChild(showContentsCheckbox);
    },

    get layerTreeImpl() {
      return this.layerTreeImpl_;
    },

    set layerTreeImpl(layerTreeImpl) {
      // FIXME(pdr): We may want to clear pictureAsCanvas_ here to save memory
      //             at the cost of performance. Note that pictureAsCanvas_ will
      //             be cleared when this is destructed, but this view might
      //             live for several layerTreeImpls.
      this.layerTreeImpl_ = layerTreeImpl;
      this.selection = null;
      this.updateContents_();
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

    get selection() {
      return this.selection_;
    },

    set selection(selection) {
      base.setPropertyAndDispatchChange(this, 'selection', selection);
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
      if (!this.layerTreeImpl_)
        return;

      if (this.pictureLoadingComplete_())
        this.generateQuads_();
    },

    pictureLoadingComplete_: function() {
      // Figure out if we can draw the quads yet. While we're at it, figure out
      // if we have any warnings we need to show.
      var layers = this.layers;
      var messages = [];
      if (this.showContents) {
        var hasPendingRasterizeImage = false;
        var firstPictureError = undefined;
        var hasMissingLayerRect = false;
        var hasUnresolvedPictureRef = false;
        for (var i = 0; i < layers.length; i++) {
          var layer = layers[i];
          for (var ir = layer.pictures.length - 1; ir >= 0; ir--) {
            var picture = layer.pictures[ir];

            if (picture.idRef) {
              hasUnresolvedPictureRef = true;
              continue;
            }
            if (!picture.layerRect) {
              hasMissingLayerRect = true;
              continue;
            }

            var pictureAsCanvas = this.pictureAsCanvas_[picture.guid];
            if (!pictureAsCanvas) {
              hasPendingRasterizeImage = true;
              this.pictureAsCanvas_[picture.guid] =
                  cc.PictureAsCanvas.Pending(this);
              picture.rasterize(
                  {stopIndex: undefined},
                  function(pictureAsCanvas) {
                    var picture_ = pictureAsCanvas.picture;
                    this.pictureAsCanvas_[picture_.guid] = pictureAsCanvas;
                    this.scheduleUpdateContents_();
                  }.bind(this));
              continue;
            }
            if (pictureAsCanvas.isPending()) {
              hasPendingRasterizeImage = true;
              continue;
            }
            if (pictureAsCanvas.error) {
              if (!firstPictureError)
                firstPictureError = pictureAsCanvas.error;
              break;
            }
          }
        }
        if (hasPendingRasterizeImage)
          return false;

        if (hasUnresolvedPictureRef) {
          messages.push({
            header: 'Missing picture',
            details: 'Your trace didnt have pictures for every layer. ' +
                'Old chrome versions had this problem'});
        }
        if (hasMissingLayerRect) {
          messages.push({
            header: 'Missing layer rect',
            details: 'Your trace may be corrupt or from a very old ' +
                'Chrome revision.'});
        }
        if (firstPictureError) {
          messages.push({
            header: 'Cannot rasterize',
            details: firstPictureError});
        }
      }
      this.messages_ = messages;
      return true;
    },

    get selectedLayer() {
      if (this.selection) {
        var selectedLayerId = this.selection.associatedLayerId;
        return this.layerTreeImpl_.findLayerWithId(selectedLayerId);
      }
    },

    get layers() {
      var layers = this.layerTreeImpl.renderSurfaceLayerList;
      if (!this.showOtherLayers) {
        var selectedLayer = this.selectedLayer;
        if (selectedLayer)
          layers = [selectedLayer];
      }
      return layers;
    },

    appendImageQuads_: function(layer, layerQuad) {
      // Generate image quads for the layer
      for (var ir = layer.pictures.length - 1; ir >= 0; ir--) {
        var picture = layer.pictures[ir];
        if (!picture.layerRect)
          continue;

        var unitRect = picture.layerRect.asUVRectInside(layer.bounds);
        var iq = layerQuad.projectUnitRect(unitRect);

        var pictureAsCanvas = this.pictureAsCanvas_[picture.guid];
        if (this.showContents && pictureAsCanvas.canvas)
          iq.canvas = pictureAsCanvas.canvas;
        else
          iq.canvas = undefined;

        iq.stackingGroupId = layerQuad.stackingGroupId;
        this.quads_.push(iq);
      }
    },

    appendInvalidationQuads_: function(layer, layerQuad) {
      // Generate the invalidation rect quads.
      for (var ir = 0; ir < layer.invalidation.rects.length; ir++) {
        var rect = layer.invalidation.rects[ir];
        var unitRect = rect.asUVRectInside(layer.bounds);
        var iq = layerQuad.projectUnitRect(unitRect);
        iq.backgroundColor = 'rgba(255, 0, 0, 0.1)';
        iq.borderColor = 'rgba(255, 0, 0, 1)';
        iq.stackingGroupId = layerQuad.stackingGroupId;
        this.quads_.push(iq);
      }
    },

    appendSelectionQuads_: function(layer, layerQuad) {
      var selection = this.selection;
      var quad = this.layerTreeImpl_.whichTree == constants.ACTIVE_TREE ?
          selection.quadIfActive : selection.quadIfPending;
      if (!quad)
        return [];

      var colorId = tracing.getStringColorId(selection.title);
      colorId += tracing.getColorPaletteHighlightIdBoost();

      var color = base.Color.fromString(tracing.getColorPalette()[colorId]);

      var quadForDrawing = quad.clone();
      quadForDrawing.backgroundColor = color.withAlpha(0.5).toString();
      quadForDrawing.borderColor = color.withAlpha(1.0).darken().toString();
      quadForDrawing.stackingGroupId = layerQuad.stackingGroupId;
      return [quadForDrawing];
    },

    generateQuads_: function() {
      this.updateContentsPending_ = false;

      // Generate the quads for the view.
      var layers = this.layers;
      this.quads_ = [];
      for (var i = 0; i < layers.length; i++) {
        var layer = layers[i];

        var layerQuad = layer.layerQuad.clone();
        layerQuad.borderColor = 'rgba(0,0,0,0.75)';
        layerQuad.stackingGroupId = i;
        if (this.showOtherLayers && this.selectedLayer == layer)
          layerQuad.upperBorderColor = 'rgb(156,189,45)';

        this.appendImageQuads_(layer, layerQuad);

        if (this.showInvalidations) {
          this.appendInvalidationQuads_(layer, layerQuad);
        }

        // Push the layer quad last.
        this.quads_.push(layerQuad);

        if (this.selectedLayer === layer) {
          this.appendSelectionQuads_(layer, layerQuad);
        }
      }
      var lthi = this.layerTreeImpl_.layerTreeHostImpl;
      var lthiInstance = lthi.objectInstance;
      var worldViewportRect = base.Rect.FromXYWH(0, 0,
          lthi.deviceViewportSize.width, lthi.deviceViewportSize.height);
      this.quadStackViewer_.quadStack.initialize(
          lthiInstance.allLayersBBox.asRect(), worldViewportRect);

      this.quadStackViewer_.quadStack.quads = this.quads_;

      this.updateInfoBar_(this.messages_);
    },

    updateInfoBar_: function(infoBarMessages) {
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
          overlay.obeyCloseEvents = true;
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
    LayerTreeQuadStackViewer: LayerTreeQuadStackViewer
  };
});
