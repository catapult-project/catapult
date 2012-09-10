// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.


/**
 * @fileoverview Renders an array of slices into the provided div,
 * using a child canvas element. Uses a FastRectRenderer to draw only
 * the visible slices.
 */
base.requireStylesheet('tracks.timeline_track');
base.require('ui');
base.exportTo('tracks', function() {

  /**
   * The base class for all tracks.
   * @constructor
   */
  var TimelineTrack = base.ui.define('div');
  TimelineTrack.prototype = {
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

    addControlButtonElements_: function(canCollapse) {
      var closeEl = document.createElement('div');
      closeEl.classList.add('timeline-track-button');
      closeEl.classList.add('timeline-track-close-button');
      closeEl.textContent = String.fromCharCode(215); // &times;
      var that = this;
      closeEl.addEventListener('click', function() {
        that.style.display = 'None';
      });
      this.appendChild(closeEl);

      var collapseEl = document.createElement('div');
      collapseEl.classList.add('timeline-track-button');
      collapseEl.classList.add('timeline-track-collapse-button');
      var minus = '\u2212'; // minus sign;
      var plus = '\u002b'; // plus sign;
      collapseEl.textContent = minus;
      var collapsed = false;
      collapseEl.addEventListener('click', function() {
        collapsed = !collapsed;
        this.collapsedDidChange(collapsed);
        collapseEl.textContent = collapsed ? plus : minus;
      });
      this.appendChild(collapseEl);
      if (!canCollapse)
        collapseEl.style.display = 'None';
    }
  };

  return {
    TimelineTrack: TimelineTrack
  };
});
