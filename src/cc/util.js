// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('base.quad');
base.require('tracing.trace_model.object_instance');

base.exportTo('cc', function() {
  var convertedNameCache = {};
  function convertNameToJSConvention(name) {
    if (name in convertedNameCache)
      return convertedNameCache[name];

    if (name[0] == '_' ||
        name[name.length - 1] == '_') {
      convertedNameCache[name] = name;
      return name;
    }

    var words = name.split('_');
    if (words.length == 1) {
      convertedNameCache[name] = words[0];
      return words[0];
    }

    for (var i = 1; i < words.length; i++)
      words[i] = words[i][0].toUpperCase() + words[i].substring(1);

    convertedNameCache[name] = words.join('');
    return convertedNameCache[name];
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

  function moveRequiredFieldsFromArgsToToplevel(object, fields) {
    for (var i = 0; i < fields.length; i++) {
      var key = fields[i];
      if (object.args[key] === undefined)
        throw Error('Expected field ' + key + ' not found in args');
      if (object[key] !== undefined)
        throw Error('Field ' + key + ' already in object');
      object[key] = object.args[key];
      delete object.args[key];
    }
  }

  function moveOptionalFieldsFromArgsToToplevel(object, fields) {
    for (var i = 0; i < fields.length; i++) {
      var key = fields[i];
      if (object.args[key] === undefined)
        continue;
      if (object[key] !== undefined)
        throw Error('Field ' + key + ' already in object');
      object[key] = object.args[key];
      delete object.args[key];
    }
  }

  function preInitializeObject(object) {
    preInitializeObjectInner(object.args, false);
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
        (object instanceof tracing.trace_model.ObjectSnapshot ||
         object instanceof tracing.trace_model.ObjectInstance))
      return;

    for (var key in object) {
      var newKey = convertNameToJSConvention(key);
      if (newKey != key) {
        var value = object[key];
        delete object[key];
        object[newKey] = value;
        key = newKey;
      }

      if (/Quad$/.test(key) && !(object[key] instanceof base.Quad)) {
        var q;
        try {
          q = base.Quad.From8Array(object[key]);
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
    preInitializeObject: preInitializeObject,
    convertNameToJSConvention: convertNameToJSConvention,
    moveRequiredFieldsFromArgsToToplevel: moveRequiredFieldsFromArgsToToplevel,
    moveOptionalFieldsFromArgsToToplevel: moveOptionalFieldsFromArgsToToplevel
  };
});
