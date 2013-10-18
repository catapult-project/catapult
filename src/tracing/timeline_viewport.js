// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview Code for the viewport.
 */
base.require('base.events');
base.require('tracing.draw_helpers');
base.require('tracing.timeline_display_transform');
base.require('ui.animation');
base.require('ui.animation_controller');

base.exportTo('tracing', function() {

  var TimelineDisplayTransform = tracing.TimelineDisplayTransform;

  /**
   * The TimelineViewport manages the transform used for navigating
   * within the timeline. It is a simple transform:
   *   x' = (x+pan) * scale
   *
   * The timeline code tries to avoid directly accessing this transform,
   * instead using this class to do conversion between world and viewspace,
   * as well as the math for centering the viewport in various interesting
   * ways.
   *
   * @constructor
   * @extends {base.EventTarget}
   */
  function TimelineViewport(parentEl) {
    this.parentEl_ = parentEl;
    this.modelTrackContainer_ = undefined;
    this.currentDisplayTransform_ = new TimelineDisplayTransform();
    this.initAnimationController_();

    // Flow events
    this.showFlowEvents_ = false;

    // Grid system.
    this.gridTimebase_ = 0;
    this.gridStep_ = 1000 / 60;
    this.gridEnabled_ = false;

    // Init logic.
    this.hasCalledSetupFunction_ = false;

    this.onResize_ = this.onResize_.bind(this);
    this.onModelTrackControllerScroll_ =
        this.onModelTrackControllerScroll_.bind(this);

    // The following code uses an interval to detect when the parent element
    // is attached to the document. That is a trigger to run the setup function
    // and install a resize listener.
    this.checkForAttachInterval_ = setInterval(
        this.checkForAttach_.bind(this), 250);

    this.markers = [];
    this.majorMarkPositions = [];

    this.eventToTrackMap_ = {};
  }

  TimelineViewport.prototype = {
    __proto__: base.EventTarget.prototype,

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
      // Allow not providing a parent element, used by tests.
      if (cur === undefined)
        return;
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

        this.iframe_.contentWindow.addEventListener('resize', this.onResize_);
      }

      var curSize = this.parentEl_.clientWidth + 'x' +
          this.parentEl_.clientHeight;
      if (this.pendingSetFunction_) {
        this.lastSize_ = curSize;
        try {
          this.pendingSetFunction_();
        } catch (ex) {
          console.log('While running setWhenPossible:',
              ex.message ? ex.message + '\n' + ex.stack : ex.stack);
        }
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
      base.dispatchSimpleEvent(this, 'change');
    },

    dispatchMarkersChangeEvent_: function() {
      base.dispatchSimpleEvent(this, 'markersChange');
    },

    detach: function() {
      if (this.checkForAttachInterval_) {
        window.clearInterval(this.checkForAttachInterval_);
        this.checkForAttachInterval_ = undefined;
      }
      if (this.iframe_) {
        this.iframe_.removeEventListener('resize', this.onResize_);
        this.parentEl_.removeChild(this.iframe_);
      }
    },

    initAnimationController_: function() {
      this.dtAnimationController_ = new ui.AnimationController();
      this.dtAnimationController_.addEventListener(
          'didtick', function(e) {
            this.onCurentDisplayTransformChange_(e.oldTargetState);
          }.bind(this));

      var that = this;
      this.dtAnimationController_.target = {
        get panX() {
          return that.currentDisplayTransform_.panX;
        },

        set panX(panX) {
          that.currentDisplayTransform_.panX = panX;
        },

        get panY() {
          return that.currentDisplayTransform_.panY;
        },

        set panY(panY) {
          that.currentDisplayTransform_.panY = panY;
        },

        get scaleX() {
          return that.currentDisplayTransform_.scaleX;
        },

        set scaleX(scaleX) {
          that.currentDisplayTransform_.scaleX = scaleX;
        },

        cloneAnimationState: function() {
          return that.currentDisplayTransform_.clone();
        },

        xPanWorldPosToViewPos: function(xWorld, xView) {
          that.currentDisplayTransform_.xPanWorldPosToViewPos(
              xWorld, xView, that.modelTrackContainer_.canvas.clientWidth);
        }
      };
    },

    get currentDisplayTransform() {
      return this.currentDisplayTransform_;
    },

    setDisplayTransformImmediately: function(displayTransform) {
      this.dtAnimationController_.cancelActiveAnimation();

      var oldDisplayTransform =
          this.dtAnimationController_.target.cloneAnimationState();
      this.currentDisplayTransform_.set(displayTransform);
      this.onCurentDisplayTransformChange_(oldDisplayTransform);
    },

    queueDisplayTransformAnimation: function(animation) {
      if (!(animation instanceof ui.Animation))
        throw new Error('animation must be instanceof ui.Animation');
      this.dtAnimationController_.queueAnimation(animation);
    },

    onCurentDisplayTransformChange_: function(oldDisplayTransform) {
      // Ensure panY stays clamped in the track container's scroll range.
      if (this.modelTrackContainer_) {
        this.currentDisplayTransform.panY = base.clamp(
            this.currentDisplayTransform.panY,
            0,
            this.modelTrackContainer_.scrollHeight -
                this.modelTrackContainer_.clientHeight);
      }

      var changed = !this.currentDisplayTransform.equals(oldDisplayTransform);
      var yChanged = this.currentDisplayTransform.panY !==
          oldDisplayTransform.panY;
      if (yChanged)
        this.modelTrackContainer_.scrollTop = this.currentDisplayTransform.panY;
      if (changed)
        this.dispatchChangeEvent();
    },

    onModelTrackControllerScroll_: function(e) {
      if (this.dtAnimationController_.activeAnimation &&
          this.dtAnimationController_.activeAnimation.affectsPanY)
        this.dtAnimationController_.cancelActiveAnimation();
      var panY = this.modelTrackContainer_.scrollTop;
      this.currentDisplayTransform_.panY = panY;
    },

    get modelTrackContainer() {
      return this.modelTrackContainer_;
    },

    set modelTrackContainer(m) {
      if (this.modelTrackContainer_)
        this.modelTrackContainer_.removeEventListener('scroll',
            this.onModelTrackControllerScroll_);

      this.modelTrackContainer_ = m;
      this.modelTrackContainer_.addEventListener('scroll',
          this.onModelTrackControllerScroll_);
    },

    get showFlowEvents() {
      return this.showFlowEvents_;
    },

    set showFlowEvents(showFlowEvents) {
      this.showFlowEvents_ = showFlowEvents;
      this.dispatchChangeEvent();
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
      this.dispatchChangeEvent();
    },

    get gridStep() {
      return this.gridStep_;
    },

    createMarker: function(positionWorld) {
      return new ViewportMarker(this, positionWorld);
    },

    addMarker: function(marker) {
      if (this.markers.indexOf(marker) >= 0)
        return false;
      this.markers.push(marker);
      this.dispatchChangeEvent();
      this.dispatchMarkersChangeEvent_();
      return marker;
    },

    removeAllMarkers: function() {
      this.markers = [];
      this.dispatchChangeEvent();
      this.dispatchMarkersChangeEvent_();
    },

    getMarkerBounds: function() {
      var bounds = new base.Range();
      for (var i = 0; i < this.markers.length; ++i)
        bounds.addValue(this.markers[i].positionWorld);
      return bounds;
    },

    removeMarker: function(marker) {
      for (var i = 0; i < this.markers.length; ++i) {
        if (this.markers[i] === marker) {
          this.markers.splice(i, 1);
          this.dispatchChangeEvent();
          this.dispatchMarkersChangeEvent_();
          return true;
        }
      }
    },

    findMarkerNear: function(positionWorld, nearnessInViewPixels) {
      // Converts pixels into distance in world.
      var dt = this.currentDisplayTransform;
      var nearnessThresholdWorld = dt.xViewVectorToWorld(
          nearnessInViewPixels);
      for (var i = 0; i < this.markers.length; ++i) {
        if (Math.abs(this.markers[i].positionWorld - positionWorld) <=
            nearnessThresholdWorld) {
          var marker = this.markers[i];
          return marker;
        }
      }
      return undefined;
    },

    drawMarkLines: function(ctx) {
      // Apply subpixel translate to get crisp lines.
      // http://www.mobtowers.com/html5-canvas-crisp-lines-every-time/
      ctx.save();
      ctx.translate((Math.round(ctx.lineWidth) % 2) / 2, 0);

      ctx.beginPath();
      for (var idx in this.majorMarkPositions) {
        var x = Math.floor(this.majorMarkPositions[idx]);
        tracing.drawLine(ctx, x, 0, x, ctx.canvas.height);
      }
      ctx.strokeStyle = '#ddd';
      ctx.stroke();

      ctx.restore();
    },

    drawGridLines: function(ctx, viewLWorld, viewRWorld) {
      if (!this.gridEnabled)
        return;

      var dt = this.currentDisplayTransform;
      var x = this.gridTimebase;

      // Apply subpixel translate to get crisp lines.
      // http://www.mobtowers.com/html5-canvas-crisp-lines-every-time/
      ctx.save();
      ctx.translate((Math.round(ctx.lineWidth) % 2) / 2, 0);

      ctx.beginPath();
      while (x < viewRWorld) {
        if (x >= viewLWorld) {
          // Do conversion to viewspace here rather than on
          // x to avoid precision issues.
          var vx = Math.floor(dt.xWorldToView(x));
          tracing.drawLine(ctx, vx, 0, vx, ctx.canvas.height);
        }

        x += this.gridStep;
      }
      ctx.strokeStyle = 'rgba(255, 0, 0, 0.25)';
      ctx.stroke();

      ctx.restore();
    },

    drawMarkerLines: function(ctx, viewLWorld, viewRWorld) {
      // Dim the area left and right of the markers if there are 2 markers.
      var dt = this.currentDisplayTransform;
      if (this.markers.length === 2) {
        var posWorld0 = this.markers[0].positionWorld;
        var posWorld1 = this.markers[1].positionWorld;

        var markerLWorld = Math.min(posWorld0, posWorld1);
        var markerRWorld = Math.max(posWorld0, posWorld1);

        var markerLView = Math.round(dt.xWorldToView(markerLWorld));
        var markerRView = Math.round(dt.xWorldToView(markerRWorld));

        ctx.fillStyle = 'rgba(0, 0, 0, 0.2)';
        if (markerLWorld > viewLWorld) {
          ctx.fillRect(dt.xWorldToView(viewLWorld), 0,
              markerLView, ctx.canvas.height);
        }

        if (markerRWorld < viewRWorld) {
          ctx.fillRect(markerRView, 0,
              dt.xWorldToView(viewRWorld), ctx.canvas.height);
        }
      }

      var pixelRatio = window.devicePixelRatio || 1;
      ctx.lineWidth = Math.round(pixelRatio);

      for (var i = 0; i < this.markers.length; ++i) {
        var marker = this.markers[i];

        var ts = marker.positionWorld;
        if (ts < viewLWorld || ts >= viewRWorld)
          continue;

        marker.drawLine(ctx, ctx.canvas.height);
      }

      ctx.lineWidth = 1;
    },

    drawMarkerIndicators: function(ctx, viewLWorld, viewRWorld) {
      for (var i = 0; i < this.markers.length; ++i) {
        var marker = this.markers[i];
        var ts = marker.positionWorld;
        if (ts < viewLWorld || ts >= viewRWorld)
          continue;

        marker.drawIndicator(ctx);
      }
    },

    rebuildEventToTrackMap: function() {
      this.eventToTrackMap_ = undefined;

      var eventToTrackMap = {};
      eventToTrackMap.addEvent = function(event, track) {
        if (!track)
          throw new Error('Must provide a track.');
        this[event.guid] = track;
      };
      this.modelTrackContainer_.addEventsToTrackMap(eventToTrackMap);
      this.eventToTrackMap_ = eventToTrackMap;
    },

    trackForEvent: function(event) {
      return this.eventToTrackMap_[event.guid];
    }
  };

  /**
   * Represents a marked position in the world, at a viewport level.
   * @constructor
   */
  function ViewportMarker(vp, positionWorld) {
    this.viewport_ = vp;
    this.positionWorld_ = positionWorld;
    this.selected_ = false;

    this.snapIndicator_ = {
      show: false,
      y: 0,
      height: 0
    };
  }

  ViewportMarker.prototype = {
    get positionWorld() {
      return this.positionWorld_;
    },

    set positionWorld(positionWorld) {
      this.positionWorld_ = positionWorld;
      this.viewport_.dispatchChangeEvent();
    },

    get positionView() {
      return this.viewport_.currentDisplayTransform.xWorldToView(
          this.positionWorld);
    },

    set selected(selected) {
      if (this.selected === selected)
        return;
      this.selected_ = selected;
      this.viewport_.dispatchChangeEvent();
    },

    get selected() {
      return this.selected_;
    },

    get color() {
      return this.selected ? 'rgb(255, 0, 0)' : 'rgb(0, 0, 0)';
    },

    drawLine: function(ctx, height) {
      var dt = this.viewport_.currentDisplayTransform;
      var viewX = Math.round(dt.xWorldToView(this.positionWorld_));

      // Apply subpixel translate to get crisp lines.
      // http://www.mobtowers.com/html5-canvas-crisp-lines-every-time/
      ctx.save();
      ctx.translate((Math.round(ctx.lineWidth) % 2) / 2, 0);

      ctx.beginPath();
      tracing.drawLine(ctx, viewX, 0, viewX, height);
      ctx.strokeStyle = this.color;
      ctx.stroke();

      ctx.restore();
    },

    drawIndicator: function(ctx) {
      if (!this.snapIndicator_.show)
        return;

      var dt = this.viewport_.currentDisplayTransform;
      var viewX = Math.round(dt.xWorldToView(this.positionWorld_));

      // Apply subpixel translate to get crisp lines.
      // http://www.mobtowers.com/html5-canvas-crisp-lines-every-time/
      ctx.save();
      ctx.translate((Math.round(ctx.lineWidth) % 2) / 2, 0);

      var pixelRatio = window.devicePixelRatio || 1;
      var viewY = this.snapIndicator_.y * devicePixelRatio;
      var viewHeight = this.snapIndicator_.height * devicePixelRatio;
      var arrowSize = 4 * pixelRatio;

      ctx.fillStyle = this.color;
      tracing.drawTriangle(ctx,
          viewX - arrowSize * 0.75, viewY,
          viewX + arrowSize * 0.75, viewY,
          viewX, viewY + arrowSize);
      ctx.fill();
      tracing.drawTriangle(ctx,
          viewX - arrowSize * 0.75, viewY + viewHeight,
          viewX + arrowSize * 0.75, viewY + viewHeight,
          viewX, viewY + viewHeight - arrowSize);
      ctx.fill();

      ctx.restore();
    },

    setSnapIndicator: function(show, y, height) {
      this.snapIndicator_.show = show;
      this.snapIndicator_.y = y;
      this.snapIndicator_.height = height;
    }
  };

  return {
    TimelineViewport: TimelineViewport,
    ViewportMarker: ViewportMarker
  };
});
