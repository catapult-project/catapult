// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.requireStylesheet('cc.picture_ops_list_view');

base.require('cc.constants');
base.require('cc.selection');
base.require('ui.list_view');
base.require('ui.dom_helpers');

base.exportTo('cc', function() {
  var ANNOTATION = 'Comment';
  var BEGIN_ANNOTATION = 'BeginCommentGroup';
  var END_ANNOTATION = 'EndCommentGroup';
  var ANNOTATION_ID = 'ID: ';
  var ANNOTATION_CLASS = 'CLASS: ';
  var ANNOTATION_TAG = 'TAG: ';

  var constants = cc.constants;

  /**
   * @constructor
   */
  var PictureOpsListView = ui.define('picture-ops-list-view');

  PictureOpsListView.prototype = {
    __proto__: HTMLUnknownElement.prototype,

    decorate: function() {
      this.opsList_ = new ui.ListView();
      this.appendChild(this.opsList_);

      this.selectedOp_ = undefined;
      this.selectedOpIndex_ = undefined;
      this.opsList_.addEventListener(
          'selection-changed', this.onSelectionChanged_.bind(this));

      this.picture_ = undefined;
    },

    get picture() {
      return this.picture_;
    },

    set picture(picture) {
      this.picture_ = picture;
      this.updateContents_();
    },

    updateContents_: function() {
      this.opsList_.clear();

      if (!this.picture_)
        return;

      var ops = this.picture_.getOps();
      if (!ops)
        return;

      ops = this.opsTaggedWithAnnotations_(ops);

      for (var i = 0; i < ops.length; i++) {
        var op = ops[i];
        var item = document.createElement('div');
        item.opIndex = op.opIndex;
        item.textContent = i + ') ' + op.cmd_string;

        // Display the element info associated with the op, if available.
        if (op.elementInfo.tag || op.elementInfo.id || op.elementInfo.class) {
          var elementInfo = document.createElement('span');
          elementInfo.classList.add('elementInfo');
          var tag = op.elementInfo.tag ? op.elementInfo.tag : 'unknown';
          var id = op.elementInfo.id ? 'id=' + op.elementInfo.id : undefined;
          var className = op.elementInfo.class ? 'class=' +
              op.elementInfo.class : undefined;
          elementInfo.textContent =
              '<' + tag + (id ? ' ' : '') +
              (id ? id : '') + (className ? ' ' : '') +
              (className ? className : '') + '>';
          item.appendChild(elementInfo);
        }

        // Display each of the Skia ops.
        op.info.forEach(function(info) {
          var infoItem = document.createElement('div');
          infoItem.textContent = info;
          item.appendChild(infoItem);
        });

        this.opsList_.appendChild(item);
      }
    },

    onSelectionChanged_: function(e) {
      var beforeSelectedOp = true;

      // Deselect on re-selection.
      if (this.opsList_.selectedElement === this.selectedOp_) {
        this.opsList_.selectedElement = undefined;
        beforeSelectedOp = false;
        this.selectedOpIndex_ = undefined;
      }

      this.selectedOp_ = this.opsList_.selectedElement;

      // Set selection on all previous ops.
      var ops = this.opsList_.children;
      for (var i = 0; i < ops.length; i++) {
        var op = ops[i];
        if (op === this.selectedOp_) {
          beforeSelectedOp = false;
          this.selectedOpIndex_ = op.opIndex;
        } else if (beforeSelectedOp) {
          op.setAttribute('beforeSelection', 'beforeSelection');
        } else {
          op.removeAttribute('beforeSelection');
        }
      }

      base.dispatchSimpleEvent(this, 'selection-changed', false);
    },

    get selectedOpIndex() {
      return this.selectedOpIndex_;
    },

    /**
     * Return Skia operations tagged by annotation.
     *
     * The ops returned from Picture.getOps() contain both Skia ops and
     * annotations threaded together. This function removes all annotations
     * from the list and tags each op with the associated annotations.
     * Additionally, the last {tag, id, class} is stored as elementInfo on
     * each op.
     *
     * @param {Array} ops Array of Skia operations and annotations.
     * @return {Array} Skia ops where op.annotations contains the associated
     *         annotations for a given op.
     */
    opsTaggedWithAnnotations_: function(ops) {
      // This algorithm works by walking all the ops and pushing any
      // annotations onto a stack. When a non-annotation op is found, the
      // annotations stack is traversed and stored with the op.
      var annotationGroups = new Array();
      var opsWithoutAnnotations = new Array();
      for (var opIndex = 0; opIndex < ops.length; opIndex++) {
        var op = ops[opIndex];
        op.opIndex = opIndex;
        switch (op.cmd_string) {
          case BEGIN_ANNOTATION:
            annotationGroups.push(new Array());
            break;
          case END_ANNOTATION:
            annotationGroups.pop();
            break;
          case ANNOTATION:
            annotationGroups[annotationGroups.length - 1].push(op);
            break;
          default:
            var annotations = new Array();
            var elementInfo = {};
            annotationGroups.forEach(function(annotationGroup) {
              elementInfo = {};
              annotationGroup.forEach(function(annotation) {
                annotation.info.forEach(function(info) {
                  if (info.indexOf(ANNOTATION_TAG) != -1)
                    elementInfo.tag = info.substring(
                        info.indexOf(ANNOTATION_TAG) +
                        ANNOTATION_TAG.length).toLowerCase();
                  else if (info.indexOf(ANNOTATION_ID) != -1)
                    elementInfo.id = info.substring(
                        info.indexOf(ANNOTATION_ID) +
                        ANNOTATION_ID.length);
                  else if (info.indexOf(ANNOTATION_CLASS) != -1)
                    elementInfo.class = info.substring(
                        info.indexOf(ANNOTATION_CLASS) +
                        ANNOTATION_CLASS.length);

                  annotations.push(info);
                });
              });
            });
            op.annotations = annotations;
            op.elementInfo = elementInfo;
            opsWithoutAnnotations.push(op);
        }
      }
      return opsWithoutAnnotations;
    }
  };

  return {
    PictureOpsListView: PictureOpsListView
  };
});
