// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.requireStylesheet('tracing.analysis.generic_object_view');

base.require('base.utils');
base.require('tracing.analysis.analysis_link');
base.require('ui');

base.exportTo('tracing.analysis', function() {

  /**
   * @constructor
   */
  var GenericObjectView = ui.define('x-generic-object-view');

  GenericObjectView.prototype = {
    __proto__: HTMLUnknownElement.prototype,

    decorate: function() {
      this.object_ = undefined;
    },

    get object() {
      return this.object_;
    },

    set object(object) {
      this.object_ = object;
      this.updateContents_();
    },

    updateContents_: function() {
      this.textContent = '';

      this.appendElementsForType_('', this.object_, 0, 0, 5, '');
    },

    appendElementsForType_: function(
        label, object, indent, depth, maxDepth, suffix) {
      if (depth > maxDepth) {
        this.appendSimpleText_(
            label, indent, '<recursion limit reached>', suffix);
        return;
      }

      if (object === undefined) {
        this.appendSimpleText_(label, indent, 'undefined', suffix);
        return;
      }

      if (object === null) {
        this.appendSimpleText_(label, indent, 'null', suffix);
        return;
      }

      if (!(object instanceof Object)) {
        var type = typeof object;
        if (type == 'string') {
          this.appendSimpleText_(label, indent, '"' + object + '"', suffix);
        } else {
          this.appendSimpleText_(label, indent, object, suffix);
        }
        return;
      }

      if (object instanceof tracing.trace_model.ObjectSnapshot) {
        var link = new tracing.analysis.ObjectSnapshotLink(object);
        link.objectSnapshot = object;
        this.appendElementWithLabel_(label, indent, link, suffix);
        return;
      }

      if (object instanceof tracing.trace_model.ObjectInstance) {
        var link = new tracing.analysis.ObjectInstanceLink(object);
        link.objectInstance = object;
        this.appendElementWithLabel_(label, indent, link, suffix);
        return;
      }

      if (object instanceof Array) {
        this.appendElementsForArray_(
            label, object, indent, depth, maxDepth, suffix);
        return;
      }

      this.appendElementsForObject_(
          label, object, indent, depth, maxDepth, suffix);
    },

    appendElementsForArray_: function(
        label, object, indent, depth, maxDepth, suffix) {
      if (object.length == 0) {
        this.appendSimpleText_(label, indent, '[]', suffix);
        return;
      }

      this.appendElementsForType_(
          label + '[',
          object[0],
          indent, depth + 1, maxDepth,
          object.length > 1 ? ',' : ']' + suffix);
      for (var i = 1; i < object.length; i++) {
        this.appendElementsForType_(
            '',
            object[i],
            indent + label.length + 1, depth + 1, maxDepth,
            i < object.length - 1 ? ',' : ']' + suffix);
      }
      return;
    },

    appendElementsForObject_: function(
        label, object, indent, depth, maxDepth, suffix) {
      var keys = base.dictionaryKeys(object);
      if (keys.length == 0) {
        this.appendSimpleText_(label, indent, '{}', suffix);
        return;
      }

      this.appendElementsForType_(
          label + '{' + keys[0] + ': ',
          object[keys[0]],
          indent, depth, maxDepth,
          keys.length > 1 ? ',' : '}' + suffix);
      for (var i = 1; i < keys.length; i++) {
        this.appendElementsForType_(
            keys[i] + ': ',
            object[keys[i]],
            indent + label.length + 1, depth + 1, maxDepth,
            i < keys.length - 1 ? ',' : '}' + suffix);
      }
    },

    appendElementWithLabel_: function(label, indent, dataElement, suffix) {
      var row = document.createElement('div');

      var indentSpan = document.createElement('span');
      indentSpan.style.whiteSpace = 'pre';
      for (var i = 0; i < indent; i++)
        indentSpan.textContent += ' ';
      row.appendChild(indentSpan);

      var labelSpan = document.createElement('span');
      labelSpan.textContent = label;
      row.appendChild(labelSpan);

      row.appendChild(dataElement);
      var suffixSpan = document.createElement('span');
      suffixSpan.textContent = suffix;
      row.appendChild(suffixSpan);

      row.dataElement = dataElement;
      this.appendChild(row);
    },

    appendSimpleText_: function(label, indent, text, suffix) {
      var el = this.ownerDocument.createElement('span');
      el.textContent = text;
      this.appendElementWithLabel_(label, indent, el, suffix);
      return el;
    }

  };

  return {
    GenericObjectView: GenericObjectView
  };
});
