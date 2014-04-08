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
tvcm.requireStylesheet('tvcm.ui.common');
tvcm.requireStylesheet('tracing.timeline_track_view');
tvcm.require('tvcm.events');
tvcm.require('tvcm.properties');
tvcm.require('tvcm.settings');
tvcm.require('tracing.filter');
tvcm.require('tracing.selection');
tvcm.require('tracing.timeline_viewport');
tvcm.require('tracing.timeline_display_transform_animations');
tvcm.require('tracing.timing_tool');
tvcm.require('tracing.trace_model.event');
tvcm.require('tracing.tracks.drawing_container');
tvcm.require('tracing.tracks.trace_model_track');
tvcm.require('tracing.tracks.ruler_track');
tvcm.require('tvcm.ui');
tvcm.require('tvcm.ui.mouse_mode_selector');

tvcm.exportTo('tracing', function() {

  var Selection = tracing.Selection;
  var SelectionState = tracing.trace_model.SelectionState;
  var Viewport = tracing.TimelineViewport;

  var tempDisplayTransform = new tracing.TimelineDisplayTransform();

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
  var TimelineTrackView = tvcm.ui.define('div');

  TimelineTrackView.prototype = {
    __proto__: HTMLDivElement.prototype,

    model_: null,

    decorate: function() {

      this.classList.add('timeline-track-view');

      this.viewport_ = new Viewport(this);
      this.viewportDisplayTransformAtMouseDown_ = null;

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

      this.timingTool_ = new tracing.TimingTool(this.viewport_,
                                                this);

      this.initMouseModeSelector();

      this.dragBox_ = this.ownerDocument.createElement('div');
      this.dragBox_.className = 'drag-box';
      this.appendChild(this.dragBox_);
      this.hideDragBox_();

      this.bindEventListener_(document, 'keypress', this.onKeypress_, this);
      this.bindEventListener_(document, 'keydown', this.onKeydown_, this);
      this.bindEventListener_(document, 'keyup', this.onKeyup_, this);

      this.bindEventListener_(this, 'dblclick', this.onDblClick_, this);
      this.bindEventListener_(this, 'mousewheel', this.onMouseWheel_, this);

      this.addEventListener('mousemove', this.onMouseMove_);

      this.mouseViewPosAtMouseDown_ = {x: 0, y: 0};
      this.lastMouseViewPos_ = {x: 0, y: 0};

      this.selection_ = new Selection();
      this.highlight_ = new Selection();

      this.isPanningAndScanning_ = false;
      this.isZooming_ = false;
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

    initMouseModeSelector: function() {
      this.mouseModeSelector_ = new tvcm.ui.MouseModeSelector(this);
      this.appendChild(this.mouseModeSelector_);

      this.mouseModeSelector_.addEventListener('beginpan',
          this.onBeginPanScan_.bind(this));
      this.mouseModeSelector_.addEventListener('updatepan',
          this.onUpdatePanScan_.bind(this));
      this.mouseModeSelector_.addEventListener('endpan',
          this.onEndPanScan_.bind(this));

      this.mouseModeSelector_.addEventListener('beginselection',
          this.onBeginSelection_.bind(this));
      this.mouseModeSelector_.addEventListener('updateselection',
          this.onUpdateSelection_.bind(this));
      this.mouseModeSelector_.addEventListener('endselection',
          this.onEndSelection_.bind(this));

      this.mouseModeSelector_.addEventListener('beginzoom',
          this.onBeginZoom_.bind(this));
      this.mouseModeSelector_.addEventListener('updatezoom',
          this.onUpdateZoom_.bind(this));
      this.mouseModeSelector_.addEventListener('endzoom',
          this.onEndZoom_.bind(this));

      this.mouseModeSelector_.addEventListener('entertiming',
          this.timingTool_.onEnterTiming.bind(this.timingTool_));
      this.mouseModeSelector_.addEventListener('begintiming',
          this.timingTool_.onBeginTiming.bind(this.timingTool_));
      this.mouseModeSelector_.addEventListener('updatetiming',
          this.timingTool_.onUpdateTiming.bind(this.timingTool_));
      this.mouseModeSelector_.addEventListener('endtiming',
          this.timingTool_.onEndTiming.bind(this.timingTool_));
      this.mouseModeSelector_.addEventListener('exittiming',
          this.timingTool_.onExitTiming.bind(this.timingTool_));

      var m = tvcm.ui.MOUSE_SELECTOR_MODE;
      this.mouseModeSelector_.supportedModeMask =
          m.SELECTION | m.PANSCAN | m.ZOOM | m.TIMING;
      this.mouseModeSelector_.settingsKey =
          'timelineTrackView.mouseModeSelector';
      this.mouseModeSelector_.setKeyCodeForMode(m.PANSCAN, '2'.charCodeAt(0));
      this.mouseModeSelector_.setKeyCodeForMode(m.SELECTION, '1'.charCodeAt(0));
      this.mouseModeSelector_.setKeyCodeForMode(m.ZOOM, '3'.charCodeAt(0));
      this.mouseModeSelector_.setKeyCodeForMode(m.TIMING, '4'.charCodeAt(0));

      this.mouseModeSelector_.setModifierForAlternateMode(
          m.SELECTION, tvcm.ui.MODIFIER.SHIFT);
      this.mouseModeSelector_.setModifierForAlternateMode(
          m.PANSCAN, tvcm.ui.MODIFIER.SPACE);
      this.mouseModeSelector_.setModifierForAlternateMode(
          m.ZOOM, tvcm.ui.MODIFIER.CMD_OR_CTRL);
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

    get model() {
      return this.model_;
    },

    set model(model) {
      if (!model)
        throw new Error('Model cannot be null');

      var modelInstanceChanged = this.model_ != model;
      this.model_ = model;
      this.modelTrack_.model = model;

      // Set up a reasonable viewport.
      if (modelInstanceChanged)
        this.viewport_.setWhenPossible(this.setInitialViewport_.bind(this));

      tvcm.setPropertyAndDispatchChange(this, 'model', model);
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
      tempDisplayTransform.set(this.viewport.currentDisplayTransform);
      tempDisplayTransform.xSetWorldBounds(min - boost,
                                           min + range + boost,
                                           w);
      this.viewport.setDisplayTransformImmediately(tempDisplayTransform);
    },

    /**
     * @param {Filter} filter The filter to use for finding matches.
     * @param {Selection} selection The selection to add matches to.
     * @return {Array} An array of objects that match the provided
     * TitleFilter.
     */
    addAllObjectsMatchingFilterToSelection: function(filter, selection) {
      this.modelTrack_.addAllObjectsMatchingFilterToSelection(
          filter, selection);
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
        return tvcm.ui.elementIsChildOf(document.activeElement,
                                        this.focusElement);
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
          this.zoomBy_(1.5, true);
          break;
        case 115:  // s
        case 111:  // o
          this.zoomBy_(1 / 1.5, true);
          break;
        case 103:  // g
          this.onGridToggle_(true);
          break;
        case 71:  // G
          this.onGridToggle_(false);
          break;
        case 87:  // W
        case 60:  // <
          this.zoomBy_(10, true);
          break;
        case 83:  // S
        case 79:  // O
          this.zoomBy_(1 / 10, true);
          break;
        case 97:  // a
          this.queueSmoothPan_(viewWidth * 0.3, 0);
          break;
        case 100:  // d
        case 101:  // e
          this.queueSmoothPan_(viewWidth * -0.3, 0);
          break;
        case 65:  // A
          this.queueSmoothPan_(viewWidth * 0.5, 0);
          break;
        case 68:  // D
          this.queueSmoothPan_(viewWidth * -0.5, 0);
          break;
        case 48:  // 0
          this.setInitialViewport_();
          break;
        case 102:  // f
          this.zoomToSelection();
          break;
        case 'm'.charCodeAt(0):
          this.setCurrentSelectionAsInterestRange_();
          break;
      }
    },

    // Not all keys send a keypress.
    onKeydown_: function(e) {
      if (!this.listenToKeys_)
        return;
      var sel;
      var vp = this.viewport;
      var viewWidth = this.modelTrackContainer_.canvas.clientWidth;

      switch (e.keyCode) {
        case 37:   // left arrow
          sel = this.selection.getShiftedSelection(
              this.viewport, -1);

          if (sel) {
            this.setSelectionAndClearHighlight(sel);
            this.panToSelection();
            e.preventDefault();
          } else {
            this.queueSmoothPan_(viewWidth * 0.3, 0);
          }
          break;
        case 39:   // right arrow
          sel = this.selection.getShiftedSelection(
              this.viewport, 1);
          if (sel) {
            this.setSelectionAndClearHighlight(sel);
            this.panToSelection();
            e.preventDefault();
          } else {
            this.queueSmoothPan_(-viewWidth * 0.3, 0);
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

    onDblClick_: function(e) {
      if (this.mouseModeSelector_.mode !==
          tvcm.ui.MOUSE_SELECTOR_MODE.SELECTION)
        return;

      if (!this.selection.length || !this.selection[0].title)
        return;

      var selection = new Selection();
      var filter = new tracing.ExactTitleFilter(this.selection[0].title);
      this.addAllObjectsMatchingFilterToSelection(filter, selection);

      this.setSelectionAndClearHighlight(selection);
    },

    onMouseWheel_: function(e) {
      if (!e.altKey)
        return;

      var delta = e.wheelDelta / 120;
      var zoomScale = Math.pow(1.5, delta);
      this.zoomBy_(zoomScale);
      e.preventDefault();
    },

    queueSmoothPan_: function(viewDeltaX, deltaY) {
      var deltaX = this.viewport_.currentDisplayTransform.xViewVectorToWorld(
          viewDeltaX);
      var animation = new tracing.TimelineDisplayTransformPanAnimation(
          deltaX, deltaY);
      this.viewport_.queueDisplayTransformAnimation(animation);
    },

    /**
     * Zoom in or out on the timeline by the given scale factor.
     * @param {Number} scale The scale factor to apply.  If <1, zooms out.
     * @param {boolean} Whether to change the zoom level smoothly.
     */
    zoomBy_: function(scale, smooth) {
      smooth = !!smooth;
      var vp = this.viewport;
      var viewWidth = this.modelTrackContainer_.canvas.clientWidth;
      var pixelRatio = window.devicePixelRatio || 1;

      var goalFocalPointXView = this.lastMouseViewPos_.x * pixelRatio;
      var goalFocalPointXWorld = vp.currentDisplayTransform.xViewToWorld(
          goalFocalPointXView);
      if (smooth) {
        var animation = new tracing.TimelineDisplayTransformZoomToAnimation(
            goalFocalPointXWorld, goalFocalPointXView,
            vp.currentDisplayTransform.panY,
            scale);
        vp.queueDisplayTransformAnimation(animation);
      } else {
        tempDisplayTransform.set(vp.currentDisplayTransform);
        tempDisplayTransform.scaleX = tempDisplayTransform.scaleX * scale;
        tempDisplayTransform.xPanWorldPosToViewPos(
            goalFocalPointXWorld, goalFocalPointXView, viewWidth);
        vp.setDisplayTransformImmediately(tempDisplayTransform);
      }
    },

    /**
     * Zoom into the current selection.
     */
    zoomToSelection: function() {
      if (!this.selectionOfInterest.length)
        return;

      var bounds = this.selectionOfInterest.bounds;
      if (!bounds.range)
        return;

      var worldCenter = bounds.center;
      var adjustedWorldRange = bounds.range * 1.25;
      var newScale = this.modelTrackContainer_.canvas.width /
          adjustedWorldRange;
      var zoomInRatio = newScale / this.viewport.currentDisplayTransform.scaleX;
      var animation = new tracing.TimelineDisplayTransformZoomToAnimation(
          worldCenter, 'center',
          this.viewport.currentDisplayTransform.panY,
          zoomInRatio);
      this.viewport.queueDisplayTransformAnimation(animation);
    },

    /**
     * Pan the view so the current selection becomes visible.
     */
    panToSelection: function() {
      if (!this.selectionOfInterest.length)
        return;

      var bounds = this.selectionOfInterest.bounds;
      var worldCenter = bounds.center;
      var viewWidth = this.modelTrackContainer_.canvas.width;

      var dt = this.viewport.currentDisplayTransform;
      if (false && !bounds.range) {
        if (dt.xWorldToView(bounds.center) < 0 ||
            dt.xWorldToView(bounds.center) > viewWidth) {
          tempDisplayTransform.set(dt);
          tempDisplayTransform.xPanWorldPosToViewPos(
              worldCenter, 'center', viewWidth);
          var deltaX = tempDisplayTransform.panX - dt.panX;
          var animation = new tracing.TimelineDisplayTransformPanAnimation(
              deltaX, 0);
          this.viewport.queueDisplayTransformAnimation(animation);
        }
        return;
      }

      tempDisplayTransform.set(dt);
      tempDisplayTransform.xPanWorldBoundsIntoView(
          bounds.min,
          bounds.max,
          viewWidth);
      var deltaX = tempDisplayTransform.panX - dt.panX;
      var animation = new tracing.TimelineDisplayTransformPanAnimation(
          deltaX, 0);
      this.viewport.queueDisplayTransformAnimation(animation);
    },

    setCurrentSelectionAsInterestRange_: function() {
      var selectionBounds = this.selection.bounds;
      if (selectionBounds.empty) {
        this.viewport.interestRange.reset();
        return;
      }

      if (this.viewport.interestRange.min == selectionBounds.min &&
          this.viewport.interestRange.max == selectionBounds.max)
        this.viewport.interestRange.reset();
      else
        this.viewport.interestRange.set(selectionBounds);
    },

    /**
     * Sets the selected events and changes the SelectionState of the events to
     *   SELECTED.
     * @param {Selection} selection A Selection of the new selected events.
     */
    set selection(selection) {
      this.setSelectionAndHighlight(selection, this.highlight_);
    },

    get selection() {
      return this.selection_;
    },

    /**
     * Sets the highlighted events and changes the SelectionState of the events
     *   to HIGHLIGHTED. All other events are set to DIMMED, except SELECTED
     *   ones.
     * @param {Selection} selection A Selection of the new selected events.
     */
    set highlight(highlight) {
      this.setSelectionAndHighlight(this.selection_, highlight);
    },

    get highlight() {
      return this.highlight_;
    },

    /**
     * Getter for events of interest, primarily SELECTED and secondarily
     *   HIGHLIGHTED events.
     */
    get selectionOfInterest() {
      if (!this.selection_.length && this.highlight_.length)
        return this.highlight_;
      return this.selection_;
    },

    /**
     * Sets the selected events, changes the SelectionState of the events to
     *   SELECTED and clears the highlighted events.
     * @param {Selection} selection A Selection of the new selected events.
     */
    setSelectionAndClearHighlight: function(selection) {
      this.setSelectionAndHighlight(selection, null);
    },

    /**
     * Sets the highlighted events, changes the SelectionState of the events to
     *   HIGHLIGHTED and clears the selected events. All other events are set to
     *   DIMMED.
     * @param {Selection} highlight A Selection of the new highlighted events.
     */
    setHighlightAndClearSelection: function(highlight) {
      this.setSelectionAndHighlight(null, highlight);
    },

    /**
     * Sets both selected and highlighted events. If an event is both it will be
     *   set to SELECTED. All other events are set to DIMMED.
     * @param {Selection} selection A Selection of the new selected events.
     * @param {Selection} highlight A Selection of the new highlighted events.
     */
    setSelectionAndHighlight: function(selection, highlight) {
      if (selection === this.selection_ && highlight === this.highlight_)
        return;

      if ((selection !== null && !(selection instanceof Selection)) ||
          (highlight !== null && !(highlight instanceof Selection))) {
        throw new Error('Expected Selection');
      }

      if (highlight && highlight.length) {
        // Set all events to DIMMED. This needs to be done before clearing the
        // old highlight, so that the old events are still available. This is
        // also necessary when the highlight doesn't change, because it might
        // have overlapping events with selection.
        this.resetEventsTo_(SelectionState.DIMMED);

        // Switch the highlight.
        if (highlight !== this.highlight_)
          this.highlight_ = highlight;

        // Set HIGHLIGHTED on the events of the new highlight.
        this.setSelectionState_(highlight, SelectionState.HIGHLIGHTED);
      } else {
        // If no highlight is active the SelectionState needs to be cleared.
        // Note that this also clears old SELECTED events, so it doesn't need
        // to be called again when setting the selection.
        this.resetEventsTo_(SelectionState.NONE);
        this.highlight_ = new Selection();
      }

      if (selection && selection.length) {
        // Switch the selection
        if (selection !== this.selection_)
          this.selection_ = selection;

        // Set SELECTED on the events of the new highlight.
        this.setSelectionState_(selection, SelectionState.SELECTED);
      } else
        this.selection_ = new Selection();

      tvcm.dispatchSimpleEvent(this, 'selectionChange');

      if (this.selectionOfInterest.length) {
        var track = this.viewport.trackForEvent(this.selectionOfInterest[0]);
        if (track)
          track.scrollIntoViewIfNeeded();
      }

      this.viewport.dispatchChangeEvent(); // Triggers a redraw.
    },

    /**
     * Sets a new SelectionState on all events in the selection.
     * @param {Selection} selection The affected selection.
     * @param {SelectionState} selectionState The new selection state.
     */
    setSelectionState_: function(selection, selectionState) {
      for (var i = 0; i < selection.length; i++)
        selection[i].selectionState = selectionState;
    },

    /**
     * Resets all events to the provided SelectionState. When the SelectionState
     *   changes from or to DIMMED all events in the model need to get updated.
     * @param {SelectionState} selectionState The SelectionState to reset to.
     */
    resetEventsTo_: function(selectionState) {
      var dimmed = this.highlight_.length;
      var resetAll = (dimmed && selectionState !== SelectionState.DIMMED) ||
                     (!dimmed && selectionState === SelectionState.DIMMED);
      if (resetAll) {
        this.model.iterateAllEvents(
            function(event) { event.selectionState = selectionState; });
      } else {
        this.setSelectionState_(this.selection_, selectionState);
        this.setSelectionState_(this.highlight_, selectionState);
      }
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
      var dt = this.viewport.currentDisplayTransform;
      var loWX = dt.xViewToWorld(
          (loX - canv.offsetLeft) * pixelRatio);
      var hiWX = dt.xViewToWorld(
          (hiX - canv.offsetLeft) * pixelRatio);

      var roundedDuration = Math.round((hiWX - loWX) * 100) / 100;
      this.dragBox_.textContent = roundedDuration + 'ms';

      var e = new tvcm.Event('selectionChanging');
      e.loWX = loWX;
      e.hiWX = hiWX;
      this.dispatchEvent(e);
    },

    onGridToggle_: function(left) {
      var tb = left ? this.selection.bounds.min : this.selection.bounds.max;

      // Toggle the grid off if the grid is on, the marker position is the same
      // and the same element is selected (same timebase).
      if (this.viewport.gridEnabled &&
          this.viewport.gridSide === left &&
          this.viewport.gridInitialTimebase === tb) {
        this.viewport.gridside = undefined;
        this.viewport.gridEnabled = false;
        this.viewport.gridInitialTimebase = undefined;
        return;
      }

      // Shift the timebase left until its just left of model_.bounds.min.
      var numIntervalsSinceStart = Math.ceil((tb - this.model_.bounds.min) /
          this.viewport.gridStep_);

      this.viewport.gridEnabled = true;
      this.viewport.gridSide = left;
      this.viewport.gridInitialTimebase = tb;
      this.viewport.gridTimebase = tb -
          (numIntervalsSinceStart + 1) * this.viewport.gridStep_;
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

    storeInitialInteractionPositionsAndFocus_: function(e) {

      this.storeInitialMouseDownPos_(e);
      this.storeLastMousePos_(e);

      this.focusElements_();
    },

    onBeginPanScan_: function(e) {
      var vp = this.viewport;
      this.viewportDisplayTransformAtMouseDown_ =
          vp.currentDisplayTransform.clone();
      this.isPanningAndScanning_ = true;

      this.storeInitialInteractionPositionsAndFocus_(e);
      e.preventDefault();
    },

    onUpdatePanScan_: function(e) {
      if (!this.isPanningAndScanning_)
        return;

      var viewWidth = this.modelTrackContainer_.canvas.clientWidth;

      var pixelRatio = window.devicePixelRatio || 1;
      var xDeltaView = pixelRatio * (this.lastMouseViewPos_.x -
          this.mouseViewPosAtMouseDown_.x);

      var yDelta = this.lastMouseViewPos_.y -
          this.mouseViewPosAtMouseDown_.y;

      tempDisplayTransform.set(this.viewportDisplayTransformAtMouseDown_);
      tempDisplayTransform.incrementPanXInViewUnits(xDeltaView);
      tempDisplayTransform.panY -= yDelta;
      this.viewport.setDisplayTransformImmediately(tempDisplayTransform);

      e.preventDefault();
      e.stopPropagation();

      this.storeLastMousePos_(e);
    },

    onEndPanScan_: function(e) {
      this.isPanningAndScanning_ = false;

      this.storeLastMousePos_(e);

      if (!e.isClick)
        e.preventDefault();
    },

    onBeginSelection_: function(e) {
      var canv = this.modelTrackContainer_.canvas;
      var rect = this.modelTrack_.getBoundingClientRect();
      var canvRect = canv.getBoundingClientRect();

      var inside = rect &&
          e.clientX >= rect.left &&
          e.clientX < rect.right &&
          e.clientY >= rect.top &&
          e.clientY < rect.bottom &&
          e.clientX >= canvRect.left &&
          e.clientX < canvRect.right;

      if (!inside)
        return;

      this.dragBeginEvent_ = e;

      this.storeInitialInteractionPositionsAndFocus_(e);
      e.preventDefault();
    },

    onUpdateSelection_: function(e) {
      if (!this.dragBeginEvent_)
        return;

      // Update the drag box
      this.dragBoxXStart_ = this.dragBeginEvent_.clientX;
      this.dragBoxXEnd_ = e.clientX;
      this.dragBoxYStart_ = this.dragBeginEvent_.clientY;
      this.dragBoxYEnd_ = e.clientY;
      this.setDragBoxPosition_(this.dragBoxXStart_, this.dragBoxYStart_,
          this.dragBoxXEnd_, this.dragBoxYEnd_);

    },

    onEndSelection_: function(e) {
      e.preventDefault();

      if (!this.dragBeginEvent_)
        return;

      // Stop the dragging.
      this.hideDragBox_();
      var eDown = this.dragBeginEvent_;
      this.dragBeginEvent_ = null;

      // Figure out extents of the drag.
      var loY = Math.min(eDown.clientY, e.clientY);
      var hiY = Math.max(eDown.clientY, e.clientY);
      var loX = Math.min(eDown.clientX, e.clientX);
      var hiX = Math.max(eDown.clientX, e.clientX);
      var tracksContainerBoundingRect =
          this.modelTrackContainer_.getBoundingClientRect();
      var topBoundary = tracksContainerBoundingRect.height;

      // Convert to worldspace.
      var canv = this.modelTrackContainer_.canvas;
      var loVX = loX - canv.offsetLeft;
      var hiVX = hiX - canv.offsetLeft;

      // Figure out what has been selected.
      var selection = new Selection();
      this.modelTrack_.addIntersectingItemsInRangeToSelection(
          loVX, hiVX, loY, hiY, selection);

      // Activate the new selection.
      this.setSelectionAndClearHighlight(selection);
    },

    onBeginZoom_: function(e) {
      this.isZooming_ = true;

      this.storeInitialInteractionPositionsAndFocus_(e);
      e.preventDefault();
    },

    onUpdateZoom_: function(e) {
      if (!this.isZooming_)
        return;
      var newPosition = this.extractRelativeMousePosition_(e);

      var zoomScaleValue = 1 + (this.lastMouseViewPos_.y -
          newPosition.y) * 0.01;

      this.zoomBy_(zoomScaleValue, false);
      this.storeLastMousePos_(e);
    },

    onEndZoom_: function(e) {
      this.isZooming_ = false;

      if (!e.isClick)
        e.preventDefault();
    }
  };

  return {
    TimelineTrackView: TimelineTrackView
  };
});
