// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('base.bbox2');
base.require('base.quad');
base.require('ui.quad_view');
base.require('cc.region');

base.exportTo('ui', function() {
  var QuadView = ui.QuadView;

  /**
   * @constructor
   */
  var QuadStack = ui.define('quad-stack');

  QuadStack.prototype = {
    __proto__: HTMLUnknownElement.prototype,

    decorate: function() {
      this.viewport_ = undefined;
      this.quads_ = undefined;
      this.deviceViewportSizeForFrame_ = undefined;
    },

    get quads() {
      return this.quads_;
    },

    set quads(quads) {
      for (var i = 0; i < quads.length; i++) {
        if (quads[i].stackingGroupId === undefined)
          throw new Error('All quads must have stackingGroupIds');
      }
      this.quads_ = quads;
      this.updateContents_();
    },

    get viewport() {
      return this.viewport_;
    },

    set viewport(viewport) {
      this.viewport_ = viewport;
      this.updateContents_();
    },

    get deviceViewportSizeForFrame() {
      return this.deviceViewportSizeForFrame_;
    },

    set deviceViewportSizeForFrame(deviceViewportSizeForFrame) {
      this.deviceViewportSizeForFrame_ = deviceViewportSizeForFrame;
      this.updateContents_();
    },

    updateContents_: function() {
      this.textContent = '';
      var that = this;
      function appendNewQuadView() {
        var quadView = new QuadView();
        quadView.viewport = that.viewport_;
        quadView.deviceViewportSizeForFrame = that.deviceViewportSizeForFrame_;
        quadView.pendingQuads = [];
        quadView.region = new cc.Region();
        that.appendChild(quadView);
        return quadView;
      }

      // Temporarily off.
      if (true) {
        var qv = appendNewQuadView();
        qv.quads = this.quads_;
        return;
      }


      var stackingGroupsById = {};
      var quads = this.quads;
      for (var i = 0; i < quads.length; i++) {
        var quad = quads[i];
        if (stackingGroupsById[quad.stackingGroupId] === undefined)
          stackingGroupsById[quad.stackingGroupId] = [];
        stackingGroupsById[quad.stackingGroupId].push(quad);
      }


      appendNewQuadView();
      for (var stackingGroupId in stackingGroupsById) {
        var stackingGroup = stackingGroupsById[stackingGroupId];
        var bbox = new base.BBox2();
        stackingGroup.forEach(function(q) { bbox.addQuad(q); });
        var bboxRect = bbox.asRect();

        var curView = this.children[this.children.length - 1];
        if (curView.region.rectIntersects(bboxRect))
          curView = appendNewQuadView();
        curView.region.rects.push(bboxRect);
        stackingGroup.forEach(function(q) {
          curView.pendingQuads.push(q);
        });
      }

      for (var i = 0; i < this.children.length; i++) {
        var child = this.children[i];
        child.quads = child.pendingQuads;
        delete child.pendingQuads;
      }
    }
  };


  return {
    QuadStack: QuadStack
  };
});
