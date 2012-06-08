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
cr.define('tracing', function() {

  /**
   * The TimelineViewport manages the transform used for navigating
   * within the timeline. It is a simple transform:
   *   x' = (x+pan) * scale
   *
   * The timeline code tries to avoid directly accessing this transform,
   * instead using this class to do conversion between world and view space,
   * as well as the math for centering the viewport in various interesting
   * ways.
   *
   * @constructor
   * @extends {cr.EventTarget}
   */
  function TimelineViewport(parentEl) {
    this.parentEl_ = parentEl;
    this.scaleX_ = 1;
    this.panX_ = 0;
    this.gridTimebase_ = 0;
    this.gridStep_ = 1000 / 60;
    this.gridEnabled_ = false;
    this.hasCalledSetupFunction_ = false;

    this.onResizeBoundToThis_ = this.onResize_.bind(this);

    // The following code uses an interval to detect when the parent element
    // is attached to the document. That is a trigger to run the setup function
    // and install a resize listener.
    this.checkForAttachInterval_ = setInterval(
        this.checkForAttach_.bind(this), 250);
  }

  TimelineViewport.prototype = {
    __proto__: cr.EventTarget.prototype,

    /**
     * Allows initialization of the viewport when the viewport's parent element
     * has been attached to the document and given a size.
     * @param {Function} fn Function to call when the viewport can be safely
     * initialized.
     */
    setWhenPossible: function(fn) {
      this.pendingSetFunction_ = fn;
    },

    /**
     * @return {boolean} Whether the current timeline is attached to the
     * document.
     */
    get isAttachedToDocument_() {
      var cur = this.parentEl_;
      while (cur.parentNode)
        cur = cur.parentNode;
      return cur == this.parentEl_.ownerDocument;
    },

    onResize_: function() {
      this.dispatchChangeEvent();
    },

    /**
     * Checks whether the parentNode is attached to the document.
     * When it is, it installs the iframe-based resize detection hook
     * and then runs the pendingSetFunction_, if present.
     */
    checkForAttach_: function() {
      if (!this.isAttachedToDocument_ || this.clientWidth == 0)
        return;

      if (!this.iframe_) {
        this.iframe_ = document.createElement('iframe');
        this.iframe_.style.cssText =
            'position:absolute;width:100%;height:0;border:0;visibility:hidden;';
        this.parentEl_.appendChild(this.iframe_);

        this.iframe_.contentWindow.addEventListener('resize',
                                                    this.onResizeBoundToThis_);
      }

      var curSize = this.clientWidth + 'x' + this.clientHeight;
      if (this.pendingSetFunction_) {
        this.lastSize_ = curSize;
        this.pendingSetFunction_();
        this.pendingSetFunction_ = undefined;
      }

      window.clearInterval(this.checkForAttachInterval_);
      this.checkForAttachInterval_ = undefined;
    },

    /**
     * Fires the change event on this viewport. Used to notify listeners
     * to redraw when the underlying model has been mutated.
     */
    dispatchChangeEvent: function() {
      cr.dispatchSimpleEvent(this, 'change');
    },

    detach: function() {
      if (this.checkForAttachInterval_) {
        window.clearInterval(this.checkForAttachInterval_);
        this.checkForAttachInterval_ = undefined;
      }
      this.iframe_.removeEventListener('resize', this.onResizeBoundToThis_);
      this.parentEl_.removeChild(this.iframe_);
    },

    get scaleX() {
      return this.scaleX_;
    },
    set scaleX(s) {
      var changed = this.scaleX_ != s;
      if (changed) {
        this.scaleX_ = s;
        this.dispatchChangeEvent();
      }
    },

    get panX() {
      return this.panX_;
    },
    set panX(p) {
      var changed = this.panX_ != p;
      if (changed) {
        this.panX_ = p;
        this.dispatchChangeEvent();
      }
    },

    setPanAndScale: function(p, s) {
      var changed = this.scaleX_ != s || this.panX_ != p;
      if (changed) {
        this.scaleX_ = s;
        this.panX_ = p;
        this.dispatchChangeEvent();
      }
    },

    xWorldToView: function(x) {
      return (x + this.panX_) * this.scaleX_;
    },

    xWorldVectorToView: function(x) {
      return x * this.scaleX_;
    },

    xViewToWorld: function(x) {
      return (x / this.scaleX_) - this.panX_;
    },

    xViewVectorToWorld: function(x) {
      return x / this.scaleX_;
    },

    xPanWorldPosToViewPos: function(worldX, viewX, viewWidth) {
      if (typeof viewX == 'string') {
        if (viewX == 'left') {
          viewX = 0;
        } else if (viewX == 'center') {
          viewX = viewWidth / 2;
        } else if (viewX == 'right') {
          viewX = viewWidth - 1;
        } else {
          throw Error('unrecognized string for viewPos. left|center|right');
        }
      }
      this.panX = (viewX / this.scaleX_) - worldX;
    },

    xPanWorldRangeIntoView: function(worldMin, worldMax, viewWidth) {
      if (this.xWorldToView(worldMin) < 0)
        this.xPanWorldPosToViewPos(worldMin, 'left', viewWidth);
      else if (this.xWorldToView(worldMax) > viewWidth)
        this.xPanWorldPosToViewPos(worldMax, 'right', viewWidth);
    },

    xSetWorldRange: function(worldMin, worldMax, viewWidth) {
      var worldRange = worldMax - worldMin;
      var scaleX = viewWidth / worldRange;
      var panX = -worldMin;
      this.setPanAndScale(panX, scaleX);
    },

    get gridEnabled() {
      return this.gridEnabled_;
    },

    set gridEnabled(enabled) {
      if (this.gridEnabled_ == enabled)
        return;
      this.gridEnabled_ = enabled && true;
      this.dispatchChangeEvent();
    },

    get gridTimebase() {
      return this.gridTimebase_;
    },

    set gridTimebase(timebase) {
      if (this.gridTimebase_ == timebase)
        return;
      this.gridTimebase_ = timebase;
      cr.dispatchSimpleEvent(this, 'change');
    },

    get gridStep() {
      return this.gridStep_;
    },

    applyTransformToCanavs: function(ctx) {
      ctx.transform(this.scaleX_, 0, 0, 1, this.panX_ * this.scaleX_, 0);
    }
  };

  function TimelineSelectionSliceHit(track, slice) {
    this.track = track;
    this.slice = slice;
  }
  TimelineSelectionSliceHit.prototype = {
    get selected() {
      return this.slice.selected;
    },
    set selected(v) {
      this.slice.selected = v;
    }
  };

  function TimelineSelectionCounterSampleHit(track, counter, sampleIndex) {
    this.track = track;
    this.counter = counter;
    this.sampleIndex = sampleIndex;
  }
  TimelineSelectionCounterSampleHit.prototype = {
    get selected() {
      return this.track.selectedSamples[this.sampleIndex] == true;
    },
    set selected(v) {
      if (v)
        this.track.selectedSamples[this.sampleIndex] = true;
      else
        this.track.selectedSamples[this.sampleIndex] = false;
      this.track.invalidate();
    }
  };


  /**
   * Represents a selection within a Timeline and its associated set of tracks.
   * @constructor
   */
  function TimelineSelection() {
    this.range_dirty_ = true;
    this.range_ = {};
    this.length_ = 0;
  }
  TimelineSelection.prototype = {
    __proto__: Object.prototype,

    get range() {
      if (this.range_dirty_) {
        var wmin = Infinity;
        var wmax = -wmin;
        for (var i = 0; i < this.length_; i++) {
          var hit = this[i];
          if (hit.slice) {
            wmin = Math.min(wmin, hit.slice.start);
            wmax = Math.max(wmax, hit.slice.end);
          }
        }
        this.range_ = {
          min: wmin,
          max: wmax
        };
        this.range_dirty_ = false;
      }
      return this.range_;
    },

    get duration() {
      return this.range.max - this.range.min;
    },

    get length() {
      return this.length_;
    },

    clear: function() {
      for (var i = 0; i < this.length_; ++i)
        delete this[i];
      this.length_ = 0;
      this.range_dirty_ = true;
    },

    push_: function(hit) {
      this[this.length_++] = hit;
      this.range_dirty_ = true;
      return hit;
    },

    addSlice: function(track, slice) {
      return this.push_(new TimelineSelectionSliceHit(track, slice));
    },

    addCounterSample: function(track, counter, sampleIndex) {
      return this.push_(
        new TimelineSelectionCounterSampleHit(
          track, counter, sampleIndex));
    },

    subSelection: function(index, count) {
      count = count || 1;

      var selection = new TimelineSelection();
      selection.range_dirty_ = true;
      if (index < 0 || index + count > this.length_)
        throw 'Index out of bounds';

      for (var i = index; i < index + count; i++)
        selection.push_(this[i]);

      return selection;
    },

    getCounterSampleHits: function() {
      var selection = new TimelineSelection();
      for (var i = 0; i < this.length_; i++)
        if (this[i] instanceof TimelineSelectionCounterSampleHit)
          selection.push_(this[i]);
      return selection;
    },

    getSliceHits: function() {
      var selection = new TimelineSelection();
      for (var i = 0; i < this.length_; i++)
        if (this[i] instanceof TimelineSelectionSliceHit)
          selection.push_(this[i]);
      return selection;
    },

    map: function(fn) {
      for (var i = 0; i < this.length_; i++)
        fn(this[i]);
    },

    /**
     * Helper for selection previous or next.
     * @param {boolean} forwardp If true, select one forward (next).
     *   Else, select previous.
     * @return {boolean} true if current selection changed.
     */
    getShiftedSelection: function(offset) {
      var newSelection = new TimelineSelection();
      for (var i = 0; i < this.length_; i++) {
        var hit = this[i];
        hit.track.addItemNearToProvidedHitToSelection(
            hit, offset, newSelection);
      }

      if (newSelection.length == 0)
        return undefined;
      return newSelection;
    },
  };

  /**
   * Renders a TimelineModel into a div element, making one
   * TimelineTrack for each subrow in each thread of the model, managing
   * overall track layout, and handling user interaction with the
   * viewport.
   *
   * @constructor
   * @extends {HTMLDivElement}
   */
  var Timeline = cr.ui.define('div');

  Timeline.prototype = {
    __proto__: HTMLDivElement.prototype,

    model_: null,

    decorate: function() {
      this.classList.add('timeline');

      this.viewport_ = new TimelineViewport(this);

      this.tracks_ = this.ownerDocument.createElement('div');
      this.appendChild(this.tracks_);

      this.dragBox_ = this.ownerDocument.createElement('div');
      this.dragBox_.className = 'timeline-drag-box';
      this.appendChild(this.dragBox_);
      this.hideDragBox_();

      this.bindEventListener_(document, 'keypress', this.onKeypress_, this);
      this.bindEventListener_(document, 'keydown', this.onKeydown_, this);
      this.bindEventListener_(document, 'mousedown', this.onMouseDown_, this);
      this.bindEventListener_(document, 'mousemove', this.onMouseMove_, this);
      this.bindEventListener_(document, 'mouseup', this.onMouseUp_, this);
      this.bindEventListener_(document, 'dblclick', this.onDblClick_, this);

      this.lastMouseViewPos_ = {x: 0, y: 0};

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
      for (var i = 0; i < this.tracks_.children.length; i++)
        this.tracks_.children[i].detach();

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
        throw Error('Model cannot be null');
      if (this.model) {
        throw Error('Cannot set model twice.');
      }
      this.model_ = model;

      // Figure out all the headings.
      var allHeadings = [];
      model.getAllThreads().forEach(function(t) {
        allHeadings.push(t.userFriendlyName);
      });
      model.getAllCounters().forEach(function(c) {
        allHeadings.push(c.name);
      });
      model.getAllCpus().forEach(function(c) {
        allHeadings.push('CPU ' + c.cpuNumber);
      });

      // Figure out the maximum heading size.
      var maxHeadingWidth = 0;
      var measuringStick = new tracing.MeasuringStick();
      var headingEl = document.createElement('div');
      headingEl.style.position = 'fixed';
      headingEl.className = 'timeline-canvas-based-track-title';
      allHeadings.forEach(function(text) {
        headingEl.textContent = text + ':__';
        var w = measuringStick.measure(headingEl).width;
        // Limit heading width to 300px.
        if (w > 300)
          w = 300;
        if (w > maxHeadingWidth)
          maxHeadingWidth = w;
      });
      maxHeadingWidth = maxHeadingWidth + 'px';

      // Reset old tracks.
      for (var i = 0; i < this.tracks_.children.length; i++)
        this.tracks_.children[i].detach();
      this.tracks_.textContent = '';

      // Add the viewport track
      var viewportTrack = new tracing.TimelineViewportTrack();
      viewportTrack.headingWidth = maxHeadingWidth;
      viewportTrack.viewport = this.viewport_;
      this.tracks_.appendChild(viewportTrack);

      // Get a sorted list of CPUs
      var cpus = model.getAllCpus();
      cpus.sort(tracing.TimelineCpu.compare);

      // Create tracks for each CPU.
      cpus.forEach(function(cpu) {
        var track = new tracing.TimelineCpuTrack();
        track.heading = 'CPU ' + cpu.cpuNumber + ':';
        track.headingWidth = maxHeadingWidth;
        track.viewport = this.viewport_;
        track.cpu = cpu;
        this.tracks_.appendChild(track);

        for (var counterName in cpu.counters) {
          var counter = cpu.counters[counterName];
          track = new tracing.TimelineCounterTrack();
          track.heading = 'CPU ' + cpu.cpuNumber + ' ' + counter.name + ':';
          track.headingWidth = maxHeadingWidth;
          track.viewport = this.viewport_;
          track.counter = counter;
          this.tracks_.appendChild(track);
        }
      }.bind(this));

      // Get a sorted list of processes.
      var processes = model.getAllProcesses();
      processes.sort(tracing.TimelineProcess.compare);

      // Create tracks for each process.
      processes.forEach(function(process) {
        // Add counter tracks for this process.
        var counters = [];
        for (var tid in process.counters)
          counters.push(process.counters[tid]);
        counters.sort(tracing.TimelineCounter.compare);

        // Create the counters for this process.
        counters.forEach(function(counter) {
          var track = new tracing.TimelineCounterTrack();
          track.heading = counter.name + ':';
          track.headingWidth = maxHeadingWidth;
          track.viewport = this.viewport_;
          track.counter = counter;
          this.tracks_.appendChild(track);
        }.bind(this));

        // Get a sorted list of threads.
        var threads = [];
        for (var tid in process.threads)
          threads.push(process.threads[tid]);
        threads.sort(tracing.TimelineThread.compare);

        // Create the threads.
        threads.forEach(function(thread) {
          var track = new tracing.TimelineThreadTrack();
          track.heading = thread.userFriendlyName + ':';
          track.tooltip = thread.userFriendlyDetails;
          track.headingWidth = maxHeadingWidth;
          track.viewport = this.viewport_;
          track.thread = thread;
          this.tracks_.appendChild(track);
        }.bind(this));
      }.bind(this));

      // Set up a reasonable viewport.
      this.viewport_.setWhenPossible(function() {
        var w = this.firstCanvas.width;
        this.viewport_.xSetWorldRange(this.model_.minTimestamp,
                                      this.model_.maxTimestamp,
                                      w);
      }.bind(this));
    },

    /**
     * @param {TimelineFilter} filter The filter to use for finding matches.
     * @param {TimelineSelection} selection The selection to add matches to.
     * @return {Array} An array of objects that match the provided
     * TimelineFilter.
     */
    addAllObjectsMatchingFilterToSelection: function(filter, selection) {
      for (var i = 0; i < this.tracks_.children.length; ++i)
        this.tracks_.children[i].addAllObjectsMatchingFilterToSelection(
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
      var viewWidth = this.firstCanvas.clientWidth;
      var curMouseV, curCenterW;
      switch (e.keyCode) {
        case 101: // e
          var vX = this.lastMouseViewPos_.x;
          var wX = vp.xViewToWorld(this.lastMouseViewPos_.x);
          var distFromCenter = vX - (viewWidth / 2);
          var percFromCenter = distFromCenter / viewWidth;
          var percFromCenterSq = percFromCenter * percFromCenter;
          vp.xPanWorldPosToViewPos(wX, 'center', viewWidth);
          break;
        case 119:  // w
          this.zoomBy_(1.5);
          break;
        case 115:  // s
          this.zoomBy_(1 / 1.5);
          break;
        case 103:  // g
          this.onGridToggle_(true);
          break;
        case 71:  // G
          this.onGridToggle_(false);
          break;
        case 87:  // W
          this.zoomBy_(10);
          break;
        case 83:  // S
          this.zoomBy_(1 / 10);
          break;
        case 97:  // a
          vp.panX += vp.xViewVectorToWorld(viewWidth * 0.1);
          break;
        case 100:  // d
          vp.panX -= vp.xViewVectorToWorld(viewWidth * 0.1);
          break;
        case 65:  // A
          vp.panX += vp.xViewVectorToWorld(viewWidth * 0.5);
          break;
        case 68:  // D
          vp.panX -= vp.xViewVectorToWorld(viewWidth * 0.5);
          break;
      }
    },

    // Not all keys send a keypress.
    onKeydown_: function(e) {
      if (!this.listenToKeys_)
        return;
      var sel;
      switch (e.keyCode) {
        case 37:   // left arrow
          sel = this.selection.getShiftedSelection(-1);
          if (sel) {
            this.setSelectionAndMakeVisible(sel);
            e.preventDefault();
          }
          break;
        case 39:   // right arrow
          sel = this.selection.getShiftedSelection(1);
          if (sel) {
            this.setSelectionAndMakeVisible(sel);
            e.preventDefault();
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

    get keyHelp() {
      var help = 'Keyboard shortcuts:\n' +
          ' w/s     : Zoom in/out    (with shift: go faster)\n' +
          ' a/d     : Pan left/right\n' +
          ' e       : Center on mouse\n' +
          ' g/G     : Shows grid at the start/end of the selected task\n';

      if (this.focusElement.tabIndex) {
        help += ' <-      : Select previous event on current timeline\n' +
            ' ->      : Select next event on current timeline\n';
      } else {
        help += ' <-,^TAB : Select previous event on current timeline\n' +
            ' ->, TAB : Select next event on current timeline\n';
      }
      help +=
          '\n' +
          'Dbl-click to zoom in; Shift dbl-click to zoom out\n';
      return help;
    },

    get selection() {
      return this.selection_;
    },

    set selection(selection) {
      if (!(selection instanceof TimelineSelection))
          throw 'Expected TimelineSelection';

      // Clear old selection.
      var i;
      for (i = 0; i < this.selection_.length; i++)
        this.selection_[i].selected = false;

      this.selection_ = selection;

      cr.dispatchSimpleEvent(this, 'selectionChange');
      for (i = 0; i < this.selection_.length; i++)
        this.selection_[i].selected = true;
      this.viewport_.dispatchChangeEvent(); // Triggers a redraw.
    },

    setSelectionAndMakeVisible: function(selection, zoomAllowed) {
      if (!(selection instanceof TimelineSelection))
          throw 'Expected TimelineSelection';
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
      return this.tracks_.firstChild ?
          this.tracks_.firstChild.firstCanvas : undefined;
    },

    hideDragBox_: function() {
      this.dragBox_.style.left = '-1000px';
      this.dragBox_.style.top = '-1000px';
      this.dragBox_.style.width = 0;
      this.dragBox_.style.height = 0;
    },

    setDragBoxPosition_: function(eDown, eCur) {
      var loX = Math.min(eDown.clientX, eCur.clientX);
      var hiX = Math.max(eDown.clientX, eCur.clientX);
      var loY = Math.min(eDown.clientY, eCur.clientY);
      var hiY = Math.max(eDown.clientY, eCur.clientY);

      this.dragBox_.style.left = loX + 'px';
      this.dragBox_.style.top = loY + 'px';
      this.dragBox_.style.width = hiX - loX + 'px';
      this.dragBox_.style.height = hiY - loY + 'px';

      var canv = this.firstCanvas;
      var loWX = this.viewport_.xViewToWorld(loX - canv.offsetLeft);
      var hiWX = this.viewport_.xViewToWorld(hiX - canv.offsetLeft);

      var roundedDuration = Math.round((hiWX - loWX) * 100) / 100;
      this.dragBox_.textContent = roundedDuration + 'ms';

      var e = new cr.Event('selectionChanging');
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

    onMouseDown_: function(e) {
      var canv = this.firstCanvas;
      var rect = this.tracks_.getClientRects()[0];
      var inside = rect &&
          e.clientX >= rect.left &&
          e.clientX < rect.right &&
          e.clientY >= rect.top &&
          e.clientY < rect.bottom &&
          e.x >= canv.offsetLeft;
      if (!inside)
        return;

      var pos = {
        x: e.clientX - canv.offsetLeft,
        y: e.clientY - canv.offsetTop
      };

      var wX = this.viewport_.xViewToWorld(pos.x);

      this.dragBeginEvent_ = e;
      e.preventDefault();
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
        this.setDragBoxPosition_(this.dragBeginEvent_, e);
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
        var loX = Math.min(eDown.clientX, e.clientX);
        var hiX = Math.max(eDown.clientX, e.clientX);
        var loY = Math.min(eDown.clientY, e.clientY);
        var hiY = Math.max(eDown.clientY, e.clientY);

        // Convert to worldspace.
        var canv = this.firstCanvas;
        var loWX = this.viewport_.xViewToWorld(loX - canv.offsetLeft);
        var hiWX = this.viewport_.xViewToWorld(hiX - canv.offsetLeft);

        // Figure out what has been hit.
        var selection = new TimelineSelection();
        for (i = 0; i < this.tracks_.children.length; i++) {
          var track = this.tracks_.children[i];

          // Only check tracks that insersect the rect.
          var trackClientRect = track.getBoundingClientRect();
          var a = Math.max(loY, trackClientRect.top);
          var b = Math.min(hiY, trackClientRect.bottom);
          if (a <= b) {
            track.addIntersectingItemsInRangeToSelection(
              loWX, hiWX, loY, hiY, selection);
          }
        }
        // Activate the new selection.
        this.selection = selection;
      }
    },

    onDblClick_: function(e) {
      var canv = this.firstCanvas;
      if (e.x < canv.offsetLeft)
        return;

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
  cr.defineProperty(Timeline, 'model', cr.PropertyKind.JS);

  return {
    Timeline: Timeline,
    TimelineSelectionSliceHit: TimelineSelectionSliceHit,
    TimelineSelectionCounterSampleHit: TimelineSelectionCounterSampleHit,
    TimelineSelection: TimelineSelection,
    TimelineViewport: TimelineViewport
  };
});
