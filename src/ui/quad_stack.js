// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('base.quad');
base.require('ui.quad_view');

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
      var quadView = new QuadView();
      quadView.viewport = this.viewport_;
      quadView.deviceViewportSizeForFrame = this.deviceViewportSizeForFrame_;
      quadView.quads = this.quads_;
      this.appendChild(quadView);
    }
  };


  return {
    QuadStack: QuadStack
  };
});
