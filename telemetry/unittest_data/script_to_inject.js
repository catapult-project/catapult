// Copyright 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

(function() {
if (window.parent != window)  // Ignore subframes.
  return;
if (!window.index) {
  window.index = 1;
}

window.addEventListener('load', function(){
  window.load_event_captured = true;
});
})();
