// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview Interactive visualizaiton of TimelineModel objects
 * based loosely on gantt charts. Each thread in the TimelineModel is given a
 * set of TimelineTracks, one per subrow in the thread. The Timeline class
 * acts as a controller, creating the individual tracks, while TimelineTracks
 * do actual drawing.
 *
 * Visually, the Timeline produces (prettier) visualizations like the following:
 *    Thread1:  AAAAAAAAAA         AAAAA
 *                  BBBB              BB
 *    Thread2:     CCCCCC                 CCCCC
 *
 */
base.requireStylesheet('timeline');
base.require('event_target');
base.require('measuring_stick');
base.require('timeline_filter');
base.require('timeline_selection');
base.require('timeline_viewport');
base.require('tracks.timeline_model_track');
base.require('tracks.timeline_viewport_track');
base.require('ui');

base.exportTo('tracing', function() {

  var TimelineSelection = tracing.TimelineSelection;
  var TimelineViewport = tracing.TimelineViewport;

  function intersectRect_(r1, r2) {
    var results = new Object;
    if (r2.left > r1.right || r2.right < r1.left ||
         r2.top > r1.bottom || r2.bottom < r1.top) {
      return false;
    }
    results.left = Math.max(r1.left, r2.left);
    results.top = Math.max(r1.top, r2.top);
    results.right = Math.min(r1.right, r2.right);
    results.bottom = Math.min(r1.bottom, r2.bottom);
    results.width = (results.right - results.left);
    results.height = (results.bottom - results.top);
    return results;
  }

  /**
   * Renders a TimelineModel into a div element, making one
   * TimelineTrack for each subrow in each thread of the model, managing
   * overall track layout, and handling user interaction with the
   * viewport.
   *
   * @constructor
   * @extends {HTMLDivElement}
   */
  var Timeline = base.ui.define('div');

  Timeline.prototype = {
    __proto__: HTMLDivElement.prototype,

    model_: null,

    decorate: function() {
      this.classList.add('timeline');

      this.categoryFilter_ = new tracing.TimelineCategoryFilter();

      this.viewport_ = new TimelineViewport(this);

      // Add the viewport track.
      this.viewportTrack_ = new tracks.TimelineViewportTrack();
      this.viewportTrack_.viewport = this.viewport_;
      this.appendChild(this.viewportTrack_);

      this.modelTrackContainer_ = document.createElement('div');
      this.modelTrackContainer_.className = 'timeline-model-track-container';
      this.appendChild(this.modelTrackContainer_);

      this.modelTrack_ = new tracks.TimelineModelTrack();
      this.modelTrackContainer_.appendChild(this.modelTrack_);

      this.dragBox_ = this.ownerDocument.createElement('div');
      this.dragBox_.className = 'timeline-drag-box';
      this.appendChild(this.dragBox_);
      this.hideDragBox_();

      this.bindEventListener_(document, 'keypress', this.onKeypress_, this);
      this.bindEventListener_(document, 'keydown', this.onKeydown_, this);
      this.bindEventListener_(document, 'keyup', this.onKeyup_, this);
      this.bindEventListener_(document, 'mousemove', this.onMouseMove_, this);
      this.bindEventListener_(document, 'mouseup', this.onMouseUp_, this);

      this.addEventListener('mousewheel', this.onMouseWheel_);
      this.addEventListener('mousedown', this.onMouseDown_);
      this.addEventListener('dblclick', this.onDblClick_);

      this.lastMouseViewPos_ = {x: 0, y: 0};
      this.maxHeadingWidth_ = 0;

      this.selection_ = new TimelineSelection();
    },

    /**
     * Wraps the standard addEventListener but automatically binds the provided
     * func to the provided target, tracking the resulting closure. When detach
     * is called, these listeners will be automatically removed.
     */
    bindEventListener_: function(object, event, func, target) {
      if (!this.boundListeners_)
        this.boundListeners_ = [];
      var boundFunc = func.bind(target);
      this.boundListeners_.push({object: object,
        event: event,
        boundFunc: boundFunc});
      object.addEventListener(event, boundFunc);
    },

    detach: function() {
      this.modelTrack_.detach();

      for (var i = 0; i < this.boundListeners_.length; i++) {
        var binding = this.boundListeners_[i];
        binding.object.removeEventListener(binding.event, binding.boundFunc);
      }
      this.boundListeners_ = undefined;
      this.viewport_.detach();
    },

    get viewport() {
      return this.viewport_;
    },

    get categoryFilter() {
      return this.categoryFilter_;
    },

    set categoryFilter(filter) {
      this.categoryFilter_ = filter;
      this.modelTrack_.categoryFilter = filter;
    },

    get model() {
      return this.model_;
    },

    set model(model) {
      if (!model)
        throw new Error('Model cannot be null');

      var modelInstanceChanged = this.model_ != model;
      this.model_ = model;
      this.modelTrack_.model = model;
      this.modelTrack_.viewport = this.viewport_;
      this.modelTrack_.categoryFilter = this.categoryFilter;
      this.viewportTrack_.headingWidth = this.modelTrack_.headingWidth;

      // Set up a reasonable viewport.
      if (modelInstanceChanged)
        this.viewport_.setWhenPossible(this.setInitialViewport_.bind(this));
    },

    get numVisibleTracks() {
      return this.modelTrack_.numVisibleTracks;
    },

    setInitialViewport_: function() {
      var w = this.firstCanvas.width;
      var boost =
          (this.model_.maxTimestamp - this.model_.minTimestamp) * 0.15;
      this.viewport_.xSetWorldRange(this.model_.minTimestamp - boost,
                                    this.model_.maxTimestamp + boost,
                                    w);
    },

    /**
     * @param {TimelineFilter} filter The filter to use for finding matches.
     * @param {TimelineSelection} selection The selection to add matches to.
     * @return {Array} An array of objects that match the provided
     * TimelineTitleFilter.
     */
    addAllObjectsMatchingFilterToSelection: function(filter, selection) {
      this.modelTrack_.addAllObjectsMatchingFilterToSelection(filter,
                                                              selection);
    },

    /**
     * @return {Element} The element whose focused state determines
     * whether to respond to keyboard inputs.
     * Defaults to the parent element.
     */
    get focusElement() {
      if (this.focusElement_)
        return this.focusElement_;
      return this.parentElement;
    },

    /**
     * Sets the element whose focus state will determine whether
     * to respond to keybaord input.
     */
    set focusElement(value) {
      this.focusElement_ = value;
    },

    get listenToKeys_() {
      if (!this.viewport_.isAttachedToDocument_)
        return false;
      if (this.activeElement instanceof tracing.TimelineFindControl)
        return false;
      if (!this.focusElement_)
        return true;
      if (this.focusElement.tabIndex >= 0)
        return document.activeElement == this.focusElement;
      return true;
    },

    onKeypress_: function(e) {
      var vp = this.viewport_;
      if (!this.firstCanvas)
        return;
      if (!this.listenToKeys_)
        return;
      if (document.activeElement.nodeName == 'INPUT')
        return;
      var viewWidth = this.firstCanvas.clientWidth;
      var curMouseV, curCenterW;
      switch (e.keyCode) {
        case 119:  // w
        case 44:   // ,
          this.zoomBy_(1.5);
          break;
        case 115:  // s
        case 111:  // o
          this.zoomBy_(1 / 1.5);
          break;
        case 103:  // g
          this.onGridToggle_(true);
          break;
        case 71:  // G
          this.onGridToggle_(false);
          break;
        case 87:  // W
        case 60:  // <
          this.zoomBy_(10);
          break;
        case 83:  // S
        case 79:  // O
          this.zoomBy_(1 / 10);
          break;
        case 97:  // a
          vp.panX += vp.xViewVectorToWorld(viewWidth * 0.1);
          break;
        case 100:  // d
        case 101:  // e
          vp.panX -= vp.xViewVectorToWorld(viewWidth * 0.1);
          break;
        case 65:  // A
          vp.panX += vp.xViewVectorToWorld(viewWidth * 0.5);
          break;
        case 68:  // D
          vp.panX -= vp.xViewVectorToWorld(viewWidth * 0.5);
          break;
        case 48:  // 0
        case 122: // z
          this.setInitialViewport_();
          break;
        case 102:  // f
          this.zoomToSelection_();
          break;
      }
    },

    onMouseWheel_: function(e) {
      if (e.altKey) {
        var delta = e.wheelDeltaY / 120;
        var zoomScale = Math.pow(1.5, delta);
        this.zoomBy_(zoomScale);
        e.preventDefault();
      }
    },

    // Not all keys send a keypress.
    onKeydown_: function(e) {
      if (!this.listenToKeys_)
        return;
      var sel;
      var vp = this.viewport_;
      var viewWidth = this.firstCanvas.clientWidth;
      switch (e.keyCode) {
        case 37:   // left arrow
          sel = this.selection.getShiftedSelection(-1);
          if (sel) {
            this.setSelectionAndMakeVisible(sel);
            e.preventDefault();
          } else {
            if (!this.firstCanvas)
              return;
            vp.panX += vp.xViewVectorToWorld(viewWidth * 0.1);
          }
          break;
        case 39:   // right arrow
          sel = this.selection.getShiftedSelection(1);
          if (sel) {
            this.setSelectionAndMakeVisible(sel);
            e.preventDefault();
          } else {
            if (!this.firstCanvas)
              return;
            vp.panX -= vp.xViewVectorToWorld(viewWidth * 0.1);
          }
          break;
        case 9:    // TAB
          if (this.focusElement.tabIndex == -1) {
            if (e.shiftKey)
              this.selectPrevious_(e);
            else
              this.selectNext_(e);
            e.preventDefault();
          }
          break;
      }
      if (e.shiftKey && this.dragBeginEvent_) {
          var vertical = e.shiftKey;
          if (this.dragBeginEvent_) {
            this.setDragBoxPosition_(this.dragBoxXStart_, this.dragBoxYStart_,
                               this.dragBoxXEnd_, this.dragBoxYEnd_, vertical);
          }
      }
    },

    onKeyup_: function(e) {
      if (!this.listenToKeys_)
        return;
      if (!e.shiftKey) {
        if (this.dragBeginEvent_) {
          var vertical = e.shiftKey;
          this.setDragBoxPosition_(this.dragBoxXStart_, this.dragBoxYStart_,
                                this.dragBoxXEnd_, this.dragBoxYEnd_, vertical);
          }
      }
    },

    /**
     * Zoom in or out on the timeline by the given scale factor.
     * @param {integer} scale The scale factor to apply.  If <1, zooms out.
     */
    zoomBy_: function(scale) {
      if (!this.firstCanvas)
        return;
      var vp = this.viewport_;
      var viewWidth = this.firstCanvas.clientWidth;
      var curMouseV = this.lastMouseViewPos_.x;
      var curCenterW = vp.xViewToWorld(curMouseV);
      vp.scaleX = vp.scaleX * scale;
      vp.xPanWorldPosToViewPos(curCenterW, curMouseV, viewWidth);
    },

    /**
     * Zoom into the current selection.
     */
    zoomToSelection_: function() {
      if (!this.selection)
        return;
      var range = this.selection.range;
      var worldCenter = range.min + (range.max - range.min) * 0.5;
      var worldRange = (range.max - range.min) * 0.5;
      var boost = worldRange * 0.15;
      this.viewport_.xSetWorldRange(worldCenter - worldRange - boost,
                                    worldCenter + worldRange + boost,
                                    this.firstCanvas.width);
    },

    get keyHelp() {
      var mod = navigator.platform.indexOf('Mac') == 0 ? 'cmd' : 'ctrl';
      var help = 'Qwerty Controls\n' +
          ' w/s           : Zoom in/out    (with shift: go faster)\n' +
          ' a/d           : Pan left/right\n\n' +
          'Dvorak Controls\n' +
          ' ,/o           : Zoom in/out     (with shift: go faster)\n' +
          ' a/e           : Pan left/right\n\n' +
          'Mouse Controls\n' +
          ' drag          : Select slices   (with ' + mod +
                                                        ': zoom to slices)\n' +
          ' drag + shift  : Select all slices vertically\n\n';

      if (this.focusElement.tabIndex) {
        help +=
          ' <-            : Select previous event on current timeline\n' +
          ' ->            : Select next event on current timeline\n';
      } else {
        help += 'General Navigation\n' +
          ' g/General     : Shows grid at the start/end of the selected' +
                                                                  ' task\n' +
          ' <-,^TAB       : Select previous event on current timeline\n' +
          ' ->, TAB       : Select next event on current timeline\n';
      }
      help +=
          '\n' +
          'Alt + Scroll to zoom in/out\n' +
          'Dbl-click to zoom in; Shift dbl-click to zoom out\n' +
          'f to zoom into selection\n' +
          'z to reset zoom and pan to initial view\n';
      return help;
    },

    get selection() {
      return this.selection_;
    },

    set selection(selection) {
      if (!(selection instanceof TimelineSelection))
        throw new Error('Expected TimelineSelection');

      // Clear old selection.
      var i;
      for (i = 0; i < this.selection_.length; i++)
        this.selection_[i].selected = false;

      this.selection_ = selection;

      base.dispatchSimpleEvent(this, 'selectionChange');
      for (i = 0; i < this.selection_.length; i++)
        this.selection_[i].selected = true;
      this.viewport_.dispatchChangeEvent(); // Triggers a redraw.
    },

    setSelectionAndMakeVisible: function(selection, zoomAllowed) {
      if (!(selection instanceof TimelineSelection))
        throw new Error('Expected TimelineSelection');
      this.selection = selection;
      var range = this.selection.range;
      var size = this.viewport_.xWorldVectorToView(range.max - range.min);
      if (zoomAllowed && size < 50) {
        var worldCenter = range.min + (range.max - range.min) * 0.5;
        var worldRange = (range.max - range.min) * 5;
        this.viewport_.xSetWorldRange(worldCenter - worldRange * 0.5,
                                      worldCenter + worldRange * 0.5,
                                      this.firstCanvas.width);
        return;
      }

      this.viewport_.xPanWorldRangeIntoView(range.min, range.max,
                                            this.firstCanvas.width);
    },

    get firstCanvas() {
      if (this.viewportTrack_)
        return this.viewportTrack_.firstCanvas;
      if (this.modelTrack_)
        return this.modelTrack_.firstCanvas;
      return undefined;
    },

    hideDragBox_: function() {
      this.dragBox_.style.left = '-1000px';
      this.dragBox_.style.top = '-1000px';
      this.dragBox_.style.width = 0;
      this.dragBox_.style.height = 0;
    },

    setDragBoxPosition_: function(xStart, yStart, xEnd, yEnd, vertical) {
      var loY;
      var hiY;
      var loX = Math.min(xStart, xEnd);
      var hiX = Math.max(xStart, xEnd);
      var modelTrackRect = this.modelTrack_.getBoundingClientRect();

      if (vertical) {
        loY = modelTrackRect.top;
        hiY = modelTrackRect.bottom;
      } else {
        loY = Math.min(yStart, yEnd);
        hiY = Math.max(yStart, yEnd);
      }

      var dragRect = {left: loX, top: loY, width: hiX - loX, height: hiY - loY};
      dragRect.right = dragRect.left + dragRect.width;
      dragRect.bottom = dragRect.top + dragRect.height;
      var modelTrackContainerRect =
                              this.modelTrackContainer_.getBoundingClientRect();
      var clipRect = {
        left: modelTrackContainerRect.left,
        top: modelTrackContainerRect.top,
        right: modelTrackContainerRect.right,
        bottom: modelTrackContainerRect.bottom,
      };
      var trackTitleWidth = parseInt(this.modelTrack_.headingWidth);
      clipRect.left = clipRect.left + trackTitleWidth;

      var finalDragBox = intersectRect_(clipRect, dragRect);

      this.dragBox_.style.left = finalDragBox.left + 'px';
      this.dragBox_.style.width = finalDragBox.width + 'px';
      this.dragBox_.style.top = finalDragBox.top + 'px';
      this.dragBox_.style.height = finalDragBox.height + 'px';

      var canv = this.firstCanvas;
      var loWX = this.viewport_.xViewToWorld(loX - canv.offsetLeft);
      var hiWX = this.viewport_.xViewToWorld(hiX - canv.offsetLeft);

      var roundedDuration = Math.round((hiWX - loWX) * 100) / 100;
      this.dragBox_.textContent = roundedDuration + 'ms';

      var e = new base.Event('selectionChanging');
      e.loWX = loWX;
      e.hiWX = hiWX;
      this.dispatchEvent(e);
    },

    onGridToggle_: function(left) {
      var tb;
      if (left)
        tb = this.selection_.range.min;
      else
        tb = this.selection_.range.max;

      // Shift the timebase left until its just left of minTimestamp.
      var numInterfvalsSinceStart = Math.ceil((tb - this.model_.minTimestamp) /
          this.viewport_.gridStep_);
      this.viewport_.gridTimebase = tb -
          (numInterfvalsSinceStart + 1) * this.viewport_.gridStep_;
      this.viewport_.gridEnabled = true;
    },

    isChildOfThis_: function(el) {
      if (el == this)
        return;

      var isChildOfThis = false;
      var cur = el;
      while (cur.parentNode) {
        if (cur == this)
          return true;
        cur = cur.parentNode;
      }
      return false;
    },

    onMouseDown_: function(e) {
      if (e.button !== 0)
        return;

      if (e.shiftKey) {
        this.viewportTrack_.placeAndBeginDraggingMarker(e.clientX);
        return;
      }

      var canv = this.firstCanvas;
      var rect = this.modelTrack_.getBoundingClientRect();
      var canvRect = this.firstCanvas.getBoundingClientRect();

      var inside = rect &&
          e.clientX >= rect.left &&
          e.clientX < rect.right &&
          e.clientY >= rect.top &&
          e.clientY < rect.bottom &&
          e.clientX >= canvRect.left &&
          e.clientX < canvRect.right;

      if (!inside)
        return;

      var pos = {
        x: e.clientX - canv.offsetLeft,
        y: e.clientY - canv.offsetTop
      };

      var wX = this.viewport_.xViewToWorld(pos.x);

      this.dragBeginEvent_ = e;
      e.preventDefault();
      if (document.activeElement)
        document.activeElement.blur();
      if (this.focusElement.tabIndex >= 0)
        this.focusElement.focus();
    },

    onMouseMove_: function(e) {
      if (!this.firstCanvas)
        return;
      var canv = this.firstCanvas;
      var pos = {
        x: e.clientX - canv.offsetLeft,
        y: e.clientY - canv.offsetTop
      };

      // Remember position. Used during keyboard zooming.
      this.lastMouseViewPos_ = pos;

      // Update the drag box
      if (this.dragBeginEvent_) {
        this.dragBoxXStart_ = this.dragBeginEvent_.clientX;
        this.dragBoxXEnd_ = e.clientX;
        this.dragBoxYStart_ = this.dragBeginEvent_.clientY;
        this.dragBoxYEnd_ = e.clientY;
        var vertical = e.shiftKey;
        this.setDragBoxPosition_(this.dragBoxXStart_, this.dragBoxYStart_,
                                this.dragBoxXEnd_, this.dragBoxYEnd_, vertical);
      }
    },

    onMouseUp_: function(e) {
      var i;
      if (this.dragBeginEvent_) {
        // Stop the dragging.
        this.hideDragBox_();
        var eDown = this.dragBeginEvent_;
        this.dragBeginEvent_ = null;

        // Figure out extents of the drag.
        var loY;
        var hiY;
        var loX = Math.min(eDown.clientX, e.clientX);
        var hiX = Math.max(eDown.clientX, e.clientX);
        var tracksContainer = this.modelTrackContainer_.getBoundingClientRect();
        var topBoundary = tracksContainer.height;
        var vertical = e.shiftKey;
        if (vertical) {
          var modelTrackRect = this.modelTrack_.getBoundingClientRect();
          loY = modelTrackRect.top;
          hiY = modelTrackRect.bottom;
        } else {
          loY = Math.min(eDown.clientY, e.clientY);
          hiY = Math.max(eDown.clientY, e.clientY);
        }

        // Convert to worldspace.
        var canv = this.firstCanvas;
        var loVX = loX - canv.offsetLeft;
        var hiVX = hiX - canv.offsetLeft;

        // Figure out what has been hit.
        var selection = new TimelineSelection();
        this.modelTrack_.addIntersectingItemsInRangeToSelection(
            loVX, hiVX, loY, hiY, selection);

        // Activate the new selection, and zoom if ctrl key held down.
        this.selection = selection;
        var isMac = navigator.platform.indexOf('Mac') == 0;
        if ((isMac && e.metaKey) || (!isMac && e.ctrlKey)) {
          this.zoomToSelection_();
        }
      }
    },

    onDblClick_: function(e) {
      var canv = this.firstCanvas;

      var scale = 4;
      if (e.shiftKey)
        scale = 1 / scale;
      this.zoomBy_(scale);
      e.preventDefault();
    }
  };

  /**
   * The TimelineModel being viewed by the timeline
   * @type {TimelineModel}
   */
  base.defineProperty(Timeline, 'model', base.PropertyKind.JS);

  return {
    Timeline: Timeline
  };
});
