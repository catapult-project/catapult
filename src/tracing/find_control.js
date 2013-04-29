// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview FindControl and FindController.
 */
base.require('tracing.timeline_track_view');
base.require('tracing.filter');
base.require('ui.overlay');
base.exportTo('tracing', function() {

  /**
   * FindControl
   * @constructor
   * @extends {ui.Overlay}
   */
  var FindControl = ui.define('div');

  FindControl.prototype = {
    __proto__: ui.Overlay.prototype,

    decorate: function() {
      ui.Overlay.prototype.decorate.call(this);

      this.className = 'find-control';

      this.hitCountEl_ = document.createElement('div');
      this.hitCountEl_.className = 'hit-count-label';
      this.hitCountEl_.textContent = '1 of 7';

      var findPreviousBn = document.createElement('div');
      findPreviousBn.className = 'button find-previous';
      findPreviousBn.textContent = '\u2190';
      findPreviousBn.addEventListener('click', function() {
        this.controller.findPrevious();
        this.updateHitCountEl_();
      }.bind(this));

      var findNextBn = document.createElement('div');
      findNextBn.className = 'button find-next';
      findNextBn.textContent = '\u2192';
      findNextBn.addEventListener('click', function() {
        this.controller.findNext();
        this.updateHitCountEl_();
      }.bind(this));

      // Filter input element.
      this.filterEl_ = document.createElement('input');
      this.filterEl_.type = 'input';

      this.filterEl_.addEventListener('input', function(e) {
        this.controller.filterText = this.filterEl_.value;
        this.updateHitCountEl_();
      }.bind(this));

      this.filterEl_.addEventListener('keydown', function(e) {
        if (e.keyCode == 13) {
          findNextBn.click();
        } else if (e.keyCode == 27) {
          this.filterEl_.blur();
          this.updateHitCountEl_();
        }
      }.bind(this));

      this.filterEl_.addEventListener('blur', function(e) {
        this.updateHitCountEl_();
      }.bind(this));

      this.filterEl_.addEventListener('focus', function(e) {
        this.updateHitCountEl_();
      }.bind(this));

      // Attach everything.
      this.appendChild(this.filterEl_);

      this.appendChild(findPreviousBn);
      this.appendChild(findNextBn);
      this.appendChild(this.hitCountEl_);

      this.updateHitCountEl_();
    },

    get controller() {
      return this.controller_;
    },

    set controller(c) {
      this.controller_ = c;
      this.updateHitCountEl_();
    },

    focus: function() {
      this.filterEl_.selectionStart = 0;
      this.filterEl_.selectionEnd = this.filterEl_.value.length;
      this.filterEl_.focus();
    },

    updateHitCountEl_: function() {
      if (!this.controller || document.activeElement != this.filterEl_) {
        this.hitCountEl_.textContent = '';
        return;
      }
      var i = this.controller.currentHitIndex;
      var n = this.controller.filterHits.length;
      if (n == 0)
        this.hitCountEl_.textContent = '0 of 0';
      else
        this.hitCountEl_.textContent = (i + 1) + ' of ' + n;
    }
  };

  function FindController() {
    this.timeline_ = undefined;
    this.model_ = undefined;
    this.filterText_ = '';
    this.filterHits_ = new tracing.Selection();
    this.filterHitsDirty_ = true;
    this.currentHitIndex_ = 0;
  };

  FindController.prototype = {
    __proto__: Object.prototype,

    get timeline() {
      return this.timeline_;
    },

    set timeline(t) {
      this.timeline_ = t;
      this.filterHitsDirty_ = true;
    },

    get filterText() {
      return this.filterText_;
    },

    set filterText(f) {
      if (f == this.filterText_)
        return;
      this.filterText_ = f;
      this.filterHitsDirty_ = true;
      this.findNext();
    },

    get filterHits() {
      if (this.filterHitsDirty_) {
        this.filterHitsDirty_ = false;
        if (this.timeline_) {
          var filter = new tracing.TitleFilter(this.filterText);
          this.filterHits_.clear();
          this.timeline.addAllObjectsMatchingFilterToSelection(
              filter, this.filterHits_);
          this.currentHitIndex_ = this.filterHits_.length - 1;
        } else {
          this.filterHits_.clear();
          this.currentHitIndex_ = 0;
        }
      }
      return this.filterHits_;
    },

    get currentHitIndex() {
      return this.currentHitIndex_;
    },

    find_: function(dir) {
      if (!this.timeline)
        return;

      var N = this.filterHits.length;
      this.currentHitIndex_ = this.currentHitIndex_ + dir;

      if (this.currentHitIndex_ < 0) this.currentHitIndex_ = N - 1;
      if (this.currentHitIndex_ >= N) this.currentHitIndex_ = 0;

      if (this.currentHitIndex_ < 0 || this.currentHitIndex_ >= N) {
        this.timeline.selection = new tracing.Selection();
        return;
      }

      // We allow the zoom level to change on the first hit level. But, when
      // then cycling through subsequent changes, restrict it to panning.
      var zoomAllowed = this.currentHitIndex_ == 0;
      var subSelection = this.filterHits.subSelection(this.currentHitIndex_);
      this.timeline.setSelectionAndMakeVisible(subSelection, zoomAllowed);
    },

    findNext: function() {
      this.find_(1);
    },

    findPrevious: function() {
      this.find_(-1);
    }
  };

  return {
    FindControl: FindControl,
    FindController: FindController
  };
});
