// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.exportTo('cc', function() {

  /**
   * @constructor
   */
  function PictureAsImage(picture, errorOrImage) {
    this.picture_ = picture;
    if (errorOrImage instanceof HTMLElement) {
      this.error_ = undefined;
      this.image_ = errorOrImage;
    } else {
      this.error_ = errorOrImage;
      this.image_ = undefined;
    }
  };

  /**
   * Creates a new pending PictureAsImage (no image and no error).
   *
   * @return {PictureAsImage} a new pending PictureAsImage.
   */
  PictureAsImage.Pending = function(picture) {
    return new PictureAsImage(picture, undefined);
  };

  PictureAsImage.prototype = {
    get picture() {
      return this.picture_;
    },

    get error() {
      return this.error_;
    },

    get image() {
      return this.image_;
    },

    isPending: function() {
      return this.error_ === undefined && this.image_ === undefined;
    }
  };

  return {
    PictureAsImage: PictureAsImage
  };
});
