// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.


/**
 * @fileoverview RegExpSelector:  A ToggleButton and a RegExp input.
 * Takes .regexp, applies to addFilterableItem()-s
 * Gives .items array. tEntry .matches true for .regexp matches.
 */
base.require('ui');
base.require('ui.toggle_button');
base.require('ui.filter_control');
base.exportTo('ui', function() {

  /**
   * @constructor
   */
  var RegExpSelector = ui.define('span');

  RegExpSelector.prototype = {
    __proto__: HTMLSpanElement.prototype,

    items_: [],

    decorate: function() {
      this.regexp = new RegExp();
      this.items = [];

      this.classList.add('regexp-selector');
      this.createActivator_();
      this.createFilterControl_();
    },

    // To avoid quadradic filter calls, set regexp to blank first
    addFilterableItem: function(text) {
      this.items_.push({text: text});
      this.items.push({text: text});
      if (!this.activator_.isOn)
        this.filterItems_();
    },

    createActivator_: function() {
      this.activator_ = new ui.ToggleButton();
      // Use CSS attribute isOn
      this.activator_.isOnText = ui.ToggleButton.blank;
      this.activator_.notIsOnText = ui.ToggleButton.blank;

      this.activator_.addEventListener('isOnChange', function(event) {
        if (this.activator_.isOn)
          this.filterItems_();
        else
          this.noMatchesItems_();
      }.bind(this));
      this.appendChild(this.activator_);
      this.activator_.isOn = false;
    },

    createFilterControl_: function() {
      this.filterControl_ = new ui.FilterControl();

      this.filterControl_.addEventListener(
        'filterTextChange',
        this.onFilterTextChange_.bind(this)
      );

      this.filterControl_.addEventListener(
        'focus',
        this.onFocus_.bind(this),
        true // focus does not bubble
      );

      this.addEventListener(
        'regexpChange',
        this.onRegexpChange_.bind(this)
      );

      this.appendChild(this.filterControl_);

      this.filterControl_.hitCountText = 'Enter RegExp';
    },

    onRegexpChange_: function(event) {
      var isARegExp = this.regexp instanceof RegExp;
      if (!isARegExp) {
        this.regexp = new RegExp();
        event.throwError('RegExpSelector.regexp must be a RegExp');
        return;
      }
      this.filterItems_();
      this.skipUpdate = true;
      var src = this.regexp.source;
      this.filterControl_.filterText = (src === '(?:)' ? '' : src);
      delete this.skipUpdate;
    },

    onFilterTextChange_: function(event) {
      if (this.skipUpdate)
        return;
      var regexpText = this.filterControl_.filterText;
      this.classList.remove('invalid-regexp');
      try {
        this.regexp = new RegExp(regexpText);
      } catch (exc) {
        this.classList.add('invalid-regexp');
      }
      if (regexpText) {
        this.classList.remove('empty-regexp');
      } else {
        this.classList.add('empty-regexp');
      }
    },

    onFocus_: function(event) {
      this.activator_.isOn = true;
    },

    filterItem_: function(item) {
      var wasMatch = item.matches;
      item.matches = this.regexp.test(item.text);
      return (item.matches !== wasMatch);
    },

    filterItems_: function() {
      var anItemMatchChanged = this.items_.reduce(
        function(matchChanged, item) {
          return this.filterItem_(item) || matchChanged;
        }.bind(this),
        false
      );
      if (anItemMatchChanged) {
        var matches = 0;
        this.items = this.items_.map(function(item) {
          if (item.matches)
            matches++;
          return {text: item.text, matches: item.matches};
        });
        var text = matches + ' of ' + this.items_.length;
        this.filterControl_.hitCountText = text;
      }
    },

    noMatchesItems_: function() {
      var noMatches = new Array(this.items_.length);
      this.items_.forEach(function(item) {
        noMatches.push({text: item.text});
      });
      this.items = noMatches;
    },

  };

  // Input, eg to predefine a RegExp.
  base.defineProperty(RegExpSelector, 'regexp',
      base.PropertyKind.JS);

  // Output Object with .text string and .matches boolean
  base.defineProperty(RegExpSelector, 'items',
      base.PropertyKind.JS);

  // For CSS styling
  base.defineProperty(RegExpSelector, 'isOn',
      base.PropertyKind.BOOL_ATTR);

  return {
    RegExpSelector: RegExpSelector
  };

});
