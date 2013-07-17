// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview Interactive visualizaiton of TraceModel objects
 * based loosely on gantt charts. Each thread in the TraceModel is given a
 * set of Tracks, one per subrow in the thread. The TimelineTrackView class
 * acts as a controller, creating the individual tracks, while Tracks
 * do actual drawing.
 *
 * Visually, the TimelineTrackView produces (prettier) visualizations like the
 * following:
 *    Thread1:  AAAAAAAAAA         AAAAA
 *                  BBBB              BB
 *    Thread2:     CCCCCC                 CCCCC
 *
 */
base.requireStylesheet('tracing.timeline_track_view');
base.require('base.events');
base.require('base.properties');
base.require('base.settings');
base.require('tracing.filter');
base.require('tracing.selection');
base.require('tracing.timeline_viewport');
base.require('tracing.mouse_mode_constants');
base.require('tracing.tracks.drawing_container');
base.require('tracing.tracks.trace_model_track');
base.require('tracing.tracks.ruler_track');
base.require('ui');
base.require('ui.mouse_mode_selector');

base.exportTo('tracing', function() {

  var Selection = tracing.Selection;
  var Viewport = tracing.TimelineViewport;
  var MIN_SELECTION_DISTANCE = 4;

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
   * Renders a TraceModel into a div element, making one
   * Track for each subrow in each thread of the model, managing
   * overall track layout, and handling user interaction with the
   * viewport.
   *
   * @constructor
   * @extends {HTMLDivElement}
   */
  var TimelineTrackView = ui.define('div');

  TimelineTrackView.prototype = {
    __proto__: HTMLDivElement.prototype,

    model_: null,

    decorate: function() {

      this.classList.add('timeline-track-view');

      this.categoryFilter_ = new tracing.CategoryFilter();

      this.viewport_ = new Viewport(this);
      this.viewportStateAtMouseDown_ = null;

      this.rulerTrackContainer_ =
          new tracing.tracks.DrawingContainer(this.viewport_);
      this.appendChild(this.rulerTrackContainer_);
      this.rulerTrackContainer_.invalidate();

      this.rulerTrack_ = new tracing.tracks.RulerTrack(this.viewport_);
      this.rulerTrackContainer_.appendChild(this.rulerTrack_);

      this.modelTrackContainer_ =
          new tracing.tracks.DrawingContainer(this.viewport_);
      this.appendChild(this.modelTrackContainer_);
      this.modelTrackContainer_.style.display = 'block';
      this.modelTrackContainer_.invalidate();

      this.viewport_.modelTrackContainer = this.modelTrackContainer_;

      this.modelTrack_ = new tracing.tracks.TraceModelTrack(this.viewport_);
      this.modelTrackContainer_.appendChild(this.modelTrack_);

      this.mouseModeSelector_ = new ui.MouseModeSelector(this);
      this.appendChild(this.mouseModeSelector_);

      this.dragBox_ = this.ownerDocument.createElement('div');
      this.dragBox_.className = 'drag-box';
      this.appendChild(this.dragBox_);
      this.hideDragBox_();

      this.bindEventListener_(document, 'keypress', this.onKeypress_, this);

      this.bindEventListener_(document, 'beginpan', this.onBeginPanScan_, this);
      this.bindEventListener_(document, 'updatepan',
          this.onUpdatePanScan_, this);
      this.bindEventListener_(document, 'endpan', this.onEndPanScan_, this);

      this.bindEventListener_(document, 'beginselection',
          this.onBeginSelection_, this);
      this.bindEventListener_(document, 'updateselection',
          this.onUpdateSelection_, this);
      this.bindEventListener_(document, 'endselection',
          this.onEndSelection_, this);

      this.bindEventListener_(document, 'beginzoom', this.onBeginZoom_, this);
      this.bindEventListener_(document, 'updatezoom', this.onUpdateZoom_, this);
      this.bindEventListener_(document, 'endzoom', this.onEndZoom_, this);

      this.bindEventListener_(document, 'keydown', this.onKeydown_, this);
      this.bindEventListener_(document, 'keyup', this.onKeyup_, this);

      this.addEventListener('mousemove', this.onMouseMove_);
      this.addEventListener('dblclick', this.onDblClick_);

      this.mouseViewPosAtMouseDown_ = {x: 0, y: 0};
      this.lastMouseViewPos_ = {x: 0, y: 0};
      this.selection_ = new Selection();

      this.isPanningAndScanning_ = false;
      this.isZooming_ = false;

    },

    distanceCoveredInPanScan_: function(e) {
      var x = this.lastMouseViewPos_.x - this.mouseViewPosAtMouseDown_.x;
      var y = this.lastMouseViewPos_.y - this.mouseViewPosAtMouseDown_.y;

      return Math.sqrt(x * x + y * y);
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
      this.modelTrackContainer_.invalidate();

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
      this.modelTrack_.categoryFilter = this.categoryFilter;

      // Set up a reasonable viewport.
      if (modelInstanceChanged)
        this.viewport_.setWhenPossible(this.setInitialViewport_.bind(this));

      base.setPropertyAndDispatchChange(this, 'model', model);
    },

    get hasVisibleContent() {
      return this.modelTrack_.hasVisibleContent;
    },

    setInitialViewport_: function() {
      var w = this.modelTrackContainer_.canvas.width;

      var min;
      var range;

      if (this.model_.bounds.isEmpty) {
        min = 0;
        range = 1000;
      } else if (this.model_.bounds.range == 0) {
        min = this.model_.bounds.min;
        range = 1000;
      } else {
        min = this.model_.bounds.min;
        range = this.model_.bounds.range;
      }
      var boost = range * 0.15;
      this.viewport_.xSetWorldBounds(min - boost,
                                     min + range + boost,
                                     w);
    },

    /**
     * @param {Filter} filter The filter to use for finding matches.
     * @param {Selection} selection The selection to add matches to.
     * @return {Array} An array of objects that match the provided
     * TitleFilter.
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
      if (this.activeElement instanceof tracing.FindControl)
        return false;
      if (!this.focusElement_)
        return true;
      if (this.focusElement.tabIndex >= 0) {
        if (document.activeElement == this.focusElement)
          return true;
        return ui.elementIsChildOf(document.activeElement, this.focusElement);
      }
      return true;
    },

    onMouseMove_: function(e) {

      // Zooming requires the delta since the last mousemove so we need to avoid
      // tracking it when the zoom interaction is active.
      if (this.isZooming_)
        return;

      this.storeLastMousePos_(e);
    },

    onKeypress_: function(e) {
      var mouseModeConstants = tracing.mouseModeConstants;
      var vp = this.viewport_;
      if (!this.listenToKeys_)
        return;
      if (document.activeElement.nodeName == 'INPUT')
        return;
      var viewWidth = this.modelTrackContainer_.canvas.clientWidth;
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
          this.zoomToSelection();
          break;
      }
    },

    // Not all keys send a keypress.
    onKeydown_: function(e) {
      if (!this.listenToKeys_)
        return;
      var sel;
      var mouseModeConstants = tracing.mouseModeConstants;
      var vp = this.viewport_;
      var viewWidth = this.modelTrackContainer_.canvas.clientWidth;

      switch (e.keyCode) {
        case 37:   // left arrow
          sel = this.selection.getShiftedSelection(-1);
          if (sel) {
            this.selection = sel;
            this.panToSelection();
            e.preventDefault();
          } else {
            vp.panX += vp.xViewVectorToWorld(viewWidth * 0.1);
          }
          break;
        case 39:   // right arrow
          sel = this.selection.getShiftedSelection(1);
          if (sel) {
            this.selection = sel;
            this.panToSelection();
            e.preventDefault();
          } else {
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
    },

    onKeyup_: function(e) {
      if (!this.listenToKeys_)
        return;
      if (!e.shiftKey) {
        if (this.dragBeginEvent_) {
          this.setDragBoxPosition_(this.dragBoxXStart_, this.dragBoxYStart_,
              this.dragBoxXEnd_, this.dragBoxYEnd_);
        }
      }

    },

    /**
     * Zoom in or out on the timeline by the given scale factor.
     * @param {integer} scale The scale factor to apply.  If <1, zooms out.
     */
    zoomBy_: function(scale) {
      var vp = this.viewport_;
      var viewWidth = this.modelTrackContainer_.canvas.clientWidth;
      var pixelRatio = window.devicePixelRatio || 1;
      var curMouseV = this.lastMouseViewPos_.x * pixelRatio;
      var curCenterW = vp.xViewToWorld(curMouseV);
      vp.scaleX = vp.scaleX * scale;
      vp.xPanWorldPosToViewPos(curCenterW, curMouseV, viewWidth);
    },

    /**
     * Zoom into the current selection.
     */
    zoomToSelection: function() {
      if (!this.selection || !this.selection.length)
        return;

      var bounds = this.selection.bounds;
      if (!bounds.range)
        return;

      var worldCenter = bounds.center;
      var worldRangeHalf = bounds.range * 0.5;
      var boost = worldRangeHalf * 0.5;
      this.viewport_.xSetWorldBounds(worldCenter - worldRangeHalf - boost,
                                     worldCenter + worldRangeHalf + boost,
                                     this.modelTrackContainer_.canvas.width);
    },

    /**
     * Pan the view so the current selection becomes visible.
     */
    panToSelection: function() {
      if (!this.selection || !this.selection.length)
        return;

      var bounds = this.selection.bounds;
      var worldCenter = bounds.center;
      var viewWidth = this.modelTrackContainer_.canvas.width;

      if (!bounds.range) {
        if (this.viewport_.xWorldToView(bounds.center) < 0 ||
            this.viewport_.xWorldToView(bounds.center) > viewWidth) {
          this.viewport_.xPanWorldPosToViewPos(
              worldCenter, 'center', viewWidth);
        }
        return;
      }

      var worldRangeHalf = bounds.range * 0.5;
      var boost = worldRangeHalf * 0.5;
      this.viewport_.xPanWorldBoundsIntoView(
          worldCenter - worldRangeHalf - boost,
          worldCenter + worldRangeHalf + boost,
          viewWidth);

      this.viewport_.xPanWorldBoundsIntoView(bounds.min, bounds.max, viewWidth);
    },

    get keyHelp() {
      var mod = navigator.platform.indexOf('Mac') == 0 ? 'cmd' : 'ctrl';
      var help = 'Qwerty Controls\n' +
          ' w/s                   : Zoom in/out     (with shift: go faster)\n' +
          ' a/d                   : Pan left/right\n\n' +
          'Dvorak Controls\n' +
          ' ,/o                   : Zoom in/out     (with shift: go faster)\n' +
          ' a/e                   : Pan left/right\n\n' +
          'Mouse Controls\n' +
          ' drag (Selection mode) : Select slices   (with ' + mod +
                                                        ': zoom to slices)\n' +
          ' drag (Pan mode)       : Pan left/right/up/down)\n\n';

      if (this.focusElement.tabIndex) {
        help +=
            ' <-                 : Select previous event on current ' +
            'timeline\n' +
            ' ->                 : Select next event on current timeline\n';
      } else {
        help += 'General Navigation\n' +
            ' g/General          : Shows grid at the start/end of the ' +
            ' selected task\n' +
            ' <-,^TAB            : Select previous event on current ' +
            'timeline\n' +
            ' ->, TAB            : Select next event on current timeline\n';
      }
      help +=
          '\n' +
          'Space to switch between select / pan modes\n' +
          'Shift to temporarily switch between select / pan modes\n' +
          'Scroll to zoom in/out (in pan mode)\n' +
          'Dbl-click to add timing markers\n' +
          'f to zoom into selection\n' +
          'z to reset zoom and pan to initial view\n' +
          '/ to search\n';
      return help;
    },

    get selection() {
      return this.selection_;
    },

    set selection(selection) {
      if (!(selection instanceof Selection))
        throw new Error('Expected Selection');

      // Clear old selection.
      var i;
      for (i = 0; i < this.selection_.length; i++)
        this.selection_[i].selected = false;

      this.selection_.clear();
      this.selection_.addSelection(selection);

      base.dispatchSimpleEvent(this, 'selectionChange');
      for (i = 0; i < this.selection_.length; i++)
        this.selection_[i].selected = true;
      if (this.selection_.length &&
          this.selection_[0].track)
        this.selection_[0].track.scrollIntoViewIfNeeded();
      this.viewport_.dispatchChangeEvent(); // Triggers a redraw.
    },

    hideDragBox_: function() {
      this.dragBox_.style.left = '-1000px';
      this.dragBox_.style.top = '-1000px';
      this.dragBox_.style.width = 0;
      this.dragBox_.style.height = 0;
    },

    setDragBoxPosition_: function(xStart, yStart, xEnd, yEnd) {
      var loY = Math.min(yStart, yEnd);
      var hiY = Math.max(yStart, yEnd);
      var loX = Math.min(xStart, xEnd);
      var hiX = Math.max(xStart, xEnd);
      var modelTrackRect = this.modelTrack_.getBoundingClientRect();
      var dragRect = {left: loX, top: loY, width: hiX - loX, height: hiY - loY};

      dragRect.right = dragRect.left + dragRect.width;
      dragRect.bottom = dragRect.top + dragRect.height;

      var modelTrackContainerRect =
          this.modelTrackContainer_.getBoundingClientRect();
      var clipRect = {
        left: modelTrackContainerRect.left,
        top: modelTrackContainerRect.top,
        right: modelTrackContainerRect.right,
        bottom: modelTrackContainerRect.bottom
      };

      var headingWidth = window.getComputedStyle(
          this.querySelector('heading')).width;
      var trackTitleWidth = parseInt(headingWidth);
      clipRect.left = clipRect.left + trackTitleWidth;

      var finalDragBox = intersectRect_(clipRect, dragRect);

      this.dragBox_.style.left = finalDragBox.left + 'px';
      this.dragBox_.style.width = finalDragBox.width + 'px';
      this.dragBox_.style.top = finalDragBox.top + 'px';
      this.dragBox_.style.height = finalDragBox.height + 'px';

      var pixelRatio = window.devicePixelRatio || 1;
      var canv = this.modelTrackContainer_.canvas;
      var loWX = this.viewport_.xViewToWorld(
          (loX - canv.offsetLeft) * pixelRatio);
      var hiWX = this.viewport_.xViewToWorld(
          (hiX - canv.offsetLeft) * pixelRatio);

      var roundedDuration = Math.round((hiWX - loWX) * 100) / 100;
      this.dragBox_.textContent = roundedDuration + 'ms';

      var e = new base.Event('selectionChanging');
      e.loWX = loWX;
      e.hiWX = hiWX;
      this.dispatchEvent(e);
    },

    onGridToggle_: function(left) {
      var tb = left ? this.selection_.bounds.min : this.selection_.bounds.max;

      // Toggle the grid off if the grid is on, the marker position is the same
      // and the same element is selected (same timebase).
      if (this.viewport_.gridEnabled &&
          this.viewport_.gridSide === left &&
          this.viewport_.gridTimebase === tb) {
        this.viewport_.gridside = undefined;
        this.viewport_.gridEnabled = false;
        this.viewport_.gridTimebase = undefined;
        return;
      }

      // Shift the timebase left until its just left of model_.bounds.min.
      var numInterfvalsSinceStart = Math.ceil((tb - this.model_.bounds.min) /
          this.viewport_.gridStep_);
      this.viewport_.gridTimebase = tb -
          (numInterfvalsSinceStart + 1) * this.viewport_.gridStep_;

      this.viewport_.gridEnabled = true;
      this.viewport_.gridSide = left;
      this.viewport_.gridTimebase = tb;
    },

    canBeginInteraction_: function(e) {
      if (e.button != 0)
        return false;

      // Ensure that we do not interfere with the user adding markers.
      if (ui.elementIsChildOf(e.target, this.rulerTrack_))
        return false;

      return true;
    },

    onDblClick_: function(e) {

      if (this.isPanningAndScanning_) {
        var endPanEvent = new base.Event('endpan');
        endPanEvent.data = e;
        this.onEndPanScan_(endPanEvent);
      }

      if (this.isZooming_) {
        var endZoomEvent = new base.Event('endzoom');
        endZoomEvent.data = e;
        this.onEndZoom_(endZoomEvent);
      }

      this.rulerTrack_.placeAndBeginDraggingMarker(e.clientX);
      e.preventDefault();
    },

    storeLastMousePos_: function(e) {
      this.lastMouseViewPos_ = this.extractRelativeMousePosition_(e);
    },

    extractRelativeMousePosition_: function(e) {
      var canv = this.modelTrackContainer_.canvas;
      return {
        x: e.clientX - canv.offsetLeft,
        y: e.clientY - canv.offsetTop
      };
    },

    storeInitialMouseDownPos_: function(e) {

      var position = this.extractRelativeMousePosition_(e);

      this.mouseViewPosAtMouseDown_.x = position.x;
      this.mouseViewPosAtMouseDown_.y = position.y;
    },

    focusElements_: function() {
      if (document.activeElement)
        document.activeElement.blur();
      if (this.focusElement.tabIndex >= 0)
        this.focusElement.focus();
    },

    storeInitialInteractionPositionsAndFocus_: function(mouseEvent) {

      this.storeInitialMouseDownPos_(mouseEvent);
      this.storeLastMousePos_(mouseEvent);

      this.focusElements_();
    },

    onBeginPanScan_: function(e) {
      var vp = this.viewport_;
      var mouseEvent = e.data;

      if (!this.canBeginInteraction_(mouseEvent))
        return;

      this.viewportStateAtMouseDown_ = vp.getStateInViewCoordinates();
      this.isPanningAndScanning_ = true;

      this.storeInitialInteractionPositionsAndFocus_(mouseEvent);
      mouseEvent.preventDefault();
    },

    onUpdatePanScan_: function(e) {
      if (!this.isPanningAndScanning_)
        return;

      var vp = this.viewport_;
      var viewWidth = this.modelTrackContainer_.canvas.clientWidth;
      var mouseEvent = e.data;

      var x = this.viewportStateAtMouseDown_.panX + (this.lastMouseViewPos_.x -
          this.mouseViewPosAtMouseDown_.x);
      var y = this.viewportStateAtMouseDown_.panY - (this.lastMouseViewPos_.y -
          this.mouseViewPosAtMouseDown_.y);

      vp.setStateInViewCoordinates({
        panX: x,
        panY: y
      });

      mouseEvent.preventDefault();
      mouseEvent.stopPropagation();

      this.storeLastMousePos_(mouseEvent);
    },

    onEndPanScan_: function(e) {
      var mouseEvent = e.data;
      this.isPanningAndScanning_ = false;

      this.storeLastMousePos_(mouseEvent);

      if (this.distanceCoveredInPanScan_(mouseEvent) > MIN_SELECTION_DISTANCE)
        return;

      this.dragBeginEvent_ = mouseEvent;
      this.onEndSelection_(e);

    },

    onBeginSelection_: function(e) {

      var mouseEvent = e.data;

      if (!this.canBeginInteraction_(mouseEvent))
        return;

      var canv = this.modelTrackContainer_.canvas;
      var rect = this.modelTrack_.getBoundingClientRect();
      var canvRect = canv.getBoundingClientRect();

      var inside = rect &&
          mouseEvent.clientX >= rect.left &&
          mouseEvent.clientX < rect.right &&
          mouseEvent.clientY >= rect.top &&
          mouseEvent.clientY < rect.bottom &&
          mouseEvent.clientX >= canvRect.left &&
          mouseEvent.clientX < canvRect.right;

      if (!inside)
        return;

      this.dragBeginEvent_ = mouseEvent;

      this.storeInitialInteractionPositionsAndFocus_(mouseEvent);
      mouseEvent.preventDefault();

    },

    onUpdateSelection_: function(e) {
      var mouseEvent = e.data;

      if (!this.dragBeginEvent_)
        return;

      // Update the drag box
      this.dragBoxXStart_ = this.dragBeginEvent_.clientX;
      this.dragBoxXEnd_ = mouseEvent.clientX;
      this.dragBoxYStart_ = this.dragBeginEvent_.clientY;
      this.dragBoxYEnd_ = mouseEvent.clientY;
      this.setDragBoxPosition_(this.dragBoxXStart_, this.dragBoxYStart_,
          this.dragBoxXEnd_, this.dragBoxYEnd_);

    },

    onEndSelection_: function(e) {

      if (!this.dragBeginEvent_)
        return;

      var mouseEvent = e.data;

      // Stop the dragging.
      this.hideDragBox_();
      var eDown = this.dragBeginEvent_ || mouseEvent;
      this.dragBeginEvent_ = null;

      // Figure out extents of the drag.
      var loY = Math.min(eDown.clientY, mouseEvent.clientY);
      var hiY = Math.max(eDown.clientY, mouseEvent.clientY);
      var loX = Math.min(eDown.clientX, mouseEvent.clientX);
      var hiX = Math.max(eDown.clientX, mouseEvent.clientX);
      var tracksContainerBoundingRect =
          this.modelTrackContainer_.getBoundingClientRect();
      var topBoundary = tracksContainerBoundingRect.height;

      // Convert to worldspace.
      var canv = this.modelTrackContainer_.canvas;
      var loVX = loX - canv.offsetLeft;
      var hiVX = hiX - canv.offsetLeft;

      // Figure out what has been hit.
      var selection = new Selection();
      this.modelTrack_.addIntersectingItemsInRangeToSelection(
          loVX, hiVX, loY, hiY, selection);

      // Activate the new selection, and zoom if ctrl key held down.
      this.selection = selection;
      if ((base.isMac && e.metaKey) || (!base.isMac && e.ctrlKey))
        this.zoomToSelection_();
    },

    onBeginZoom_: function(e) {

      var mouseEvent = e.data;

      if (!this.canBeginInteraction_(mouseEvent))
        return;

      this.isZooming_ = true;

      this.storeInitialInteractionPositionsAndFocus_(mouseEvent);
      mouseEvent.preventDefault();
    },

    onUpdateZoom_: function(e) {

      if (!this.isZooming_)
        return;
      var mouseEvent = e.data;
      var newPosition = this.extractRelativeMousePosition_(mouseEvent);

      var zoomScaleValue = 1 + (this.lastMouseViewPos_.y -
          newPosition.y) * 0.01;

      this.zoomBy_(zoomScaleValue);
      this.storeLastMousePos_(mouseEvent);
    },

    onEndZoom_: function(e) {
      this.isZooming_ = false;
    }
  };

  return {
    TimelineTrackView: TimelineTrackView
  };
});
