/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';
tr.exportTo('cp', () => {
  PolymerSvgTemplate('chart-base');

  class ChartBase extends Polymer.GestureEventListeners(cp.ElementBase) {
    collectIcons_(line) {
      if (!line || !line.data) return [];
      return line.data.filter(datum => datum.icon);
    }

    hasCursor_(axis) {
      return axis && axis.cursor && axis.cursor.pct;
    }

    antiBrushes_(brushes) {
      return ChartBase.antiBrushes(brushes);
    }

    tooltipHidden_(tooltip) {
      return !tooltip || !tooltip.isVisible || this.isEmpty_(tooltip.rows);
    }

    get isMouseOverMain() {
      return getComputedStyle(this.$.main).getPropertyValue(
          '--mouse').includes('inside');
    }

    maybePollMouseLeaveMain_() {
      if (this.mouseLeaveMainPoller_) return;
      this.mouseLeaveMainPoller_ = this.pollMouseLeaveMain_();
    }

    async pollMouseLeaveMain_() {
      // Ideally, an on-mouseleave listener would dispatchEvent so that callers
      // could hide the tooltip and whatever else when the mouse leaves the main
      // area. However, mouseleave and mouseout are flaky in obnoxious ways. CSS
      // :hover seems to be robust, so a :hover selector sets the property
      // --mouse: inside. mouseLeaveMain_ polls this property.
      while (this.isMouseOverMain) {
        await cp.animationFrame();
      }
      this.dispatchEvent(new CustomEvent('mouse-leave-main', {
        bubbles: true,
        composed: true,
      }));
      this.mouseLeaveMainPoller_ = undefined;
    }

    brushPointSize_(brushSize) {
      if (Number.isNaN(brushSize)) return 0;
      return brushSize * 1.5;
    }

    onMainClick_(event) {
      this.dispatchEvent(new CustomEvent('chart-click', {
        bubbles: true,
        composed: true,
      }));
    }

    async onTrackBrushHandle_(event) {
      const xPct = ChartBase.computeBrush(
          event.detail.x, await cp.measureElement(this.$.main));
      this.dispatch('brushX', this.statePath, event.model.brushIndex, xPct);
      this.dispatchEvent(new CustomEvent('brush', {
        bubbles: true,
        composed: true,
        detail: {
          brushIndex: event.model.brushIndex,
          sourceEvent: event,
        },
      }));
    }

    async onMouseMoveMain_(event) {
      if (!this.showTooltip) return;

      // It might be expensive to measure $.main and getNearestPoint, so
      // debounce to save CPU.
      this.debounce('mousemove-main', async() => {
        const mainRect = await cp.measureElement(this.$.main);
        const {nearestPoint, nearestLine} = ChartBase.getNearestPoint(
            event, mainRect, this.lines);
        if (!nearestPoint) return;

        // It might be expensive to build and render the tooltip, so only
        // dispatch get-tooltip when the nearestPoint changes.
        if (nearestPoint === this.previousNearestPoint) return;
        this.previousNearestPoint = nearestPoint;

        this.dispatchEvent(new CustomEvent('get-tooltip', {
          bubbles: true,
          composed: true,
          detail: {mainRect, nearestPoint, nearestLine},
        }));
        this.maybePollMouseLeaveMain_();
      }, Polymer.Async.animationFrame);
    }
  }

  ChartBase.State = {
    brushSize: options => options.brushSize || 10,
    graphHeight: options => options.graphHeight || 200,
    lines: options => options.lines || [],
    showTooltip: options => options.showTooltip || false,
    tooltip: options => {
      return {
        isVisible: false,
        left: '',
        right: '',
        top: '',
        bottom: '',
        color: '',
        rows: [],
        ...options.tooltip,
      };
    },
    xAxis: options => {
      return {
        brushes: [],
        height: 0,
        range: new tr.b.math.Range(),
        showTickLines: false,
        ticks: [],
        ...options.xAxis,
      };
    },
    yAxis: options => {
      return {
        brushes: [],
        range: new tr.b.math.Range(),
        showTickLines: false,
        ticks: [],
        width: 0,
        ...options.yAxis,
      };
    },
  };

  ChartBase.properties = cp.buildProperties('state', ChartBase.State);
  ChartBase.buildState = options => cp.buildState(ChartBase.State, options);

  ChartBase.actions = {
    brushX: (statePath, brushIndex, xPct) => async(dispatch, getState) => {
      const path = `${statePath}.xAxis.brushes.${brushIndex}`;
      dispatch(Redux.UPDATE(path, {xPct}));
    },
  };

  ChartBase.reducers = {
    boldLine: (state, {lineIndex}, rootState) => {
      const lines = state.lines.map((line, index) => {
        const strokeWidth = (index === lineIndex) ? 2 : 1;
        return {...line, strokeWidth};
      });
      if (lineIndex !== undefined && lineIndex !== (lines.length - 1)) {
        // Move lineIndex to the end so it is drawn over top of any other
        // lines.
        [lines[lineIndex], lines[lines.length - 1]] =
          [lines[lines.length - 1], lines[lineIndex]];
      }
      return {...state, lines};
    },
  };

  ChartBase.antiBrushes = brushes => {
    if (!brushes || brushes.length === 0) return [];
    if (brushes.length % 2 === 1) throw new Error('Odd number of brushes');
    brushes = brushes.map(brush =>
      Number.parseFloat(brush.xPct)).sort((a, b) => a - b);
    let previous = {start: 0, length: undefined};
    const antiBrushes = [previous];
    for (let i = 0; i < brushes.length; i += 2) {
      if (previous.start === 0 && brushes[i] === 0) {
        antiBrushes.splice(0, 1);
      } else {
        previous.length = (brushes[i] - previous.start) + '%';
        previous.start += '%';
      }
      if (brushes[i + 1] === 100) return antiBrushes;
      previous = {start: brushes[i + 1], length: undefined};
      antiBrushes.push(previous);
    }
    previous.length = (100 - previous.start) + '%';
    previous.start += '%';
    return antiBrushes;
  };

  ChartBase.computeBrush = (x, containerRect) => {
    const value = tr.b.math.normalize(
        x, containerRect.left, containerRect.right);
    return tr.b.math.clamp(100 * value, 0, 100) + '%';
  };

  ChartBase.getNearestPoint = (pt, rect, lines) => {
    const xPct = tr.b.math.normalize(pt.x, rect.left, rect.right) * 100;
    const yPct = tr.b.math.normalize(pt.y, rect.top, rect.bottom) * 100;
    let nearestPoint;
    let nearestDelta;
    let nearestLine;
    for (const line of lines) {
      const datum = tr.b.findClosestElementInSortedArray(
          line.data, d => d.xPct, xPct, 10);
      if (datum === null) continue;
      const dx = xPct - datum.xPct;
      const dy = yPct - datum.yPct;
      const delta = Math.sqrt(dx * dx + dy * dy);
      if (nearestPoint && (nearestDelta < delta)) {
        continue;
      }
      nearestPoint = datum;
      nearestDelta = delta;
      nearestLine = line;
    }
    return {nearestPoint, nearestLine};
  };

  cp.ElementBase.register(ChartBase);

  return {ChartBase};
});
