// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

tvcm.requireStylesheet('tracing.analysis.analysis_link');

tvcm.require('tvcm.ui');
tvcm.require('tracing.selection');
tvcm.require('tracing.analysis.util');

tvcm.exportTo('tracing.analysis', function() {

  var tsRound = tracing.analysis.tsRound;

  var RequestSelectionChangeEvent = tracing.RequestSelectionChangeEvent;

  /**
   * A clickable link that requests a change of selection to the return value of
   * this.selectionGenerator when clicked.
   *
   * @constructor
   */
  var AnalysisLink = tvcm.ui.define('a');

  AnalysisLink.prototype = {
    __proto__: HTMLAnchorElement.prototype,
    decorate: function() {
      this.classList.add('analysis-link');
      this.addEventListener('click', this.onClicked_.bind(this));
    },
    onClicked_: function() {
      var event = new RequestSelectionChangeEvent();
      event.selection = this.selectionGenerator();
      this.dispatchEvent(event);
    }
  };

  /**
   * Changes the selection to the given ObjectSnapshot when clicked.
   * @constructor
   */
  var ObjectSnapshotLink = tvcm.ui.define(
      'object-snapshot-link', AnalysisLink);

  ObjectSnapshotLink.prototype = {
    __proto__: AnalysisLink.prototype,

    decorate: function() {
      AnalysisLink.prototype.decorate.apply(this);
    },

    set objectSnapshot(snapshot) {
      this.textContent =
          snapshot.objectInstance.typeName + ' ' +
          snapshot.objectInstance.id + ' @ ' +
          tsRound(snapshot.ts) + ' ms';
      this.selectionGenerator = function() {
        var selection = new tracing.Selection();
        selection.push(snapshot);
        return selection;
      }.bind(this);
    }
  };

  /**
   * Changes the selection to the given ObjectInstance when clicked.
   * @constructor
   */
  var ObjectInstanceLink = tvcm.ui.define(
      'object-instance-link', AnalysisLink);

  ObjectInstanceLink.prototype = {
    __proto__: AnalysisLink.prototype,

    decorate: function() {
      AnalysisLink.prototype.decorate.apply(this);
    },

    set objectInstance(instance) {
      this.textContent = instance.typeName + ' ' + instance.id;
      this.selectionGenerator = function() {
        var selection = new tracing.Selection();
        selection.push(instance);
        return selection;
      }.bind(this);
    }
  };

  return {
    RequestSelectionChangeEvent: RequestSelectionChangeEvent,
    AnalysisLink: AnalysisLink,
    ObjectSnapshotLink: ObjectSnapshotLink,
    ObjectInstanceLink: ObjectInstanceLink
  };
});
