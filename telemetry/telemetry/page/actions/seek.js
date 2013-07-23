// Copyright 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// This file performs actions on media elements.
(function() {
  function seekMedia(selector, seekTime, logSeekTime) {
    // Performs the "Seek" action on media satisfying selector.
    var mediaElements = window.__findMediaElements(selector);
    for (var i = 0; i < mediaElements.length; i++) {
      seek(mediaElements[i], seekTime, logSeekTime);
    }
  }

  function seek(element, seekTime, logSeekTime) {
    if (element instanceof HTMLMediaElement)
      seekHTML5Element(element, seekTime, logSeekTime);
    else
      console.error('Can not seek non HTML5 media elements.');
  }

  function seekHTML5Element(element, seekTime, logSeekTime) {
    element['seeked_completed'] = false;
    var onSeeked = function(e) {
      element[e.type + '_completed'] = true;
      element.removeEventListener('seeked', onSeeked);
    };
    function onError(e) {
      console.error('Error playing media :' + e.type);
    }
    element.addEventListener('error', onError);
    element.addEventListener('abort', onError);

    if (logSeekTime) {
      var willSeekEvent = document.createEvent('Event');
      willSeekEvent.initEvent('willSeek', false, false);
      willSeekEvent.seekLabel = seekTime;
      element.dispatchEvent(willSeekEvent);
    }
    element.addEventListener('seeked', onSeeked);
    try {
      element.currentTime = seekTime;
    } catch (err) {
      console.error('Cannot seek with network state: ' + element.networkState);
    }
  }

  window.__seekMedia = seekMedia;
})();
