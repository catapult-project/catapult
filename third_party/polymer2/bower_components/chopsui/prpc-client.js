// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// TODO(jeffcarp): Package as an ES module when ready.
(function(window) {

  /**
   * An enum object mapping gRPC code names to integer codes.
   * Reference: https://github.com/grpc/grpc-go/blob/972dbd2/codes/codes.go#L43
   * @readonly
   * @enum {number}
   */
  const RpcCode = Object.freeze({
    OK: 0,
    CANCELED: 1,
    UNKNOWN: 2,
    INVALID_ARGUMENT: 3,
    DEADLINE_EXCEEDED: 4,
    NOT_FOUND: 5,
    ALREADY_EXISTS: 6,
    PERMISSION_DENIED: 7,
    RESOURCE_EXHAUSTED: 8,
    FAILED_PRECONDITION: 9,
    ABORTED: 10,
    OUT_OF_RANGE: 11,
    UNIMPLEMENTED: 12,
    INTERNAL: 13,
    UNAVAILABLE: 14,
    DATA_LOSS: 15,
    UNAUTHENTICATED: 16,
  });

  const rpcCodeNames = {};
  for (const name in RpcCode) {
    rpcCodeNames[RpcCode[name]] = name;
  }

  /**
   * Converts a gRPC code integer into its code name.
   * @param rpcCode {number} the RPC code to convert.
   * @return {string|undefined} the code name of the corresponding gRPC code
   * or undefined if not found.
   */
  function rpcCodeToCodeName(rpcCode) {
    return rpcCodeNames[rpcCode];
  }

  /**
   * Class for interacting with a pRPC API.
   * Protocol: https://godoc.org/go.chromium.org/luci/grpc/prpc
   */
  class PrpcClient {

    /**
     * @constructor
     * @param options {Object} with the following (all optional) config options:
     * - host: {string} pRPC server host, defaults to current document host.
     * - accessToken {string} OAuth 2.0 access token to use in RPC.
     * - insecure {boolean} if true, use HTTP instead of HTTPS. Defaults to false.
     * - fetchImpl {function} if supplied, use this function instead of fetch.
     *   Defaults to `window.fetch`.
     */
    constructor(options=null) {
      options = options || {};
      this.host = options.host || document.location.host;
      this.accessToken = options.accessToken || null;
      this.insecure = options.hasOwnProperty('insecure') && Boolean(options.insecure);
      this.fetchImpl = options.fetchImpl || window.fetch.bind(window);
    }

    /**
     * Send an RPC request.
     * @async
     * @param service {string} Full service name, including package name.
     * @param method {string} Service method name.
     * @param message {Object} The protobuf message to send.
     * Note: because this method is async the following exceptions reject
     * the returned Promise.
     * @throws {TypeError} for invalid arguments.
     * @throws {ProtocolError} when an error happens at the pRPC protocol
     * (HTTP) level.
     * @throws {GrpcError} when the response returns a non-OK gRPC status.
     * @return {Promise<Object>} a promise resolving the response message
     * or rejecting with an error..
     */
    async call(service, method, message) {
      if (!service) {
        throw new TypeError('missing required argument: service');
      }
      if (!method) {
        throw new TypeError('missing required argument: method');
      }
      if (!message) {
        throw new TypeError('missing required argument: message');
      }
      if (!(message instanceof Object)) {
        throw new TypeError('argument `message` must be a protobuf object');
      }

      const protocol = this.insecure === true ? 'http:' : 'https:';
      const url = `${protocol}//${this.host}/prpc/${service}/${method}`;
      const options = this._requestOptions(message);

      const response = await this.fetchImpl(url, options);

      if (!response.headers.has('X-Prpc-Grpc-Code')) {
        throw new ProtocolError(response.status,
            'Invalid response: no X-Prpc-Grpc-Code response header');
      }

      const rpcCode = Number.parseInt(response.headers.get('X-Prpc-Grpc-Code'), 10);
      if (Number.isNaN(rpcCode)) {
        throw new ProtocolError(response.status,
            `Invalid X-Prpc-Grpc-Code response header`);
      }

      const XSSIPrefix = ')]}\'';
      const rawResponseText = await response.text();

      if (rpcCode !== RpcCode.OK) {
        throw new GrpcError(rpcCode, rawResponseText);
      }

      if (!rawResponseText.startsWith(XSSIPrefix)) {
        throw new ProtocolError(response.status,
            `Response body does not start with XSSI prefix: ${XSSIPrefix}`);
      }

      return JSON.parse(rawResponseText.substr(XSSIPrefix.length));
    }

    /**
     * @return {Object} the options used in fetch().
     */
    _requestOptions(message) {
      const headers = {
        'accept': 'application/json',
        'content-type': 'application/json',
      };
      if (this.accessToken) {
        headers.authorization = `Bearer ${this.accessToken}`;
      }

      return {
        credentials: 'omit',
        method: 'POST',
        headers: headers,
        body: JSON.stringify(message),
      };
    }
  }

  /**
   * Data class representing an error returned from pRPC-gRPC.
   */
  class GrpcError extends Error {

    /**
     * @constructor
     * @param code {number} gRPC code.
     * @param description {string} error message.
     */
    constructor(code, description) {
      super();
      if (code === null) {
        throw new Error('missing required argument: code');
      }

      this.code = code;
      this.codeName = rpcCodeToCodeName(code);
      this.description = description;
    }

    get message() {
      return `code: ${this.code} (${this.codeName}) desc: ${this.description}`;
    }
  }

  /**
   * Data class representing a violation of the pRPC protocol.
   */
  class ProtocolError extends Error {
    constructor(httpStatus, description) {
      super();
      if (httpStatus === null) {
        throw new Error('missing required argument: httpStatus');
      }

      this.httpStatus = httpStatus;
      this.description = description;
    }

    get message() {
      return `status: ${this.httpStatus} desc: ${this.description}`;
    }
  }

  // Export variables onto window.chops.rpc.
  window.chops = window.chops || {};
  window.chops.rpc = window.chops.rpc || {};
  Object.assign(window.chops.rpc, {
    RpcCode,
    rpcCodeToCodeName,
    PrpcClient,
    ProtocolError,
    GrpcError,
  });
})(window);
