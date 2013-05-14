// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/**
 * @fileoverview Renders an array of slices into the provided div,
 * using a child canvas element. Uses a FastRectRenderer to draw only
 * the visible slices.
 */
base.requireStylesheet('tracing.tracks.track');
base.require('ui');
base.require('ui.toggle_button');
base.exportTo('tracing.tracks', function() {

  /**
   * The base class for all tracks.
   * @constructor
   */
  var Track = ui.define('div');
  Track.prototype = {
    __proto__: HTMLDivElement.prototype,

    decorate: function() {
    },

    get visible() {
      return this.style.display !== 'none';
    },

    set visible(v) {
      this.style.display = (v ? '' : 'none');
    },

    get numVisibleTracks() {
      return (this.visible ? 1 : 0);
    },

    addControlButtonElements_: function() {
      var toggleButton = new ui.ToggleButton();
      toggleButton.classList.add('track-button');
      toggleButton.classList.add('track-collapse-button');
      this.insertBefore(toggleButton, this.firstChild);

      toggleButton.addEventListener('isOnChange', function() {
        this.style.display = toggleButton.isOn ? '' : 'none';
      }.bind(this));
    }
  };

  return {
    Track: Track
  };
});
