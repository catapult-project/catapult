// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.requireStylesheet('cc.raster_task_slice_view');
base.require('cc.tile');
base.require('cc.tile_view');
base.require('cc.layer_tree_host_impl_view');
base.require('tracing.analysis.slice_view');
base.require('ui.info_bar');

base.exportTo('cc', function() {

  /**
   * @constructor
   */
  var RasterTaskSliceView = ui.define(
      'raster-task-slice-view', tracing.analysis.SliceView);

  RasterTaskSliceView.prototype = {
    __proto__: tracing.analysis.SliceView.prototype,

    decorate: function() {
      this.classList.add('raster-task-slice-view');
      this.layerTreeView_ = new cc.LayerTreeHostImplSnapshotView();
      this.infoBar_ = new ui.InfoBar();
      this.appendChild(this.infoBar_);
      this.appendChild(this.layerTreeView_);
    },

    updateContents: function() {
      this.infoBar_.visible = false;

      if (!this.slice.args.data) {
        this.infoBar_.visible = true;
        this.infoBar_.message = 'No data on this raster task.';
        this.layerTreeView_.style.display = 'none';
        return;
      }
      var tile = this.slice.args.data.tile_id;
      if (!tile) {
        this.infoBar_.visible = true;
        this.infoBar_.message = 'No tile on this raster task.';
        this.layerTreeView_.style.display = 'none';
        return;
      }
      if (!(tile instanceof cc.TileSnapshot)) {
        this.infoBar_.visible = true;
        this.infoBar_.message = 'This raster task didn\'t get fully traced.';
        this.layerTreeView_.style.display = 'none';
        return;
      }
      this.layerTreeView_.style.display = '';

      var containingSnapshot = tile.containingSnapshot;
      this.layerTreeView_.objectSnapshot = containingSnapshot;
      this.layerTreeView_.selection = new cc.RasterTaskSelection(this.slice);
    }
  };

  tracing.analysis.SliceView.register(
      'TileManager::RunRasterTask', RasterTaskSliceView);
  tracing.analysis.SliceView.register(
      'RasterWorkerPoolTaskImpl::RunRasterOnThread', RasterTaskSliceView);

  tracing.analysis.SliceView.register(
      'TileManager::RunAnalyzeTask', RasterTaskSliceView);
  tracing.analysis.SliceView.register(
      'RasterWorkerPoolTaskImpl::RunAnalysisOnThread', RasterTaskSliceView);

  return {
    RasterTaskSliceView: RasterTaskSliceView
  };

});
