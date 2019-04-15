/* Copyright 2019 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

// Polyfill import() even though it works in Chrome, eslint doesn't support it
// until it enters stage 4: https://github.com/eslint/eslint/issues/7764
// https://github.com/uupaa/dynamic-import-polyfill/blob/master/importModule.js
function importModule(url) {
  return new Promise((resolve, reject) => {
    const vector = 'importModule' + Math.random();
    const script = document.createElement('script');
    const destructor = () => {
      delete window[vector];
      script.onerror = null;
      script.onload = null;
      script.remove();
      URL.revokeObjectURL(script.src);
      script.src = '';
    };
    script.type = 'module';
    script.onerror = () => {
      reject(new Error(`Failed to import: ${url}`));
      destructor();
    };
    script.onload = () => {
      resolve(window[vector]);
      destructor();
    };
    const a = document.createElement('a');
    a.setAttribute('href', url);
    const absURL = a.cloneNode(false).href;
    const loader = `import * as m from "${absURL}"; window.${vector} = m;`;
    const blob = new Blob([loader], {type: 'text/javascript'});
    script.src = URL.createObjectURL(blob);
    document.head.appendChild(script);
  });
}
