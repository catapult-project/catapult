// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.exportTo('base', function() {
  function asArray(arrayish) {
    var values = [];
    for (var i = 0; i < arrayish.length; i++)
      values.push(arrayish[i]);
    return values;
  }

  function concatenateArrays(/*arguments*/) {
    var values = [];
    for (var i = 0; i < arguments.length; i++) {
      if (!(arguments[i] instanceof Array))
        throw new Error('Arguments ' + i + 'is not an array');
      values.push.apply(values, arguments[i]);
    }
    return values;
  }

  function dictionaryKeys(dict) {
    var keys = [];
    for (var key in dict)
      keys.push(key);
    return keys;
  }

  function dictionaryValues(dict) {
    var values = [];
    for (var key in dict)
      values.push(dict[key]);
    return values;
  }

  function iterItems(dict, fn, opt_this) {
    opt_this = opt_this || this;
    for (var key in dict)
      fn.call(opt_this, key, dict[key]);
  }

  function iterObjectFieldsRecursively(object, func) {
    if (!(object instanceof Object))
      return;

    if (object instanceof Array) {
      for (var i = 0; i < object.length; i++) {
        func(object, i, object[i]);
        iterObjectFieldsRecursively(object[i], func);
      }
      return;
    }

    for (var key in object) {
      var value = object[key];
      func(object, key, value);
      iterObjectFieldsRecursively(value, func);
    }
  }

  return {
    asArray: asArray,
    concatenateArrays: concatenateArrays,
    dictionaryKeys: dictionaryKeys,
    dictionaryValues: dictionaryValues,
    iterItems: iterItems,
    iterObjectFieldsRecursively: iterObjectFieldsRecursively
  };
});

