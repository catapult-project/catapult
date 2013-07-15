// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview Renders an array of slices into the provided div,
 * using a child canvas element. Uses a FastRectRenderer to draw only
 * the visible slices.
 */

base.requireStylesheet('tracing.tracks.track');
base.require('ui');
base.require('ui.container_that_decorates_its_children');

base.exportTo('tracing.tracks', function() {

  /**
   * The base class for all tracks.
   * @constructor
   */
  var Track = ui.define('track', ui.ContainerThatDecoratesItsChildren);
  Track.prototype = {
    __proto__: ui.ContainerThatDecoratesItsChildren.prototype,

    decorate: function(viewport) {
      ui.ContainerThatDecoratesItsChildren.prototype.decorate.call(this);
      if (viewport === undefined)
        throw new Error('viewport is required when creating a Track.');

      this.viewport_ = viewport;
      this.classList.add('track');
      this.categoryFilter_ = undefined;
    },

    get viewport() {
      return this.viewport_;
    },

    context: function() {
      // This is a little weird here, but we have to be able to walk up the
      // parent tree to get the context.
      if (!this.parentNode)
        return undefined;
      if (!this.parentNode.context)
        throw new Error('Parent container does not support context() method.');
      return this.parentNode.context();
    },

    get categoryFilter() {
      return this.categoryFilter_;
    },

    set categoryFilter(categoryFilter) {
      if (this.categoryFilter_ == categoryFilter)
        return;
      this.categoryFilter_ = categoryFilter;
      this.updateContents_();
    },

    decorateChild_: function(childTrack) {
      if (childTrack instanceof Track)
        childTrack.categoryFilter = this.categoryFilter;
    },

    undecorateChild_: function(childTrack) {
      if (childTrack.detach)
        childTrack.detach();
    },

    updateContents_: function() {
    }
  };

  return {
    Track: Track
  };
});
