// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.requireStylesheet('cc.layer_viewer');

base.require('base.raf');
base.require('base.settings');
base.require('cc.constants');
base.require('cc.picture');
base.require('cc.selection');
base.require('tracing.analysis.util');
base.require('ui.drag_handle');
base.require('ui.overlay');
base.require('ui.info_bar');
base.require('ui.quad_stack');
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
      this.quadStack_ = new ui.QuadStack();
      this.dragBar_ = new ui.DragHandle();
      this.analysisEl_ = document.createElement('layer-viewer-analysis');

      this.dragBar_.target = this.analysisEl_;

      this.appendChild(this.controls_);
      this.appendChild(this.infoBar_);
      this.appendChild(this.quadStack_);
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

      this.showOtherLayers_ = true;
      var showOtherLayersCheckbox = ui.createCheckBox(
          this, 'showOtherLayers',
          'layerViewer.showOtherLayers', true,
          'Show other layers');
      this.controls_.appendChild(showOtherLayersCheckbox);

      this.showInvalidations_ = true;
      var showInvalidationsCheckbox = ui.createCheckBox(
          this, 'showInvalidations',
          'layerViewer.showInvalidations', true,
          'Show invalidations');
      this.controls_.appendChild(showInvalidationsCheckbox);

      this.showContents_ = true;
      var showContentsCheckbox = ui.createCheckBox(
          this, 'showContents',
          'layerViewer.showContents', true,
          'Show contents');
      this.controls_.appendChild(showContentsCheckbox);

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

      // Figure out if we can draw the quads yet. While we're at it, figure out
      // if we have any warnings we need to show.
      var infoBarMessages = [];
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
          infoBarMessages.push({
            header: 'Cannot rasterize',
            details: cc.PictureSnapshot.HowToEnableRasterizing()});
        }
        if (hasUnresolvedPictureRef) {
          infoBarMessages.push({
            header: 'Missing picture',
            details: 'Your trace didnt have pictures for every layer. ' +
                'Old chrome versions had this problem'});
        }
        if (hasMissingLayerRect) {
          infoBarMessages.push({
            header: 'Missing layer rect',
            details: 'Your trace may be corrupt or from a very old ' +
                'Chrome revision.'});
        }
        if (hasBrokenPicture) {
          infoBarMessages.push({
            header: 'Broken SkPicture',
            details: 'Your recording may be from an old Chrome version. ' +
                'The SkPicture format is not backward compatible.'});
        }
      }

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

      // Do the analysis.
      this.updateAnalysisContents_();

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

      var viewport = new ui.QuadViewViewport(
          lthiInstance.allLayersBBox, this.scale_, lthi.deviceViewportSize);

      this.quadStack_.setQuadsAndViewport(quads, viewport);
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
    LayerViewer: LayerViewer
  };
});
