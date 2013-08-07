// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview QuadStackViewer controls the content and viewing angle a
 * QuadStack.
 */

base.require('ui.quad_stack');
base.require('ui.mouse_mode_selector');

base.exportTo('ui', function() {
  /**
   * @constructor
   */
  var QuadStackViewer = ui.define('quad-stack-viewer');

  QuadStackViewer.prototype = {
    __proto__: HTMLUnknownElement.prototype,

    decorate: function() {
      this.className = 'quad-stack-viewer';
      this.scale_ = 0.25;

      this.quadStack_ = new ui.QuadStack();
      this.appendChild(this.quadStack_);

      this.settingsKey_ = undefined;

      this.mouseModeSelector_ = new ui.MouseModeSelector(this);
      this.mouseModeSelector_.supportedModeMask =
          ui.MOUSE_SELECTOR_MODE.PANSCAN;
      this.appendChild(this.mouseModeSelector_);

      this.camera_ = new ui.Camera(this.quadStack_);
    },

    get mouseModeSelector() {
      return this.mouseModeSelector_;
    },

    get quadStack() {
      return this.quadStack_;
    },

    get camera() {
      return this.camera_;
    }
  };

  return {
    QuadStackViewer: QuadStackViewer
  };
});
