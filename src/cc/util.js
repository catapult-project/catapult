// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.exportTo('cc', function() {
  function convertNameToJSConvention(name) {
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
        var newFieldName = convertNameToJSConvention(fieldName);
        if (newFieldName == fieldName)
          return;
        delete object[fieldName];
        object[newFieldName] = fieldValue;
      });
  }

  return {
    convertNameToJSConvention: convertNameToJSConvention,
    convertObjectFieldNamesToJSConventions: convertObjectFieldNamesToJSConventions
  };
});
