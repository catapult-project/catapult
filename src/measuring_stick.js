// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

base.exportTo('tracing', function() {

  /**
   * Uses an embedded iframe to measure provided elements without forcing layout
   * on the main document. You must call attach() on the stick before using it,
   * and call detach() on it when you are done using it.
   * @constructor
   * @extends {Object}
   */
  function MeasuringStick() {
    this.iframe_ = undefined;
  }

  MeasuringStick.prototype = {
    __proto__: Object.prototype,

    /**
     * Measures the provided element without forcing layout on the main
     * document.
     */
    measure: function(element) {
      this.iframe_.contentDocument.body.appendChild(element);
      var style = this.iframe_.contentWindow.getComputedStyle(element);
      var width = parseInt(style.width, 10);
      var height = parseInt(style.height, 10);
      this.iframe_.contentDocument.body.removeChild(element);
      return { width: width, height: height };
    },

    attach: function() {
      var iframe = document.createElement('iframe');
      iframe.style.cssText =
          'width:100%;height:0;border:0;visibility:hidden';
      document.body.appendChild(iframe);
      this.iframe_ = iframe;
      this.iframe_.contentDocument.body.style.cssText =
          'padding:0;margin:0;overflow:hidden';

      var stylesheets = document.querySelectorAll('link[rel=stylesheet]');
      for (var i = 0; i < stylesheets.length; i++) {
        var stylesheet = stylesheets[i];
        var link = this.iframe_.contentDocument.createElement('link');
        link.rel = 'stylesheet';
        link.href = stylesheet.href;
        this.iframe_.contentDocument.head.appendChild(link);
      }
    },

    detach: function() {
      document.body.removeChild(this.iframe_);
      this.iframe_ = undefined;
    }
  };

  return {
    MeasuringStick: MeasuringStick
  };
});
