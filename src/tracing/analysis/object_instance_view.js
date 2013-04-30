// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('ui');

base.exportTo('tracing.analysis', function() {
  var ObjectInstanceView = ui.define('div');

  ObjectInstanceView.prototype = {
    __proto__: HTMLDivElement.prototype,

    decorate: function() {
      this.objectInstance_ = undefined;
    },

    get objectInstance() {
      return this.objectInstance_;
    },

    set objectInstance(i) {
      this.objectInstance_ = i;
      this.updateContents();
    },

    updateContents: function() {
      throw new Error('Not implemented');
    }
  };

  ObjectInstanceView.typeNameToViewConstructorMap = {};
  ObjectInstanceView.register = function(typeName, viewConstructor) {
    if (ObjectInstanceView.typeNameToViewConstructorMap[typeName])
      throw new Error('Handler already registerd for ' + typeName);
    ObjectInstanceView.typeNameToViewConstructorMap[typeName] =
      viewConstructor;
  };

  ObjectInstanceView.getViewConstructor = function(typeName) {
    return ObjectInstanceView.typeNameToViewConstructorMap[typeName];
  };


  return {
    ObjectInstanceView: ObjectInstanceView
  };
});
