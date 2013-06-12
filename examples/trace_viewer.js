// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

console.log('foo');

var timelineViewEl;

function loadTraces(filenames, onTracesLoaded) {
  var traces = [];
  for (var i = 0; i < filenames.length; i++) {
    traces.push(undefined);
  }
  var numTracesPending = filenames.length;

  filenames.forEach(function(filename, i) {
    getAsync(filename, function(trace) {
      traces[i] = trace;
      numTracesPending--;
      if (numTracesPending == 0)
        onTracesLoaded(filenames, traces);
    });
  });
}

function getAsync(url, cb) {
  var req = new XMLHttpRequest();
  req.open('GET', url, true);
  req.onreadystatechange = function(aEvt) {
    if (req.readyState == 4) {
      window.setTimeout(function() {
        if (req.status == 200) {
          cb(req.responseText);
        } else {
          console.log('Failed to load ' + url);
        }
      }, 0);
    }
  };
  req.send(null);
}

function createViewFromTraces(filenames, traces) {
  var m = new tracing.TraceModel();
  m.importTraces(traces, true);

  timelineViewEl.model = m;
  timelineViewEl.tabIndex = 1;
  if (timelineViewEl.timeline)
    timelineViewEl.timeline.focusElement = timelineViewEl;
  timelineViewEl.viewTitle = filenames;
}

function onSelectionChange() {
  var select = document.querySelector('#trace_file');
  window.location.hash = '#' + select[select.selectedIndex].value;
}

function onHashChange() {
  var file = window.location.hash.substr(1);
  var select = document.querySelector('#trace_file');
  if (select[select.selectedIndex].value != file) {
    for (var i = 0; i < select.children.length; i++) {
      if (select.children[i].value == file) {
        select.selectedIndex = i;
        break;
      }
    }
  }
  reload();
}

function cleanFilename(file) {
  function upcase(letter) {
    return ' ' + letter.toUpperCase();
  }

  return file.replace(/_/g, ' ')
             .replace(/\.[^\.]*$/, '')
             .replace(/ ([a-z])/g, upcase)
             .replace(/^[a-z]/, upcase);
}

function reload() {
  var file = window.location.hash.substr(1);
  var filenames = ['../test_data/' + file];
  loadTraces(filenames, createViewFromTraces);
}

window.addEventListener('hashchange', onHashChange);

function domContentLoaded() {
  timelineViewEl = document.querySelector('.view');
  ui.decorate(timelineViewEl, tracing.TimelineView);

  getAsync('/json/examples', function(data) {
    var select = document.querySelector('#trace_file');
    var files = JSON.parse(data);

    for (var i = 0; i < files.length; ++i) {
      var opt = document.createElement('option');
      opt.value = files[i];
      opt.textContent = cleanFilename(files[i]);
      select.appendChild(opt);
    }
    select.selectedIndex = 0;
    select.onchange = onSelectionChange;

    if (!window.location.hash) {
      // This will trigger an onHashChange so no need to reload directly.
      window.location.hash = '#' + select[select.selectedIndex].value;
    } else {
      onHashChange();
    }
  });
}

if (document.readyState == 'interactive' || document.readyState == 'loading')
  domContentLoaded();
else
  document.addEventListener('DOMContentLoaded', domContentLoaded);
