// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

cr.define('tracing', function() {
  /**
   * Uses an embedded iframe to measure provided elements without forcing layout
   * on the main document.
   * @constructor
   * @extends {Object}
   */
  function MeasuringStick() {
    var iframe = document.createElement('iframe');
    iframe.style.cssText = 'width:100%;height:0;border:0;visibility:hidden';
    document.body.appendChild(iframe);
    this._doc = iframe.contentDocument;
    this._window = iframe.contentWindow;
    this._doc.body.style.cssText = 'padding:0;margin:0;overflow:hidden';

    var stylesheets = document.querySelectorAll('link[rel=stylesheet]');
    for (var i = 0; i < stylesheets.length; i++) {
      var stylesheet = stylesheets[i];
      var link = this._doc.createElement('link');
      link.rel = 'stylesheet';
      link.href = stylesheet.href;
      this._doc.head.appendChild(link);
    }
  }

  MeasuringStick.prototype = {
    __proto__: Object.prototype,

    /**
     * Measures the provided element without forcing layout on the main
     * document.
     */
    measure: function(element) {
      this._doc.body.appendChild(element);
      var style = this._window.getComputedStyle(element);
      var width = parseInt(style.width, 10);
      var height = parseInt(style.height, 10);
      this._doc.body.removeChild(element);
      return { width: width, height: height };
    }
  };

  return {
    MeasuringStick: MeasuringStick
  };
});
