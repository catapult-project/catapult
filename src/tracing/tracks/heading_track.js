// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.requireStylesheet('tracing.tracks.heading_track');

base.require('tracing.constants');
base.require('tracing.tracks.track');
base.require('ui');

base.exportTo('tracing.tracks', function() {
  /**
   * A track with a header. Provides the basic heading and tooltip
   * infrastructure. Subclasses must implement drawing code.
   * @constructor
   * @extends {HTMLDivElement}
   */
  var HeadingTrack = ui.define('heading-track', tracing.tracks.Track);

  HeadingTrack.prototype = {
    __proto__: tracing.tracks.Track.prototype,

    decorate: function(viewport) {
      tracing.tracks.Track.prototype.decorate.call(this, viewport);
      this.classList.add('heading-track');

      this.headingDiv_ = document.createElement('heading');
      this.headingDiv_.style.width = tracing.constants.HEADING_WIDTH + 'px';
      this.heading_ = '';
      this.selectionGenerator_ = undefined;
      this.updateContents_();
    },

    get heading() {
      return this.heading_;
    },

    set heading(text) {
      this.heading_ = text;
      this.updateContents_();
    },

    set tooltip(text) {
      this.headingDiv_.title = text;
    },

    set selectionGenerator(generator) {
      this.selectionGenerator_ = generator;
      this.updateContents_();
    },

    updateContents_: function() {
      /**
       * If this is a heading track of a sampling thread, we add a link to
       * the heading text ("Sampling Thread"). We associate a selection
       * generator with the link so that sampling profiling results are
       * displayed in the bottom frame when you click the link.
       */
      this.headingDiv_.innerHTML = '';
      if (this.selectionGenerator_) {
        this.headingLink_ = document.createElement('a');
        tracing.analysis.AnalysisLink.decorate(this.headingLink_);
        this.headingLink_.selectionGenerator = this.selectionGenerator_;
        this.headingDiv_.appendChild(this.headingLink_);
        this.headingLink_.appendChild(document.createTextNode(this.heading_));
      } else {
        this.headingDiv_.appendChild(document.createTextNode(this.heading_));
      }
      this.appendChild(this.headingDiv_);
    },

    draw: function(type, viewLWorld, viewRWorld) {
      throw new Error('draw implementation missing');
    }
  };

  return {
    HeadingTrack: HeadingTrack
  };
});
