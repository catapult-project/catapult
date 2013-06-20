// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';
/**
 * @fileoverview QuadStackViewer controls the content and
*    viewing angle a QuadStack.
 */

base.requireStylesheet('cc.layer_viewer');

base.require('base.raf');
base.require('cc.constants');
base.require('cc.picture');
base.require('cc.selection');
base.require('ui.overlay');
base.require('ui.info_bar');
base.require('ui.quad_stack');
base.require('ui.dom_helpers');

base.exportTo('cc', function() {
  var constants = cc.constants;

  /**
   * @constructor
   */
  var QuadStackViewer = ui.define('quad-stack-viewer');

  QuadStackViewer.prototype = {
    __proto__: HTMLUnknownElement.prototype,

    decorate: function() {
      this.layerTreeImpl_ = undefined;
      this.selection_ = undefined;

      this.showInvalidations_ = true;
      this.showOtherLayers_ = true;
      this.showContents_ = true;

      this.quadStack_ = new ui.QuadStack();
      this.appendChild(this.quadStack_);

      this.camera_ = new ui.Camera(this.quadStack_);

      this.scheduleUpdateContents_();
    },

    get layerTreeImpl() {
      return layerTreeImpl_;
    },

    set layerTreeImpl(layerTreeImpl) {
      this.layerTreeImpl_ = layerTreeImpl;
      this.scheduleUpdateContents_();
    },

    get scale() {
      return this.scale_;
    },

    set scale(scale) {
      this.scale_ = scale;
      base.Settings.set('layer_viewer.scale', this.scale_, 'cc');
      if (this.quadStack_.viewport)
        this.quadStack_.viewport.scale = scale;
      else
        this.scheduleUpdateContents_();
    },

    get showOtherLayers() {
      return this.showOtherLayers_;
    },

    set showOtherLayers(show) {
      this.showOtherLayers_ = show;
      this.scheduleUpdateContents_();
    },

    get showContents() {
      return this.showContents_;
    },

    set showContents(show) {
      this.showContents_ = show;
      this.scheduleUpdateContents_();
    },

    get showInvalidations() {
      return this.showInvalidations_;
    },

    set showInvalidations(show) {
      this.showInvalidations_ = show;
      this.scheduleUpdateContents_();
    },

    get messages() {
      return this.messages_;
    },

    set messages(newValue) {
      base.setPropertyAndDispatchChange(this, 'messages', newValue);
    },

    set selection(selection) {
      this.selection_ = selection;
      this.scheduleUpdateContents_();
    },

    scheduleUpdateContents_: function() {
      if (this.updateContentsPending_)
        return;
      this.updateContentsPending_ = true;
      base.requestAnimationFrameInThisFrameIfPossible(
          this.updateContents_, this);
    },

    readyToDraw_: function(layers) {
      // Figure out if we can draw the quads yet. While we're at it, figure out
      // if we have any warnings we need to show.
      var messages = [];
      if (this.showContents_) {
        var hasPendingRasterizeImage = false;
        var hasBrokenPicture = false;
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
            if (picture.image)
              continue;
            if (!picture.canRasterizeImage) {
              hasBrokenPicture = true;
              continue;
            }
            picture.beginRasterizingImage(
                this.scheduleUpdateContents_.bind(this));
            hasPendingRasterizeImage = true;
          }
        }
        if (hasPendingRasterizeImage)
          return;

        if (!cc.PictureSnapshot.CanRasterize()) {
          // In this case, broken pictures are just the result of not being able
          // to rasterize at all.
          hasBrokenPicture = false;
          messages.push({
            header: 'Cannot rasterize',
            details: cc.PictureSnapshot.HowToEnableRasterizing()});
        }
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
        if (hasBrokenPicture) {
          messages.push({
            header: 'Broken SkPicture',
            details: 'Your recording may be from an old Chrome version. ' +
                'The SkPicture format is not backward compatible.'});
        }
      }
      this.messages = messages;
      return true;
    },

    updateContents_: function() {
      this.updateContentsPending_ = false;

      if (!this.layerTreeImpl_) {
        this.quadStack_.quads = [];
        this.updateAnalysisContents_();
        return;
      }
      var layerTreeImpl = this.layerTreeImpl_;
      var lthi = layerTreeImpl.layerTreeHostImpl;
      var lthiInstance = lthi.objectInstance;

      var selectedLayerId = this.selection_ ?
          this.selection_.associatedLayerId : undefined;
      var selectedLayer;
      if (selectedLayerId !== undefined)
        selectedLayer = layerTreeImpl.findLayerWithId(selectedLayerId);

      var showOtherLayers = this.showOtherLayers_;

      var layers = [];
      if (showOtherLayers) {
        layers = layerTreeImpl.renderSurfaceLayerList;
      } else {
        if (selectedLayer)
          layers = [selectedLayer];
        else
          layers = layerTreeImpl.renderSurfaceLayerList;
      }

      if (!this.readyToDraw_(layers))
        return;

      // Generate the quads for the view.
      var quads = [];
      for (var i = 0; i < layers.length; i++) {
        var layer = layers[i];
        var layerQuad;
        layerQuad = layer.layerQuad.clone();

        // Generate image quads for the layer
        for (var ir = layer.pictures.length - 1; ir >= 0; ir--) {
          var picture = layer.pictures[ir];
          if (!picture.layerRect)
            continue;

          var unitRect = picture.layerRect.asUVRectInside(layer.bounds);
          var iq = layerQuad.projectUnitRect(unitRect);

          if (picture.image && this.showContents_)
            iq.backgroundImage = picture.image;
          else
            iq.backgroundColor = 'rgba(0,0,0,0.1)';

          iq.stackingGroupId = i;
          quads.push(iq);
        }

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

      if (this.selection_)
        this.appendQuadsForSelection_(
            quads, layerTreeImpl, this.selection_, i);

      var allLayersRect = lthiInstance.allLayersBBox.asRect();
      var viewport = new ui.QuadViewViewport(
          allLayersRect, this.scale_, lthi.deviceViewportSize);

      this.quadStack_.setQuadsAndViewport(quads, viewport);

      base.dispatchSimpleEvent(this, 'selectionChange', true);
    },

    appendQuadsForSelection_: function(
        quads, layerTreeImpl,
        selection, stackingGroupId) {
      var quad = layerTreeImpl.whichTree == constants.ACTIVE_TREE ?
          selection.quadIfActive : selection.quadIfPending;
      if (!quad)
        return;

      var colorId = tracing.getStringColorId(selection.title);
      colorId += tracing.getColorPaletteHighlightIdBoost();

      var color = base.Color.fromString(tracing.getColorPalette()[colorId]);

      var quadForDrawing = quad.clone();
      quadForDrawing.backgroundColor = color.withAlpha(0.5).toString();
      quadForDrawing.borderColor = color.withAlpha(1.0).darken().toString();
      quadForDrawing.stackingGroupId = stackingGroupId;
      quads.push(quadForDrawing);
    }
  };

  return {
    QuadStackViewer: QuadStackViewer
  };
});
