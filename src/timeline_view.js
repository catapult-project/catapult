// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview TimelineView visualizes TRACE_EVENT events using the
 * tracing.Timeline component and adds in selection summary and control buttons.
 */
base.defineModule('timeline_view')
    .stylesheet('timeline_view')
    .dependsOn('timeline',
               'timeline_analysis',
               'overlay',
               'trace_event_importer',
               'linux_perf_cpufreq_parser',
               'linux_perf_drm_parser',
               'linux_perf_exynos_parser',
               'linux_perf_i915_parser',
               'linux_perf_power_parser',
               'linux_perf_sched_parser',
               'linux_perf_workqueue_parser')
    .exportsTo('tracing', function() {

  /**
   * TimelineFindControl
   * @constructor
   * @extends {tracing.Overlay}
   */
  var TimelineFindControl = base.ui.define('div');

  TimelineFindControl.prototype = {
    __proto__: tracing.Overlay.prototype,

    decorate: function() {
      tracing.Overlay.prototype.decorate.call(this);

      this.className = 'timeline-find-control';

      this.hitCountEl_ = document.createElement('div');
      this.hitCountEl_.className = 'hit-count-label';
      this.hitCountEl_.textContent = '1 of 7';

      var findPreviousBn = document.createElement('div');
      findPreviousBn.className = 'timeline-button find-previous';
      findPreviousBn.textContent = '\u2190';
      findPreviousBn.addEventListener('click', function() {
        this.controller.findPrevious();
        this.updateHitCountEl_();
      }.bind(this));

      var findNextBn = document.createElement('div');
      findNextBn.className = 'timeline-button find-next';
      findNextBn.textContent = '\u2192';
      findNextBn.addEventListener('click', function() {
        this.controller.findNext();
        this.updateHitCountEl_();
      }.bind(this));

      // Filter input element.
      this.filterEl_ = document.createElement('input');
      this.filterEl_.type = 'input';

      this.filterEl_.addEventListener('input', function(e) {
        this.controller.filterText = this.filterEl_.value;
        this.updateHitCountEl_();
      }.bind(this));

      this.filterEl_.addEventListener('keydown', function(e) {
        if (e.keyCode == 13) {
          findNextBn.click();
        } else if (e.keyCode == 27) {
          this.filterEl_.blur();
          this.updateHitCountEl_();
        }
      }.bind(this));

      this.filterEl_.addEventListener('blur', function(e) {
        this.updateHitCountEl_();
      }.bind(this));

      this.filterEl_.addEventListener('focus', function(e) {
        this.updateHitCountEl_();
      }.bind(this));

      // Attach everything.
      this.appendChild(this.filterEl_);

      this.appendChild(findPreviousBn);
      this.appendChild(findNextBn);
      this.appendChild(this.hitCountEl_);

      this.updateHitCountEl_();
    },

    get controller() {
      return this.controller_;
    },

    set controller(c) {
      this.controller_ = c;
      this.updateHitCountEl_();
    },

    focus: function() {
      this.filterEl_.selectionStart = 0;
      this.filterEl_.selectionEnd = this.filterEl_.value.length;
      this.filterEl_.focus();
    },

    updateHitCountEl_: function() {
      if (!this.controller || document.activeElement != this.filterEl_) {
        this.hitCountEl_.textContent = '';
        return;
      }
      var i = this.controller.currentHitIndex;
      var n = this.controller.filterHits.length;
      if (n == 0)
        this.hitCountEl_.textContent = '0 of 0';
      else
        this.hitCountEl_.textContent = (i + 1) + ' of ' + n;
    }
  };

  function TimelineFindController() {
    this.timeline_ = undefined;
    this.model_ = undefined;
    this.filterText_ = '';
    this.filterHits_ = new tracing.TimelineSelection();
    this.filterHitsDirty_ = true;
    this.currentHitIndex_ = 0;
  };

  TimelineFindController.prototype = {
    __proto__: Object.prototype,

    get timeline() {
      return this.timeline_;
    },

    set timeline(t) {
      this.timeline_ = t;
      this.filterHitsDirty_ = true;
    },

    get filterText() {
      return this.filterText_;
    },

    set filterText(f) {
      if (f == this.filterText_)
        return;
      this.filterText_ = f;
      this.filterHitsDirty_ = true;
      this.findNext();
    },

    get filterHits() {
      if (this.filterHitsDirty_) {
        this.filterHitsDirty_ = false;
        if (this.timeline_) {
          var filter = new tracing.TimelineFilter(this.filterText);
          this.filterHits_.clear();
          this.timeline.addAllObjectsMatchingFilterToSelection(
            filter, this.filterHits_);
          this.currentHitIndex_ = this.filterHits_.length - 1;
        } else {
          this.filterHits_.clear();
          this.currentHitIndex_ = 0;
        }
      }
      return this.filterHits_;
    },

    get currentHitIndex() {
      return this.currentHitIndex_;
    },

    find_: function(dir) {
      if (!this.timeline)
        return;

      var N = this.filterHits.length;
      this.currentHitIndex_ = this.currentHitIndex_ + dir;

      if (this.currentHitIndex_ < 0) this.currentHitIndex_ = N - 1;
      if (this.currentHitIndex_ >= N) this.currentHitIndex_ = 0;

      if (this.currentHitIndex_ < 0 || this.currentHitIndex_ >= N) {
        this.timeline.selection = new tracing.TimelineSelection();
        return;
      }

      // We allow the zoom level to change on the first hit level. But, when
      // then cycling through subsequent changes, restrict it to panning.
      var zoomAllowed = this.currentHitIndex_ == 0;
      var subSelection = this.filterHits.subSelection(this.currentHitIndex_);
      this.timeline.setSelectionAndMakeVisible(subSelection, zoomAllowed);
    },

    findNext: function() {
      this.find_(1);
    },

    findPrevious: function() {
      this.find_(-1);
    }
  };

  /**
   * TimelineView
   * @constructor
   * @extends {HTMLDivElement}
   */
  var TimelineView = base.ui.define('div');

  TimelineView.prototype = {
    __proto__: HTMLDivElement.prototype,

    decorate: function() {
      this.classList.add('timeline-view');

      // Create individual elements.
      this.titleEl_ = document.createElement('div');
      this.titleEl_.textContent = 'Tracing: ';
      this.titleEl_.className = 'title';

      this.controlDiv_ = document.createElement('div');
      this.controlDiv_.className = 'control';

      this.leftControlsEl_ = document.createElement('div');
      this.leftControlsEl_.className = 'controls';
      this.rightControlsEl_ = document.createElement('div');
      this.rightControlsEl_.className = 'controls';

      var spacingEl = document.createElement('div');
      spacingEl.className = 'spacer';

      this.timelineContainer_ = document.createElement('div');
      this.timelineContainer_.className = 'timeline-container';

      var analysisContainer_ = document.createElement('div');
      analysisContainer_.className = 'analysis-container';

      this.analysisEl_ = new tracing.TimelineAnalysisView();

      this.dragEl_ = new TimelineDragHandle();
      this.dragEl_.target = analysisContainer_;

      this.findCtl_ = new TimelineFindControl();
      this.findCtl_.controller = new TimelineFindController();

      this.importErrorsButton_ = this.createImportErrorsButton_();
      this.importErrorsButton_.style.display = 'none';

      // Connect everything up.
      this.rightControls.appendChild(this.importErrorsButton_);
      this.rightControls.appendChild(this.findCtl_);
      this.controlDiv_.appendChild(this.titleEl_);
      this.controlDiv_.appendChild(this.leftControlsEl_);
      this.controlDiv_.appendChild(spacingEl);
      this.controlDiv_.appendChild(this.rightControlsEl_);
      this.appendChild(this.controlDiv_);

      this.appendChild(this.timelineContainer_);
      this.appendChild(this.dragEl_);

      analysisContainer_.appendChild(this.analysisEl_);
      this.appendChild(analysisContainer_);

      this.rightControls.appendChild(this.createHelpButton_());

      // Bookkeeping.
      this.onSelectionChangedBoundToThis_ = this.onSelectionChanged_.bind(this);
      document.addEventListener('keypress', this.onKeypress_.bind(this), true);
    },

    createImportErrorsButton_: function() {
      // Set by the embedder of the help button that we create in this function.
      var model;

      var dlg = new tracing.Overlay();
      dlg.classList.add('timeline-view-import-errors-overlay');
      dlg.autoClose = true;

      var showEl = document.createElement('div');
      showEl.className = 'timeline-button timeline-view-import-errors-button';
      showEl.textContent = 'Import errors!';
      showEl.__defineSetter__('model', function(value) {
        model = value;
      });

      var textEl = document.createElement('div');
      textEl.style.whiteSpace = 'pre';
      textEl.style.fontFamily = 'monospace';
      textEl.style.margin = '8px';

      var containerEl = document.createElement('div');
      containerEl.style.overflow = 'auto';
      containerEl.style.minWidth = '400px';
      containerEl.style.minHeight = '200px';
      containerEl.style.maxWidth = '800px';
      containerEl.style.maxHeight = '500px';

      containerEl.textContent = 'Errors occurred during import:';
      containerEl.appendChild(textEl);
      dlg.appendChild(containerEl);

      function onClick() {
        dlg.visible = true;
        textEl.textContent = model.importErrors.join("\n");
      }
      showEl.addEventListener('click', onClick.bind(this));

      return showEl;
    },

    createHelpButton_: function() {
      var dlg = new tracing.Overlay();
      dlg.classList.add('timeline-view-help-overlay');
      dlg.autoClose = true;
      dlg.additionalCloseKeyCodes.push('?'.charCodeAt(0));

      var showEl = document.createElement('div');
      showEl.className = 'timeline-button timeline-view-help-button';
      showEl.textContent = '?';

      var helpTextEl = document.createElement('div');
      helpTextEl.style.whiteSpace = 'pre';
      helpTextEl.style.fontFamily = 'monospace';
      dlg.appendChild(helpTextEl);

      function onClick(e) {
        dlg.visible = true;
        if (this.timeline_)
          helpTextEl.textContent = this.timeline_.keyHelp;
        else
          helpTextEl.textContent = 'No content loaded. For interesting help, load something.';
        document.addEventListener('click', bgClick);

        // Stop event so it doesn't trigger new click listener on document.
        e.stopPropagation();
        return false;
      }

      function bgClick(e) {
        var target = e.target;
        // Check to make sure we are not in dlg.
        while(target!==null) {
          if(target === dlg) {
            return false;
          }
          target = target.parentNode;
        }
        // If the click occured outside dlg.
        closeHelp();
        return false;
      }

      function closeHelp() {
        if (!dlg.visible) {
          return;
        }
        document.removeEventListener('click', bgClick, true);
        dlg.visible = false;
      }

      showEl.addEventListener('click', onClick.bind(this));

      return showEl;
    },

    get leftControls() {
      return this.leftControlsEl_;
    },

    get rightControls() {
      return this.rightControlsEl_;
    },

    get title() {
      return this.titleEl_.textContent.substring(
        this.titleEl_.textContent.length - 2);
    },

    set title(text) {
      this.titleEl_.textContent = text + ':';
    },

    set traceData(traceData) {
      this.model = new tracing.TimelineModel(traceData);
    },

    get model() {
      return this.timelineModel_;
    },

    set model(model) {
      this.timelineModel_ = model;

      // remove old timeline
      this.timelineContainer_.textContent = '';
      this.importErrorsButton_.style.display = 'none';
      this.importErrorsButton_.model = undefined;

      // create new timeline if needed
      if (this.timelineModel_.minTimestamp !== undefined) {
        if (this.timeline_)
          this.timeline_.detach();
        this.timeline_ = new tracing.Timeline();
        this.timeline_.model = this.timelineModel_;
        this.timeline_.focusElement =
            this.focusElement_ ? this.focusElement_ : this.parentElement;
        this.timelineContainer_.appendChild(this.timeline_);
        this.timeline_.addEventListener('selectionChange',
                                        this.onSelectionChangedBoundToThis_);

        this.findCtl_.controller.timeline = this.timeline_;
        if (this.timeline_.model.importErrors.length) {
          this.importErrorsButton_.model = model;
          this.importErrorsButton_.style.display = ''; // Show the button.
        }
        this.onSelectionChanged_();
      } else {
        this.timeline_ = undefined;
        this.findCtl_.controller.timeline = undefined;
      }
    },

    get timeline() {
      return this.timeline_;
    },

    /**
     * Sets the element whose focus state will determine whether
     * to respond to keybaord input.
     */
    set focusElement(value) {
      this.focusElement_ = value;
      if (this.timeline_)
        this.timeline_.focusElement = value;
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
     * @return {boolean} Whether the current timeline is attached to the
     * document.
     */
    get isAttachedToDocument_() {
      var cur = this;
      while (cur.parentNode)
        cur = cur.parentNode;
      return cur == this.ownerDocument;
    },

    get listenToKeys_() {
      if (!this.isAttachedToDocument_)
        return;
      if (!this.focusElement_)
        return true;
      if (this.focusElement.tabIndex >= 0)
        return document.activeElement == this.focusElement;
      return true;
    },

    onKeypress_: function(e) {
      if (!this.listenToKeys_)
        return;

      if (event.keyCode == '/'.charCodeAt(0)) { // / key
        this.findCtl_.focus();
        event.preventDefault();
        return;
      } else if (e.keyCode == '?'.charCodeAt(0)) {
        this.querySelector('.timeline-view-help-button').click();
        e.preventDefault();
      }
    },

    beginFind: function() {
      if (this.findInProgress_)
        return;
      this.findInProgress_ = true;
      var dlg = TimelineFindControl();
      dlg.controller = new TimelineFindController();
      dlg.controller.timeline = this.timeline;
      dlg.visible = true;
      dlg.addEventListener('close', function() {
        this.findInProgress_ = false;
      }.bind(this));
      dlg.addEventListener('findNext', function() {
      });
      dlg.addEventListener('findPrevious', function() {
      });
    },

    onSelectionChanged_: function(e) {
      var oldScrollTop = this.timelineContainer_.scrollTop;
      this.analysisEl_.selection = this.timeline_.selection;
      this.timelineContainer_.scrollTop = oldScrollTop;
    }
  };

  /**
   * Timeline Drag Handle
   * Detects when user clicks handle determines new height of container based
   * on user's vertical mouse move and resizes the target.
   * @constructor
   * @extends {HTMLDivElement}
   * You will need to set target to be the draggable element
   */
  var TimelineDragHandle = base.ui.define('div');

  TimelineDragHandle.prototype = {
    __proto__: HTMLDivElement.prototype,

    decorate: function() {
      this.className = 'timeline-drag-handle';
      this.lastMousePosY = 0;
      this.dragAnalysis = this.dragAnalysis.bind(this);
      this.onMouseUp = this.onMouseUp.bind(this);
      this.addEventListener('mousedown', this.onMouseDown);
    },

    dragAnalysis: function(e) {
      // Compute the difference in height position.
      var dy = this.lastMousePosY - e.clientY;
      // If style is not set, start off with computed height.
      if (!this.target.style.height)
        this.target.style.height = window.getComputedStyle(this.target).height;
      // Calculate new height of the container.
      this.target.style.height = parseInt(this.target.style.height) + dy + 'px';
      this.lastMousePosY = e.clientY;
    },

    onMouseDown: function(e) {
      this.lastMousePosY = e.clientY;
      document.addEventListener('mousemove', this.dragAnalysis);
      document.addEventListener('mouseup', this.onMouseUp);
      e.stopPropagation();
      return false;
    },

    onMouseUp: function(e) {
      document.removeEventListener('mousemove', this.dragAnalysis);
      document.removeEventListener('mouseup', this.onMouseUp);
    }
  };

  return {
    TimelineFindControl: TimelineFindControl,
    TimelineFindController: TimelineFindController,
    TimelineView: TimelineView
  };
});
