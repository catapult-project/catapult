// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

cr.define('cr.ui', function() {

  /**
   * The class name to set on the document element.
   * @const
   */
  var CLASS_NAME = 'focus-outline-visible';

  /**
   * This class sets a CSS class name on the HTML element of |doc| when the user
   * presses the tab key. It removes the class name when the user clicks
   * anywhere.
   *
   * This allows you to write CSS like this:
   *
   * html.focus-outline-visible my-element:focus {
   *   outline: 5px auto -webkit-focus-ring-color;
   * }
   *
   * And the outline will only be shown if the user uses the keyboard to get to
   * it.
   *
   * @param {Document} doc The document to attach the focus outline manager to.
   * @constructor
   */
  function FocusOutlineManager(doc) {
    this.classList_ = doc.documentElement.classList;
    var self = this;
    doc.addEventListener('keydown', function(e) {
      if (e.keyCode == 9)  // Tab
        self.visible = true;
    }, true);

    doc.addEventListener('mousedown', function(e) {
      self.visible = false;
    }, true);
  }

  FocusOutlineManager.prototype = {
    /**
     * Whether the focus outline should be visible.
     * @type {boolean}
     */
    set visible(visible) {
      if (visible)
        this.classList_.add(CLASS_NAME);
      else
        this.classList_.remove(CLASS_NAME);
    },
    get visible() {
      this.classList_.contains(CLASS_NAME);
    }
  };

  /**
   * Array of Document and FocusOutlineManager pairs.
   * @type {Array}
   */
  var docsToManager = [];

  /**
   * Gets a per document sigleton focus outline manager.
   * @param {Document} doc The document to get the |FocusOutlineManager| for.
   * @return {FocusOutlineManager} The per document singleton focus outline
   *     manager.
   */
  FocusOutlineManager.forDocument = function(doc) {
    for (var i = 0; i < docsToManager.length; i++) {
      if (doc == docsToManager[i][0])
        return docsToManager[i][1];
    }
    var manager = new FocusOutlineManager(doc);
    docsToManager.push([doc, manager]);
    return manager;
  };

  return {
    FocusOutlineManager: FocusOutlineManager
  };
});
