// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview Graphical view of  LayerTreeImpl, with controls for
 * type of layer content shown and info bar for content-loading warnings.
 */

base.requireStylesheet('cc.layer_tree_quad_stack_view');

base.require('base.color');
base.require('base.properties');
base.require('base.raf');
base.require('base.quad');
base.require('base.range');
base.require('cc.picture');
base.require('cc.render_pass');
base.require('cc.tile');
base.require('cc.debug_colors');
base.require('ui.quad_stack_view');
base.require('ui.info_bar');


base.exportTo('cc', function() {

  var TILE_HEATMAP_TYPE = {};
  TILE_HEATMAP_TYPE.NONE = 0;
  TILE_HEATMAP_TYPE.SCHEDULED_PRIORITY = 1;
  TILE_HEATMAP_TYPE.DISTANCE_TO_VISIBLE = 2;
  TILE_HEATMAP_TYPE.TIME_TO_VISIBLE = 3;
  TILE_HEATMAP_TYPE.USING_GPU_MEMORY = 4;

  function createTileRectsSelectorBaseOptions() {
    return [{label: 'None', value: 'none'},
            {label: 'Coverage Rects', value: 'coverage'}];
  }

  /**
   * @constructor
   */
  var LayerTreeQuadStackView = ui.define('layer-tree-quad-stack-view');

  LayerTreeQuadStackView.prototype = {
    __proto__: HTMLDivElement.prototype,

    decorate: function() {
      this.isRenderPassQuads_ = false;
      this.pictureAsImageData_ = {}; // Maps picture.guid to PictureAsImageData.
      this.messages_ = [];
      this.controls_ = document.createElement('top-controls');
      this.infoBar_ = new ui.InfoBar();
      this.quadStackView_ = new ui.QuadStackView();
      this.quadStackView_.addEventListener(
          'selectionchange', this.onQuadStackViewSelectionChange_.bind(this));

      var m = ui.MOUSE_SELECTOR_MODE;
      var mms = this.quadStackView_.mouseModeSelector;
      mms.settingsKey = 'cc.layerTreeQuadStackView.mouseModeSelector';
      mms.setKeyCodeForMode(m.SELECTION, 'Z'.charCodeAt(0));
      mms.setKeyCodeForMode(m.PANSCAN, 'X'.charCodeAt(0));
      mms.setKeyCodeForMode(m.ZOOM, 'C'.charCodeAt(0));
      mms.setKeyCodeForMode(m.ROTATE, 'V'.charCodeAt(0));

      this.appendChild(this.controls_);
      this.appendChild(this.infoBar_);
      this.appendChild(this.quadStackView_);

      this.tileRectsSelector_ = ui.createSelector(
          this, 'howToShowTiles',
          'layerView.howToShowTiles', 'none',
          createTileRectsSelectorBaseOptions());
      this.controls_.appendChild(this.tileRectsSelector_);

      var tileHeatmapText = ui.createSpan({
        textContent: 'Tile heatmap:'
      });
      this.controls_.appendChild(tileHeatmapText);

      var tileHeatmapSelector = ui.createSelector(
          this, 'tileHeatmapType',
          'layerView.tileHeatmapType', TILE_HEATMAP_TYPE.NONE,
          [{label: 'None',
            value: TILE_HEATMAP_TYPE.NONE},
           {label: 'Scheduled Priority',
            value: TILE_HEATMAP_TYPE.SCHEDULED_PRIORITY},
           {label: 'Distance to Visible',
            value: TILE_HEATMAP_TYPE.DISTANCE_TO_VISIBLE},
           {label: 'Time to Visible',
            value: TILE_HEATMAP_TYPE.TIME_TO_VISIBLE},
           {label: 'Is using GPU memory',
            value: TILE_HEATMAP_TYPE.USING_GPU_MEMORY}
          ]);
      this.controls_.appendChild(tileHeatmapSelector);

      var showOtherLayersCheckbox = ui.createCheckBox(
          this, 'showOtherLayers',
          'layerView.showOtherLayers', true,
          'Other layers/passes');
      showOtherLayersCheckbox.title =
          'When checked, show all layers, selected or not.';
      this.controls_.appendChild(showOtherLayersCheckbox);

      var showInvalidationsCheckbox = ui.createCheckBox(
          this, 'showInvalidations',
          'layerView.showInvalidations', true,
          'Invalidations');
      showInvalidationsCheckbox.title =
          'When checked, compositing invalidations are highlighted in red';
      this.controls_.appendChild(showInvalidationsCheckbox);

      var showBottlenecksCheckbox = ui.createCheckBox(
          this, 'showBottlenecks',
          'layerView.showBottlenecks', true,
          'Bottlenecks');
      showBottlenecksCheckbox.title =
          'When checked, scroll bottlenecks are highlighted';
      this.controls_.appendChild(showBottlenecksCheckbox);

      var showContentsCheckbox = ui.createCheckBox(
          this, 'showContents',
          'layerView.showContents', true,
          'Contents');
      showContentsCheckbox.title =
          'When checked, show the rendered contents inside the layer outlines';
      this.controls_.appendChild(showContentsCheckbox);
    },

    get layerTreeImpl() {
      return this.layerTreeImpl_;
    },

    set whichTree(whichTree) {
      this.whichTree_ = whichTree;
    },

    set isRenderPassQuads(newValue) {
      this.isRenderPassQuads_ = newValue;
    },

    set layerTreeImpl(layerTreeImpl) {
      // FIXME(pdr): We may want to clear pictureAsImageData_ here to save
      //             memory at the cost of performance. Note that
      //             pictureAsImageData_ will be cleared when this is
      //             destructed, but this view might live for several
      //             layerTreeImpls.
      this.layerTreeImpl_ = layerTreeImpl;
      this.selection = undefined;
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

    get showBottlenecks() {
      return this.showBottlenecks_;
    },

    set showBottlenecks(show) {
      this.showBottlenecks_ = show;
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

    regenerateContent: function() {
      this.updateTilesSelector_();
      this.updateContents_();
    },

    onQuadStackViewSelectionChange_: function(e) {
      var selectableQuads = e.quads.filter(function(q) {
        return q.selectionToSetIfClicked !== undefined;
      });
      if (selectableQuads.length == 0) {
        this.selection = undefined;
        return;
      }

      // Sort the quads low to high on stackingGroupId.
      selectableQuads.sort(function(x, y) {
        var z = x.stackingGroupId - y.stackingGroupId;
        if (z != 0)
          return z;
        return x.selectionToSetIfClicked.specicifity -
            y.selectionToSetIfClicked.specicifity;
      });

      // TODO(nduca): Support selecting N things at once.
      var quadToSelect = selectableQuads[selectableQuads.length - 1];
      this.selection = quadToSelect.selectionToSetIfClicked;
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


      var status = this.computePictureLoadingStatus_();
      if (!status.picturesComplete)
        return;

      var lthi = this.layerTreeImpl_.layerTreeHostImpl;
      var lthiInstance = lthi.objectInstance;
      var worldViewportRect = base.Rect.fromXYWH(
          0, 0,
          lthi.deviceViewportSize.width, lthi.deviceViewportSize.height);
      this.quadStackView_.deviceRect = worldViewportRect;
      if (this.isRenderPassQuads_)
        this.quadStackView_.quads = this.generateRenderPassQuads();
      else
        this.quadStackView_.quads = this.generateLayerQuads();

      this.updateInfoBar_(status.messages);
    },

    updateTilesSelector_: function() {
      var data = createTileRectsSelectorBaseOptions();

      if (this.layerTreeImpl_) {
        // First get all of the scales information from LTHI.
        var lthi = this.layerTreeImpl_.layerTreeHostImpl;
        var scaleNames = lthi.getContentsScaleNames();
        for (var scale in scaleNames) {
          data.push({
            label: 'Scale ' + scale + ' (' + scaleNames[scale] + ')',
            value: scale
          });
        }
      }

      // Then create a new selector and replace the old one.
      var new_selector = ui.createSelector(
          this, 'howToShowTiles',
          'layerView.howToShowTiles', 'none',
          data);
      this.controls_.replaceChild(new_selector, this.tileRectsSelector_);
      this.tileRectsSelector_ = new_selector;
    },

    computePictureLoadingStatus_: function() {
      // Figure out if we can draw the quads yet. While we're at it, figure out
      // if we have any warnings we need to show.
      var layers = this.layers;
      var status = {
        messages: [],
        picturesComplete: true
      };
      if (this.showContents) {
        var hasPendingRasterizeImage = false;
        var firstPictureError = undefined;
        var hasMissingLayerRect = false;
        var hasUnresolvedPictureRef = false;
        for (var i = 0; i < layers.length; i++) {
          var layer = layers[i];
          for (var ir = 0; ir < layer.pictures.length; ++ir) {
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
        if (hasPendingRasterizeImage) {
          status.picturesComplete = false;
        } else {
          if (hasUnresolvedPictureRef) {
            status.messages.push({
              header: 'Missing picture',
              details: 'Your trace didnt have pictures for every layer. ' +
                  'Old chrome versions had this problem'});
          }
          if (hasMissingLayerRect) {
            status.messages.push({
              header: 'Missing layer rect',
              details: 'Your trace may be corrupt or from a very old ' +
                  'Chrome revision.'});
          }
          if (firstPictureError) {
            status.messages.push({
              header: 'Cannot rasterize',
              details: firstPictureError});
          }
        }
      }
      return status;
    },

    get selectedRenderPass() {
      if (this.selection)
        return this.selection.renderPass_;
    },

    get selectedLayer() {
      if (this.selection) {
        var selectedLayerId = this.selection.associatedLayerId;
        return this.layerTreeImpl_.findLayerWithId(selectedLayerId);
      }
    },

    get renderPasses() {
      var renderPasses =
          this.layerTreeImpl.layerTreeHostImpl.args.frame.renderPasses;
      if (!this.showOtherLayers) {
        var selectedRenderPass = this.selectedRenderPass;
        if (selectedRenderPass)
          renderPasses = [selectedRenderPass];
      }
      return renderPasses;
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

    appendImageQuads_: function(quads, layer, layerQuad) {
      // Generate image quads for the layer
      for (var ir = 0; ir < layer.pictures.length; ++ir) {
        var picture = layer.pictures[ir];
        if (!picture.layerRect)
          continue;

        var unitRect = picture.layerRect.asUVRectInside(layer.bounds);
        var iq = layerQuad.projectUnitRect(unitRect);

        var pictureData = this.pictureAsImageData_[picture.guid];
        if (this.showContents && pictureData && pictureData.imageData) {
          iq.imageData = pictureData.imageData;
          iq.borderColor = 'rgba(0,0,0,0)';
        } else {
          iq.imageData = undefined;
        }

        iq.stackingGroupId = layerQuad.stackingGroupId;
        quads.push(iq);
      }
    },

    appendInvalidationQuads_: function(quads, layer, layerQuad) {
      // Generate the invalidation rect quads.
      for (var ir = 0; ir < layer.invalidation.rects.length; ir++) {
        var rect = layer.invalidation.rects[ir];
        var unitRect = rect.asUVRectInside(layer.bounds);
        var iq = layerQuad.projectUnitRect(unitRect);
        iq.backgroundColor = 'rgba(255, 0, 0, 0.1)';
        iq.borderColor = 'rgba(255, 0, 0, 1)';
        iq.stackingGroupId = layerQuad.stackingGroupId;
        iq.selectionToSetIfClicked = new cc.LayerRectSelection(
            layer, 'Invalidation rect', rect, rect);
        quads.push(iq);
      }
    },

    appendBottleneckQuads_: function(quads, layer, layerQuad, stackingGroupId) {
      function processRegion(region, label, borderColor) {
        var backgroundColor = borderColor.clone();
        backgroundColor.a = 0.4 * (borderColor.a || 1.0);

        for (var ir = 0; ir < region.rects.length; ir++) {
          var rect = region.rects[ir];
          var unitRect = rect.asUVRectInside(layer.bounds);
          var iq = layerQuad.projectUnitRect(unitRect);
          iq.backgroundColor = backgroundColor.toString();
          iq.borderColor = borderColor.toString();
          iq.borderWidth = 4.0;
          iq.stackingGroupId = stackingGroupId;
          iq.selectionToSetIfClicked = new cc.LayerRectSelection(
              layer, label, rect, rect);
          quads.push(iq);
        }
      }

      processRegion(layer.touchEventHandlerRegion, 'Touch listener',
                    base.Color.fromString('rgb(228, 226, 27)'));
      processRegion(layer.wheelEventHandlerRegion, 'Wheel listener',
                    base.Color.fromString('rgb(176, 205, 29)'));
      processRegion(layer.nonFastScrollableRegion, 'Repaints on scroll',
                    base.Color.fromString('rgb(213, 134, 32)'));
    },

    appendTileCoverageRectQuads_: function(
        quads, layer, layerQuad, heatmapType) {
      if (!layer.tileCoverageRects)
        return;

      var tiles = [];
      for (var ct = 0; ct < layer.tileCoverageRects.length; ++ct) {
        var tile = layer.tileCoverageRects[ct].tile;
        if (tile !== undefined)
          tiles.push(tile);
      }

      var lthi = this.layerTreeImpl_.layerTreeHostImpl;
      var minMax =
          this.getMinMaxForHeatmap_(lthi.tiles, heatmapType);
      var heatmapColors =
          this.computeHeatmapColors_(tiles, minMax, heatmapType);
      var heatIndex = 0;

      for (var ct = 0; ct < layer.tileCoverageRects.length; ++ct) {
        var rect = layer.tileCoverageRects[ct].geometryRect;
        rect = rect.scale(1.0 / layer.geometryContentsScale);

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
        var label;
        if (tile)
          label = 'coverageRect';
        else
          label = 'checkerboard coverageRect';
        quad.selectionToSetIfClicked = new cc.LayerRectSelection(
            layer, label, rect, layer.tileCoverageRects[ct]);

        quads.push(quad);
      }
    },

    getValueForHeatmap_: function(tile, heatmapType) {
      if (heatmapType == TILE_HEATMAP_TYPE.SCHEDULED_PRIORITY) {
        return tile.scheduledPriority == 0 ?
            undefined :
            tile.scheduledPriority;
      } else if (heatmapType == TILE_HEATMAP_TYPE.DISTANCE_TO_VISIBLE) {
        return tile.distanceToVisible;
      } else if (heatmapType == TILE_HEATMAP_TYPE.TIME_TO_VISIBLE) {
        return Math.min(5, tile.timeToVisible);
      } else if (heatmapType == TILE_HEATMAP_TYPE.USING_GPU_MEMORY) {
        if (tile.isSolidColor)
          return 0.5;
        return tile.isUsingGpuMemory ? 0 : 1;
      }
    },

    getMinMaxForHeatmap_: function(tiles, heatmapType) {
      var range = new base.Range();
      if (heatmapType == TILE_HEATMAP_TYPE.USING_GPU_MEMORY) {
        range.addValue(0);
        range.addValue(1);
        return range;
      }

      for (var i = 0; i < tiles.length; ++i) {
        var value = this.getValueForHeatmap_(tiles[i], heatmapType);
        if (value == undefined)
          continue;
        range.addValue(value);
      }
      if (range.range == 0)
        range.addValue(1);
      return range;
    },

    computeHeatmapColors_: function(tiles, minMax, heatmapType) {
      var min = minMax.min;
      var max = minMax.max;

      var color = function(value) {
        var hue = 120 * (1 - (value - min) / (max - min));
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

    appendTilesWithScaleQuads_: function(
        quads, layer, layerQuad, scale, heatmapType) {
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

      var minMax =
          this.getMinMaxForHeatmap_(lthi.tiles, heatmapType);
      var heatmapColors =
          this.computeHeatmapColors_(tiles, minMax, heatmapType);

      for (var i = 0; i < tiles.length; ++i) {
        var tile = tiles[i];
        var rect = tile.layerRect;
        if (!tile.layerRect)
          continue;
        var unitRect = rect.asUVRectInside(layer.bounds);
        var quad = layerQuad.projectUnitRect(unitRect);

        quad.backgroundColor = 'rgba(0, 0, 0, 0)';
        quad.stackingGroupId = layerQuad.stackingGroupId;

        var type = tile.getTypeForLayer(layer);
        quad.borderColor = cc.tileBorder[type].color;
        quad.borderWidth = cc.tileBorder[type].width;

        quad.backgroundColor = heatmapColors[i];
        quad.selectionToSetIfClicked = new cc.TileSelection(tile);
        quads.push(quad);
      }
    },

    appendSelectionQuads_: function(quads, layer, layerQuad) {
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
      quads.push(quadForDrawing);
    },

    generateRenderPassQuads: function() {
      if (!this.layerTreeImpl.layerTreeHostImpl.args.frame)
        return [];
      var renderPasses = this.renderPasses;
      if (!renderPasses)
        return [];

      var quads = [];
      for (var i = 0; i < renderPasses.length; ++i) {
        var quadList = renderPasses[i].quadList;
        for (var j = 0; j < quadList.length; ++j) {
          var drawQuad = quadList[j];
          var quad = drawQuad.rectAsTargetSpaceQuad.clone();
          quad.borderColor = 'rgb(170, 204, 238)';
          quad.borderWidth = 2;
          quad.stackingGroupId = i;
          quads.push(quad);
        }
      }
      return quads;
    },

    generateLayerQuads: function() {
      this.updateContentsPending_ = false;

      // Generate the quads for the view.
      var layers = this.layers;
      var quads = [];
      var nextStackingGroupId = 0;
      var alreadyVisitedLayerIds = {};

      for (var i = 1; i <= layers.length; i++) {
        // Generate quads back-to-front.
        var layer = layers[layers.length - i];
        alreadyVisitedLayerIds[layer.layerId] = true;
        if (layer.objectInstance.name == 'cc::NinePatchLayerImpl')
          continue;

        var layerQuad = layer.layerQuad.clone();
        layerQuad.borderColor = 'rgba(0,0,0,0.75)';
        layerQuad.stackingGroupId = nextStackingGroupId++;
        layerQuad.selectionToSetIfClicked = new cc.LayerSelection(layer);
        layerQuad.layer = layer;
        if (this.showOtherLayers && this.selectedLayer == layer)
          layerQuad.upperBorderColor = 'rgb(156,189,45)';

        this.appendImageQuads_(quads, layer, layerQuad);
        quads.push(layerQuad);


        if (this.showInvalidations)
          this.appendInvalidationQuads_(quads, layer, layerQuad);
        if (this.showBottlenecks)
          this.appendBottleneckQuads_(quads, layer, layerQuad,
                                      layerQuad.stackingGroupId);

        if (this.howToShowTiles === 'coverage') {
          this.appendTileCoverageRectQuads_(
              quads, layer, layerQuad, this.tileHeatmapType);
        } else if (this.howToShowTiles !== 'none') {
          this.appendTilesWithScaleQuads_(
              quads, layer, layerQuad,
              this.howToShowTiles, this.tileHeatmapType);
        }

        if (this.selectedLayer === layer)
          this.appendSelectionQuads_(quads, layer, layerQuad);
      }

      this.layerTreeImpl.iterLayers(function(layer, depth, isMask, isReplica) {
        if (!this.showOtherLayers && this.selectedLayer != layer)
          return;
        if (alreadyVisitedLayerIds[layer.layerId])
          return;
        var layerQuad = layer.layerQuad;
        var stackingGroupId = nextStackingGroupId++;
        if (this.showBottlenecks)
          this.appendBottleneckQuads_(quads, layer, layerQuad, stackingGroupId);
      }, this);

      return quads;
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
    LayerTreeQuadStackView: LayerTreeQuadStackView
  };
});
