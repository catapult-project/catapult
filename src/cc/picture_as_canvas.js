// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.exportTo('cc', function() {

  /**
   * @constructor
   */
  function PictureAsCanvas(picture, errorOrCanvas) {
    this.picture_ = picture;
    if (errorOrCanvas instanceof HTMLCanvasElement) {
      this.error_ = undefined;
      this.canvas_ = errorOrCanvas;
    } else {
      this.error_ = errorOrCanvas;
      this.canvas_ = undefined;
    }
  };

  /**
   * Creates a new pending PictureAsCanvas (no canvas and no error).
   *
   * @return {PictureAsCanvas} a new pending PictureAsCanvas.
   */
  PictureAsCanvas.Pending = function(picture) {
    return new PictureAsCanvas(picture, undefined);
  };

  PictureAsCanvas.prototype = {
    get picture() {
      return this.picture_;
    },

    get error() {
      return this.error_;
    },

    get canvas() {
      return this.canvas_;
    },

    isPending: function() {
      return this.error_ === undefined && this.canvas_ === undefined;
    }
  };

  return {
    PictureAsCanvas: PictureAsCanvas
  };
});
