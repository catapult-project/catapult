// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('base.quad');
base.require('tracing.model.object_instance');

base.exportTo('cc', function() {
  function convertNameToJSConvention(name) {
    if (name[0] == '_' ||
        name[name.length - 1] == '_')
      return name;

    var words = name.split('_');
    if (words.length == 1)
      return words[0];
    for (var i = 1; i < words.length; i++)
      words[i] = words[i][0].toUpperCase() + words[i].substring(1);
    return words.join('');
  }

  function convertObjectFieldNamesToJSConventions(object) {
    base.iterObjectFieldsRecursively(
        object,
        function(object, fieldName, fieldValue) {
          delete object[fieldName];
          object[newFieldName] = fieldValue;
          return newFieldName;
        });
  }

  function convertQuadSuffixedTypesToQuads(object) {
    base.iterObjectFieldsRecursively(
        object,
        function(object, fieldName, fieldValue) {
        });
  }

  function convertObject(object) {
    convertObjectFieldNamesToJSConventions(object);
    convertQuadSuffixedTypesToQuads(object);
  }

  function moveFieldsFromArgsToToplevel(object) {
    for (var key in object.args) {
      if (object[key] !== undefined)
        throw Error('Field ' + key + ' already in object');
      object[key] = object.args[key];
    }
    object.args = {};
  }

  function assertHasField(object, fieldName) {
    if (object[fieldName] !== undefined)
      return;
    throw new Error('Expected ' + fieldName);
  }

  function preInitializeObject(object) {
    preInitializeObjectInner(object, false);
  }

  function preInitializeObjectInner(object, hasRecursed) {
    if (!(object instanceof Object))
      return;

    if (object instanceof Array) {
      for (var i = 0; i < object.length; i++)
        preInitializeObjectInner(object[i], true);
      return;
    }

    if (hasRecursed &&
        (object instanceof tracing.model.ObjectSnapshot ||
         object instanceof tracing.model.ObjectInstance))
      return;

    for (var key in object) {
      var newKey = convertNameToJSConvention(key);
      if (newKey != key) {
        var value = object[key];
        delete object[key];
        object[newKey] = value;
        key = newKey;
      }

      if (/Quad$/.test(key)) {
        var q;
        try {
          q = base.QuadFrom8Array(object[key]);
        } catch (e) {
          console.log(e);
        }
        object[key] = q;
        continue;
      }

      preInitializeObjectInner(object[key], true);
    }
  }

  return {
    assertHasField: assertHasField,
    preInitializeObject: preInitializeObject,
    convertNameToJSConvention: convertNameToJSConvention,
    moveFieldsFromArgsToToplevel: moveFieldsFromArgsToToplevel
  };
});
