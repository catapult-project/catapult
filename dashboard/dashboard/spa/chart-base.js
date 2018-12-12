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

    antiBrushes_(brushes) {
      return ChartBase.antiBrushes(brushes);
    }

    tooltipHidden_(tooltip) {
      return !tooltip || !tooltip.isVisible || this.isEmpty_(tooltip.rows);
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
  }

  ChartBase.State = {
    brushSize: options => options.brushSize || 10,
    graphHeight: options => options.graphHeight || 200,
    lines: options => options.lines || [],
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

    tooltip: (statePath, rows) => async(dispatch, getState) => {
      dispatch(Redux.UPDATE(statePath + '.tooltip', {rows}));
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

  cp.ElementBase.register(ChartBase);

  return {ChartBase};
});
