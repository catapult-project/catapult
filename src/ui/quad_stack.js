// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.requireStylesheet('ui.quad_stack');

base.require('base.properties');
base.require('base.bbox2');
base.require('base.quad');
base.require('base.utils');
base.require('base.raf');
base.require('ui.quad_view');
base.require('cc.region');
base.require('ui.camera');
base.require('ui.rect_view');

base.exportTo('ui', function() {
  var QuadView = ui.QuadView;

  function validateQuads(quads) {
    for (var i = 0; i < quads.length; i++) {
      if (quads[i].stackingGroupId === undefined)
        throw new Error('All quads must have stackingGroupIds');
    }
  }

  /**
   * @constructor
   */
  var QuadStack = ui.define('quad-stack');

  QuadStack.prototype = {
    __proto__: HTMLUnknownElement.prototype,

    decorate: function() {
      this.layerContainer_ = document.createElement('layer-container');
      this.appendChild(this.layerContainer_);
      this.viewport_ = undefined;
      this.worldViewportRectView_ = new ui.RectView();
      this.quads_ = undefined;
    },

    initialize: function(unpaddedWorldRect, opt_worldViewportRect, opt_scale) {
      this.viewport_ = new ui.QuadViewViewport(unpaddedWorldRect);
      if (opt_scale)
        this.viewport_.scale = opt_scale;

      this.viewport_.addEventListener('change', function() {
        this.worldViewportRectView_.viewport = this.viewport_;
      }.bind(this));

      this.worldViewportRect_ = base.Rect.FromXYWH(
          opt_worldViewportRect.x || 0,
          opt_worldViewportRect.y || 0,
          opt_worldViewportRect.width,
          opt_worldViewportRect.height
          );

      this.worldViewportRectView_.viewport = this.viewport_;
      this.worldViewportRectView_.rect = this.worldViewportRect_;
    },

    get layers() {
      return this.layers_;
    },

    set layers(newValue) {
      base.setPropertyAndDispatchChange(this, 'layers', newValue);
    },

    get quads() {
      return this.quads_;
    },

    set quads(quads) {
      validateQuads(quads);
      this.quads_ = quads;
      this.updateContents_();
    },

    get viewport() {
      return this.viewport_;
    },

    get worldViewportRect() {
      return this.worldViewportRect_;
    },

    get worldViewportRectView() {
      return this.worldViewportRectView_;
    },

    get layerContainer() {
      return this.layerContainer_;
    },

    updateContents_: function() {
      // Build the stacks.
      var stackingGroupsById = {};
      var quads = this.quads;
      for (var i = 0; i < quads.length; i++) {
        var quad = quads[i];
        if (stackingGroupsById[quad.stackingGroupId] === undefined)
          stackingGroupsById[quad.stackingGroupId] = [];
        stackingGroupsById[quad.stackingGroupId].push(quad);
      }

      // Remove worldViewportRectView to re-insert after Quads.
      if (this.worldViewportRectView_.parentNode === this.layerContainer_)
        this.layerContainer_.removeChild(this.worldViewportRectView_);

      // Get rid of old quad views if needed.
      var numStackingGroups = base.dictionaryValues(stackingGroupsById).length;
      while (this.layerContainer_.children.length > numStackingGroups) {
        var n = this.layerContainer_.children.length - 1;
        this.layerContainer_.removeChild(
            this.layerContainer_.children[n]);
      }

      // Helper function to create a new quad view and track the current one.
      var that = this;
      var curQuadViewIndex = -1;
      var curQuadView = undefined;
      function appendNewQuadView() {
        curQuadViewIndex++;
        if (curQuadViewIndex < that.layerContainer_.children.length) {
          curQuadView = that.layerContainer_.children[curQuadViewIndex];
        } else {
          curQuadView = new QuadView();
          that.layerContainer_.appendChild(curQuadView);
        }
        curQuadView.quads = undefined;
        curQuadView.viewport = that.viewport_;
        curQuadView.pendingQuads = [];
        curQuadView.region = new cc.Region();
        return curQuadView;
      }

      appendNewQuadView();
      for (var stackingGroupId in stackingGroupsById) {
        var stackingGroup = stackingGroupsById[stackingGroupId];
        var bbox = new base.BBox2();
        stackingGroup.forEach(function(q) { bbox.addQuad(q); });
        var bboxRect = bbox.asRect();

        if (curQuadView.region.rectIntersects(bboxRect))
          appendNewQuadView();
        curQuadView.region.rects.push(bboxRect);
        stackingGroup.forEach(function(q) {
          curQuadView.pendingQuads.push(q);
        });
      }

      // Add worldViewportRectView after the Quads.
      this.layerContainer_.appendChild(this.worldViewportRectView_);

      for (var i = 0; i < this.layerContainer_.children.length; i++) {
        var child = this.layerContainer_.children[i];
        if (child instanceof ui.QuadView) {
          child.quads = child.pendingQuads;
          delete child.pendingQuads;
        }
      }

      this.viewport.updateBoxSize(this.layerContainer_);
      this.layers = this.layerContainer_.children;
    },


  };

  return {
    QuadStack: QuadStack
  };
});
