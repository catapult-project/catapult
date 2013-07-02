// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('ui');

base.exportTo('tracing.analysis', function() {
  /**
   * Slice views allow customized visualization of specific slices, indexed by
   * title. If not registered, the default slice viewing logic is used.
   *
   * @constructor
   */
  var SliceView = ui.define('slice-view');

  SliceView.prototype = {
    __proto__: HTMLDivElement.prototype,

    decorate: function() {
      this.objectInstance_ = undefined;
    },

    set modelObject(obj) {
      this.slice = obj;
    },

    get modelObject() {
      return this.slice;
    },

    get slice() {
      return this.slice_;
    },

    set slice(s) {
      this.slice_ = s;
      this.updateContents();
    },

    updateContents: function() {
      throw new Error('Not implemented');
    }
  };

  SliceView.titleToViewInfoMap = {};
  SliceView.register = function(title, viewConstructor) {
    if (SliceView.titleToViewInfoMap[title])
      throw new Error('Handler already registerd for ' + title);
    SliceView.titleToViewInfoMap[title] = {
      constructor: viewConstructor
    };
  };

  SliceView.unregister = function(title) {
    if (SliceView.titleToViewInfoMap[title] === undefined)
      throw new Error(title + ' not registered');
    delete SliceView.titleToViewInfoMap[title];
  };

  SliceView.getViewInfo = function(title) {
    return SliceView.titleToViewInfoMap[title];
  };

  return {
    SliceView: SliceView
  };
});
