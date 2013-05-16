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

  RegExpSelector.defaultSource = '(?:)';

  RegExpSelector.prototype = {
    __proto__: HTMLSpanElement.prototype,

    decorate: function() {
      this.regexp = new RegExp();
      this.items = [];

      this.classList.add('regexp-selector');
      this.createActivator_();
      this.createFilterControl_();
    },

    // To avoid quadradic filter calls, set regexp to blank first
    addFilterableItem: function(text, opt_data) {
      var item = {text: text, data: opt_data};
      this.items.push(item);
      if (this.activator_.isOn)
        this.filterItems_();
    },

    clearItems: function() {
      this.items = [];
    },

    get isOn() {
      return this.activator_.isOn;
    },

    set isOn(aBoolean) {
      this.activator_.isOn = aBoolean;
    },

    //-------------------------------------

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
      var isDefault = (src === ui.RegExpSelector.defaultSource);
      this.filterControl_.filterText = isDefault ? '' : src;
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

    clone_: function(items) {
      return items.map(function(item) {
        return {text: item.text, matches: item.matches, data: item.data};
      });
    },

    filterItems_: function() {
      var itemsClone = this.clone_(this.items);
      var anItemMatchChanged = itemsClone.reduce(
        function(matchChanged, item) {
          return this.filterItem_(item) || matchChanged;
        }.bind(this),
        false
      );
      if (anItemMatchChanged) {
        var matches = 0;
        this.items = this.clone_(itemsClone);
        var matches = this.items.reduce(function(matches, item) {
          return item.matches ? matches + 1 : matches;
        }, 0);
        var text = matches + ' of ' + this.items.length;
        this.filterControl_.hitCountText = text;
      }
    },

    noMatchesItems_: function() {
      var noMatches = [];
      this.items.forEach(function(item) {
        noMatches.push({text: item.text, data: item.data});
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

  return {
    RegExpSelector: RegExpSelector
  };

});
