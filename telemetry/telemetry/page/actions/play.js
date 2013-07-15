// Copyright 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// This file performs actions on media elements.
(function() {
  function findMediaElements(selector) {
    // Returns elements matching the selector, otherwise returns the first video
    // or audio tag element that can be found.
    // If selector == 'all', returns all media elements.
    if (selector == 'all') {
      return document.querySelectorAll('video, audio');
    } else if (selector) {
      return document.querySelectorAll(selector);
    } else {
      var media = document.getElementsByTagName('video');
      if (media.length > 0) {
        return [media[0]];
      } else {
        media = document.getElementsByTagName('audio');
        if (media.length > 0) {
          return [media[0]];
        }
      }
    }
    console.error('Could not find any media elements matching: ' + selector);
    return [];
  }

  function playMedia(selector) {
    // Performs the "Play" action on media satisfying selector.
    var mediaElements = findMediaElements(selector);
    for (var i = 0; i < mediaElements.length; i++) {
      console.log('Playing element: ' + mediaElements[i].src);
      play(mediaElements[i]);
    }
  }

  function play(element) {
    if (element instanceof HTMLMediaElement)
      playHTML5Element(element);
    else
      console.error('Can not play non HTML5 media elements.');
  }

  function playHTML5Element(element) {
    function logEventHappened(e) {
      element[e.type + '_completed'] = true;
    }
    function onError(e) {
      console.error('Error playing media :' + e.type);
    }
    element.addEventListener('playing', logEventHappened);
    element.addEventListener('ended', logEventHappened);
    element.addEventListener('error', onError);
    element.addEventListener('abort', onError);

    var willPlayEvent = document.createEvent('Event');
    willPlayEvent.initEvent('willPlay', false, false);
    element.dispatchEvent(willPlayEvent);
    element.play();
  }

  function hasEventCompleted(selector, event_name) {
    // Return true if the event_name fired for media satisfying the selector.
    var mediaElements = findMediaElements(selector);
    for (var i = 0; i < mediaElements.length; i++) {
      if (!mediaElements[i][event_name + '_completed'])
        return false;
    }
    return true;
  }

  window.__playMedia = playMedia;
  window.__hasEventCompleted = hasEventCompleted;
})();
