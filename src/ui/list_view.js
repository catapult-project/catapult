// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
'use strict';

/**
 * @fileoverview Simple list view.
 */
base.require('ui');
base.requireStylesheet('ui.list_view');
base.exportTo('ui', function() {

  /**
   * @constructor
   */
  var ListView = ui.define('x-list-view');

  ListView.prototype = {
    __proto__: HTMLUnknownElement.prototype,

    decorate: function() {
      this.onItemClicked_ = this.onItemClicked_.bind(this);
      this.onKeyDown_ = this.onKeyDown_.bind(this);
      this.observer_ = new WebKitMutationObserver(this.didMutate_.bind(this));
      this.observer_.observe(this, { childList: true });
      this.tabIndex = 0;
      this.addEventListener('keydown', this.onKeyDown_);
    },

    appendChild: function(x) {
      HTMLUnknownElement.prototype.appendChild.call(this, x);
      this.didMutate_(this.observer_.takeRecords());
    },

    insertBefore: function(x, y) {
      HTMLUnknownElement.prototype.insertBefore.call(this, x, y);
      this.didMutate_(this.observer_.takeRecords());
    },

    removeChild: function(x) {
      HTMLUnknownElement.prototype.removeChild.call(this, x);
      this.didMutate_(this.observer_.takeRecords());
    },

    replaceChild: function(x, y) {
      HTMLUnknownElement.prototype.replaceChild.call(this, x, y);
      this.didMutate_(this.observer_.takeRecords());
    },

    didMutate_: function(records) {
      var selectionChanged = false;
      for (var i = 0; i < records.length; i++) {
        var addedNodes = records[i].addedNodes;
        if (addedNodes) {
          for (var j = 0; j < addedNodes.length; j++)
            this.decorateItem_(addedNodes[j]);
        }
        var removedNodes = records[i].removedNodes;
        if (removedNodes) {
          for (var j = 0; j < removedNodes.length; j++) {
            selectionChanged |= removedNodes[j].selected;
            this.undecorateItem_(removedNodes[j]);
          }
        }
      }
      if (selectionChanged)
        base.dispatchSimpleEvent(this, 'selection-changed', false);
    },

    decorateItem_: function(item) {
      item.classList.add('list-item');
      item.addEventListener('click', this.onItemClicked_);

      var listView = this;
      Object.defineProperty(
        item,
        "selected", {
          configurable: true,
          set: function(value) {
            var oldSelection = listView.selectedElement;
            if (oldSelection && oldSelection != this && value)
              listView.selectedElement.removeAttribute('selected');
            if (value)
              this.setAttribute('selected', 'selected');
            else
              this.removeAttribute('selected');
            var newSelection = listView.selectedElement;
            if (newSelection != oldSelection)
              base.dispatchSimpleEvent(listView, 'selection-changed', false);
          },
          get: function() {
            return this.hasAttribute('selected');
          }
        });
    },

    undecorateItem_: function(item) {
      item.classList.remove('list-item');
      item.removeEventListener('click', this.onItemClicked_);
      delete item.selected;
    },

    get selectedElement() {
      var el = this.querySelector('.list-item[selected]');
      if (!el)
        return undefined;
      return el;
    },

    set selectedElement(el) {
      if (!el) {
        if (this.selectedElement)
          this.selectedElement.selected = false;
        return;
      }

      if (el.parentElement != this)
        throw new Error(
            'Can only select elements that are children of this list view');
      el.selected = true;
    },

    clear: function() {
      var changed = this.selectedElement !== undefined;
      this.textContent = '';
      if (changed)
        base.dispatchSimpleEvent(this, 'selection-changed', false);
    },

    onItemClicked_: function(e) {
      var currentSelectedElement = this.selectedElement;
      if (currentSelectedElement)
        currentSelectedElement.removeAttribute('selected');
      e.target.setAttribute('selected', 'selected');
      base.dispatchSimpleEvent(this, 'selection-changed', false);
    },

    onKeyDown_: function(e) {
      if (e.keyCode == 38) { // Up arrow.
        var prev = this.selectedElement.previousSibling;
        if (prev) {
          prev.selected = true;
          prev.scrollIntoView(false);
          e.preventDefault();
          return true;
        }
      } else if(e.keyCode == 40) { // Down arrow.
        var next = this.selectedElement.nextSibling;
        if (next) {
          next.selected = true;
          next.scrollIntoView(false);
          e.preventDefault();
          return true;
        }
      }
    },

    addItem: function(textContent) {
      var item = document.createElement('div');
      item.textContent = textContent;
      this.appendChild(item);
      return item;
    },

  };

  return {
    ListView: ListView
  };

});
