/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import {LitElement, html, css} from 'lit-element';

export default class CpLoading extends LitElement {
  static get is() { return 'cp-loading'; }

  static get styles() {
    return css`
      :host {
        display: block;
        height: 4px;
        overflow: hidden;
        position: relative;
        width: 100%;
      }
      div {
        border-radius: 50%;
        height: 4px;
        overflow-x: hidden;
        position: absolute;
        transform-origin: left center;
        transform: scaleX(0);
        width: 100%;
        will-change: transform;
      }
      div:after {
        content: "";
        position: absolute;
        height: 5px;
      }
      :host([loading]) div {
        background: var(--primary-color-dark, blue);
        transform-origin: right center;
        animation: indeterminate-bar 2s linear infinite;
      }
      :host([loading]) div:after {
        content: "";
        transform-origin: center center;
        animation: indeterminate-splitter 2s linear infinite;
      }
      @keyframes indeterminate-bar {
        0% {
          transform: scaleX(1) translateX(-100%);
        }
        50% {
          transform: scaleX(1) translateX(0%);
        }
        75% {
          transform: scaleX(1) translateX(0%);
          animation-timing-function: cubic-bezier(.28,.62,.37,.91);
        }
        100% {
          transform: scaleX(0) translateX(0%);
        }
      }
      @keyframes indeterminate-splitter {
        0% {
          transform: scaleX(.75) translateX(-125%);
        }
        30% {
          transform: scaleX(.75) translateX(-125%);
          animation-timing-function: cubic-bezier(.42,0,.6,.8);
        }
        90% {
          transform: scaleX(.75) translateX(125%);
        }
        100% {
          transform: scaleX(.75) translateX(125%);
        }
      }
    `;
  }

  render() {
    return html`
      <div></div>
    `;
  }
}
customElements.define(CpLoading.is, CpLoading);
