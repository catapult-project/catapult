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
base.require('cc.tile');
base.require('cc.debug_colors');
base.require('ui.quad_stack_viewer');
base.require('ui.info_bar');


base.exportTo('cc', function() {

  var TILE_HEATMAP_TYPE = {};
  TILE_HEATMAP_TYPE.NONE = 0;
  TILE_HEATMAP_TYPE.SCHEDULED_PRIORITY = 1;
  TILE_HEATMAP_TYPE.DISTANCE_TO_VISIBLE = 2;
  TILE_HEATMAP_TYPE.TIME_TO_VISIBLE = 3;

  /**
   * @constructor
   */
  var LayerTreeQuadStackViewer = ui.define('layer-tree-quad-stack-viewer');

  LayerTreeQuadStackViewer.prototype = {
    __proto__: HTMLDivElement.prototype,

    decorate: function() {
      this.pictureAsImageData_ = {}; // Maps picture.guid to PictureAsImageData.
      this.quads_ = [];
      this.messages_ = [];
      this.controls_ = document.createElement('top-controls');
      this.infoBar_ = new ui.InfoBar();
      this.quadStackViewer_ = new ui.QuadStackViewer();

      var m = ui.MOUSE_SELECTOR_MODE;
      var mms = this.quadStackViewer_.mouseModeSelector;
      mms.settingsKey = 'cc.layerTreeQuadStackViewer.mouseModeSelector';
      mms.setKeyCodeForMode(m.PANSCAN, 'z'.charCodeAt(0));

      this.appendChild(this.controls_);
      this.appendChild(this.infoBar_);
      this.appendChild(this.quadStackViewer_);

      this.tileRectsSelector_ = ui.createSelector(
          this, 'howToShowTiles',
          'layerViewer.howToShowTiles', 'none',
          [{label: 'None', value: 'none'},
           {label: 'Coverage Rects', value: 'coverage'}
          ]);
      this.controls_.appendChild(this.tileRectsSelector_);

      var tileHeatmapText = ui.createSpan({
        textContent: 'Tile heatmap:'
      });
      this.controls_.appendChild(tileHeatmapText);

      var tileHeatmapSelector = ui.createSelector(
          this, 'tileHeatmapType',
          'layerViewer.tileHeatmapType', TILE_HEATMAP_TYPE.NONE,
          [{label: 'None',
            value: TILE_HEATMAP_TYPE.NONE},
           {label: 'Scheduled Priority',
            value: TILE_HEATMAP_TYPE.SCHEDULED_PRIORITY},
           {label: 'Distance to Visible',
            value: TILE_HEATMAP_TYPE.DISTANCE_TO_VISIBLE},
           {label: 'Time to Visible',
            value: TILE_HEATMAP_TYPE.TIME_TO_VISIBLE}
          ]);
      this.controls_.appendChild(tileHeatmapSelector);

      var showOtherLayersCheckbox = ui.createCheckBox(
          this, 'showOtherLayers',
          'layerViewer.showOtherLayers', true,
          'Other layers');
      showOtherLayersCheckbox.title =
          'When checked, show all layers, selected or not.';
      this.controls_.appendChild(showOtherLayersCheckbox);

      var showInvalidationsCheckbox = ui.createCheckBox(
          this, 'showInvalidations',
          'layerViewer.showInvalidations', true,
          'Invalidations');
      showInvalidationsCheckbox.title =
          'When checked, compositing invalidations are highlighted in red';
      this.controls_.appendChild(showInvalidationsCheckbox);

      var showContentsCheckbox = ui.createCheckBox(
          this, 'showContents',
          'layerViewer.showContents', true,
          'Contents');
      showContentsCheckbox.title =
          'When checked, show the rendered contents inside the layer outlines';
      this.controls_.appendChild(showContentsCheckbox);
    },

    get layerTreeImpl() {
      return this.layerTreeImpl_;
    },

    set layerTreeImpl(layerTreeImpl) {
      // FIXME(pdr): We may want to clear pictureAsImageData_ here to save
      //             memory at the cost of performance. Note that
      //             pictureAsImageData_ will be cleared when this is
      //             destructed, but this view might live for several
      //             layerTreeImpls.
      this.layerTreeImpl_ = layerTreeImpl;
      this.selection = null;
      this.updateTilesSelector_();
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

    get howToShowTiles() {
      return this.howToShowTiles_;
    },

    set howToShowTiles(val) {
      // Make sure val is something we expect.
      console.assert(
          (val === 'none') ||
          (val === 'coverage') ||
          !isNaN(parseFloat(val)));

      this.howToShowTiles_ = val;
      this.updateContents_();
    },

    get tileHeatmapType() {
      return this.tileHeatmapType_;
    },

    set tileHeatmapType(val) {
      this.tileHeatmapType_ = val;
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

    updateTilesSelector_: function() {
      var data = [{label: 'None', value: 'none'},
                  {label: 'Coverage Rects', value: 'coverage'}];

      // First get all of the scales information from LTHI.
      var lthi = this.layerTreeImpl_.layerTreeHostImpl;
      var scaleNames = lthi.getContentsScaleNames();
      for (var scale in scaleNames) {
        data.push({
          label: 'Scale ' + scale + ' (' + scaleNames[scale] + ')',
          value: scale
        });
      }

      // Then create a new selector and replace the old one.
      var new_selector = ui.createSelector(
          this, 'howToShowTiles',
          'layerViewer.howToShowTiles', 'none',
          data);
      this.controls_.replaceChild(new_selector, this.tileRectsSelector_);
      this.tileRectsSelector_ = new_selector;
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

            var pictureAsImageData = this.pictureAsImageData_[picture.guid];
            if (!pictureAsImageData) {
              hasPendingRasterizeImage = true;
              this.pictureAsImageData_[picture.guid] =
                  cc.PictureAsImageData.Pending(this);
              picture.rasterize(
                  {stopIndex: undefined},
                  function(pictureImageData) {
                    var picture_ = pictureImageData.picture;
                    this.pictureAsImageData_[picture_.guid] = pictureImageData;
                    this.scheduleUpdateContents_();
                  }.bind(this));
              continue;
            }
            if (pictureAsImageData.isPending()) {
              hasPendingRasterizeImage = true;
              continue;
            }
            if (pictureAsImageData.error) {
              if (!firstPictureError)
                firstPictureError = pictureAsImageData.error;
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

        var pictureData = this.pictureAsImageData_[picture.guid];
        if (this.showContents && pictureData && pictureData.imageData)
          iq.imageData = pictureData.imageData;
        else
          iq.imageData = undefined;

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

    appendTileCoverageRectQuads_: function(layer, layerQuad, heatmapType) {
      if (!layer.tileCoverageRects)
        return;

      var tiles = [];
      for (var ct = 0; ct < layer.tileCoverageRects.length; ++ct) {
        var tile = layer.tileCoverageRects[ct].tile;
        if (tile !== undefined)
          tiles.push(tile);
      }

      var heatmapColors = this.computeHeatmapColors_(tiles, heatmapType);
      var heatIndex = 0;

      for (var ct = 0; ct < layer.tileCoverageRects.length; ++ct) {
        var rect = layer.tileCoverageRects[ct].geometryRect;
        var tile = layer.tileCoverageRects[ct].tile;

        var unitRect = rect.asUVRectInside(layer.bounds);
        var quad = layerQuad.projectUnitRect(unitRect);

        quad.backgroundColor = 'rgba(0, 0, 0, 0)';
        quad.stackingGroupId = layerQuad.stackingGroupId;
        var type = cc.tileTypes.missing;
        if (tile) {
          type = tile.getTypeForLayer(layer);
          quad.backgroundColor = heatmapColors[heatIndex];
          ++heatIndex;
        }

        quad.borderColor = cc.tileBorder[type].color;
        quad.borderWidth = cc.tileBorder[type].width;

        this.quads_.push(quad);
      }
    },

    getValueForHeatmap_: function(tile, heatmapType) {
      if (heatmapType == TILE_HEATMAP_TYPE.SCHEDULED_PRIORITY)
        return tile.scheduledPriority;
      else if (heatmapType == TILE_HEATMAP_TYPE.DISTANCE_TO_VISIBLE)
        return tile.distanceToVisible;
      else if (heatmapType == TILE_HEATMAP_TYPE.TIME_TO_VISIBLE)
        return tile.timeToVisible;
    },

    computeHeatmapColors_: function(tiles, heatmapType) {
      var maxValue = 0;
      for (var i = 0; i < tiles.length; ++i) {
        var tile = tiles[i];
        var value = this.getValueForHeatmap_(tile, heatmapType);
        if (value !== undefined)
          maxValue = Math.max(value, maxValue);
      }

      if (maxValue == 0)
        maxValue = 1;

      var color = function(value) {
        var hue = 120 * (1 - value / maxValue);
        if (hue < 0)
          hue = 0;
        return 'hsla(' + hue + ', 100%, 50%, 0.5)';
      };

      var values = [];
      for (var i = 0; i < tiles.length; ++i) {
        var tile = tiles[i];
        var value = this.getValueForHeatmap_(tile, heatmapType);
        if (value !== undefined)
          values.push(color(value));
        else
          values.push(undefined);
      }

      return values;
    },

    appendTilesWithScaleQuads_: function(layer, layerQuad, scale, heatmapType) {
      var lthi = this.layerTreeImpl_.layerTreeHostImpl;

      var tiles = [];
      for (var i = 0; i < lthi.tiles.length; ++i) {
        var tile = lthi.tiles[i];

        if (Math.abs(tile.contentsScale - scale) > 1e-6)
          continue;

        // TODO(vmpstr): Make the stiching of tiles and layers a part of
        // tile construction (issue 346)
        if (layer.layerId != tile.layerId)
          continue;

        tiles.push(tile);
      }

      var heatmapColors =
          this.computeHeatmapColors_(tiles, heatmapType);

      for (var i = 0; i < tiles.length; ++i) {
        var tile = tiles[i];
        var rect = tile.layerRect;
        var unitRect = rect.asUVRectInside(layer.bounds);
        var quad = layerQuad.projectUnitRect(unitRect);

        quad.backgroundColor = 'rgba(0, 0, 0, 0)';
        quad.stackingGroupId = layerQuad.stackingGroupId;

        var type = tile.getTypeForLayer(layer);
        quad.borderColor = cc.tileBorder[type].color;
        quad.borderWidth = cc.tileBorder[type].width;

        quad.backgroundColor = heatmapColors[i];
        this.quads_.push(quad);
      }
    },

    appendSelectionQuads_: function(layer, layerQuad) {
      var selection = this.selection;
      var rect = selection.layerRect;
      if (!rect)
        return [];

      var unitRect = rect.asUVRectInside(layer.bounds);
      var quad = layerQuad.projectUnitRect(unitRect);

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

        if (this.showInvalidations)
          this.appendInvalidationQuads_(layer, layerQuad);

        if (this.howToShowTiles === 'coverage') {
          this.appendTileCoverageRectQuads_(
              layer, layerQuad, this.tileHeatmapType);
        } else if (this.howToShowTiles !== 'none') {
          this.appendTilesWithScaleQuads_(
              layer, layerQuad, this.howToShowTiles, this.tileHeatmapType);
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
      var camera = this.quadStackViewer_.camera;
      this.quadStackViewer_.quadStack.initialize(
          lthiInstance.allLayersBBox.asRect(), worldViewportRect,
          camera.scheduledLayoutPixelsPerWorldPixel);

      this.quadStackViewer_.quadStack.quads = this.quads_;

      this.updateInfoBar_(this.messages_);
    },

    updateInfoBar_: function(infoBarMessages) {
      if (infoBarMessages.length) {
        this.infoBar_.removeAllButtons();
        this.infoBar_.message = 'Some problems were encountered...';
        this.infoBar_.addButton('More info...', function(e) {
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

          e.stopPropagation();
          return false;
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
