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
    },

    setQuadsAndViewport: function(quads, viewport) {
      viewport.scale = this.scale_;
      this.quadStack_.setQuadsAndViewport(quads, viewport);
    },

    get scale() {
      return this.scale_;
    },

    set scale(newValue) {
      this.scale_ = newValue;
      if (this.quadStack_.viewport)
        this.quadStack_.viewport.scale = newValue;
    }

  };

  return {
    QuadStackViewer: QuadStackViewer
  };
});
