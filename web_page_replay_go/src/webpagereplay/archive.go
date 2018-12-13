// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package webpagereplay

import (
	"bufio"
	"bytes"
	"compress/gzip"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"io/ioutil"
	"log"
	"net/http"
	"net/url"
	"os"
	"reflect"
	"sync"
)

var ErrNotFound = errors.New("not found")

// ArchivedRequest contains a single request and its response.
// Immutable after creation.
type ArchivedRequest struct {
	SerializedRequest  []byte
	SerializedResponse []byte // if empty, the request failed
}

func serializeRequest(req *http.Request, resp *http.Response) (*ArchivedRequest, error) {
	ar := &ArchivedRequest{}
	{
		var buf bytes.Buffer
		if err := req.Write(&buf); err != nil {
			return nil, fmt.Errorf("failed writing request for %s: %v", req.URL.String(), err)
		}
		ar.SerializedRequest = buf.Bytes()
	}
	{
		var buf bytes.Buffer
		if err := resp.Write(&buf); err != nil {
			return nil, fmt.Errorf("failed writing response for %s: %v", req.URL.String(), err)
		}
		ar.SerializedResponse = buf.Bytes()
	}
	return ar, nil
}

func (ar *ArchivedRequest) unmarshal(scheme string) (*http.Request, *http.Response, error) {
	req, err := http.ReadRequest(bufio.NewReader(bytes.NewReader(ar.SerializedRequest)))
	if err != nil {
		return nil, nil, fmt.Errorf("couldn't unmarshal request: %v", err)
	}

	if req.URL.Host == "" {
		req.URL.Host = req.Host
		req.URL.Scheme = scheme
	}

	resp, err := http.ReadResponse(bufio.NewReader(bytes.NewReader(ar.SerializedResponse)), req)
	if err != nil {
		if req.Body != nil {
			req.Body.Close()
		}
		return nil, nil, fmt.Errorf("couldn't unmarshal response: %v", err)
	}
	return req, resp, nil
}

// Archive contains an archive of requests. Immutable except when embedded in a WritableArchive.
// Fields are exported to enabled JSON encoding.
type Archive struct {
	// Requests maps host(url) => url => []request.
	// The two-level mapping makes it easier to search for similar requests.
	// There may be multiple requests for a given URL.
	Requests map[string]map[string][]*ArchivedRequest
	// Maps host string to DER encoded certs.
	Certs map[string][]byte
	// Maps host string to the negotiated protocol. eg. "http/1.1" or "h2"
	// If absent, will default to "http/1.1".
	NegotiatedProtocol map[string]string
	// The time seed that was used to initialize deterministic.js.
	DeterministicTimeSeedMs int64
}

func newArchive() Archive {
	return Archive{Requests: make(map[string]map[string][]*ArchivedRequest)}
}

// OpenArchive opens an archive file previously written by OpenWritableArchive.
func OpenArchive(path string) (*Archive, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, fmt.Errorf("could not open %s: %v", path, err)
	}
	defer f.Close()

	gz, err := gzip.NewReader(f)
	if err != nil {
		return nil, fmt.Errorf("gunzip failed: %v", err)
	}
	defer gz.Close()
	buf, err := ioutil.ReadAll(gz)
	if err != nil {
		return nil, fmt.Errorf("read failed: %v", err)
	}
	a := newArchive()
	if err := json.Unmarshal(buf, &a); err != nil {
		return nil, fmt.Errorf("json unmarshal failed: %v", err)
	}
	return &a, nil
}

// ForEach applies f to all requests in the archive.
func (a *Archive) ForEach(f func(req *http.Request, resp *http.Response) error) error {
	for _, urlmap := range a.Requests {
		for urlString, requests := range urlmap {
			fullURL, _ := url.Parse(urlString)
			for index, archivedRequest := range requests {
				req, resp, err := archivedRequest.unmarshal(fullURL.Scheme)
				if err != nil {
					log.Printf("Error unmarshaling request #%d for %s: %v", index, urlString, err)
					continue
				}
				if err := f(req, resp); err != nil {
					return err
				}
			}
		}
	}
	return nil
}

// Returns the der encoded cert and negotiated protocol.
func (a *Archive) FindHostTlsConfig(host string) ([]byte, string, error) {
	if cert, ok := a.Certs[host]; ok {
		return cert, a.findHostNegotiatedProtocol(host), nil
	}
	return nil, "", ErrNotFound
}

func (a *Archive) findHostNegotiatedProtocol(host string) string {
	if negotiatedProtocol, ok := a.NegotiatedProtocol[host]; ok {
		return negotiatedProtocol
	}
	return "http/1.1"
}

func assertCompleteURL(url *url.URL) {
	if url.Host == "" || url.Scheme == "" {
		log.Printf("Missing host and scheme: %v\n", url)
		os.Exit(1)
	}
}

// FindRequest searches for the given request in the archive.
// Returns ErrNotFound if the request could not be found. Does not consume req.Body.
// TODO: conditional requests
func (a *Archive) FindRequest(req *http.Request) (*http.Request, *http.Response, error) {
	hostMap := a.Requests[req.Host]
	if len(hostMap) == 0 {
		return nil, nil, ErrNotFound
	}

	// Exact match. Note that req may be relative, but hostMap keys are always absolute.
	assertCompleteURL(req.URL)

	var bestRatio float64
	if len(hostMap[req.URL.String()]) > 0 {
		var bestRequest *http.Request
		var bestResponse *http.Response
		// There can be multiple requests with the same URL string. If that's the case,
		// break the tie by the number of headers that match.
		for _, archivedRequest := range hostMap[req.URL.String()] {
			curReq, curResp, err := archivedRequest.unmarshal(req.URL.Scheme)
			if err != nil {
				log.Println("Error unmarshaling request")
				continue
			}
			if curReq.Method != req.Method {
				continue
			}
			rh := curReq.Header
			reqh := req.Header
			m := 1
			t := len(rh) + len(reqh)
			for k, v := range rh {
				if reflect.DeepEqual(v, reqh[k]) {
					m++
				}
			}
			ratio := 2 * float64(m) / float64(t)
			// Note that since |m| starts from 1. The ratio will be more than 0
			// even if no header matches.
			if ratio > bestRatio {
				bestRequest = curReq
				bestResponse = curResp
				bestRatio = ratio
			}
		}
		if bestRequest != nil && bestResponse != nil {
			return bestRequest, bestResponse, nil
		}
	}

	// For all URLs with a matching path, pick the URL that has the most matching query parameters.
	// The match ratio is defined to be 2*M/T, where
	//   M = number of matches x where a.Query[x]=b.Query[x]
	//   T = sum(len(a.Query)) + sum(len(b.Query))
	aq := req.URL.Query()

	var bestURL string

	for ustr := range hostMap {
		u, err := url.Parse(ustr)
		if err != nil {
			continue
		}
		if u.Path != req.URL.Path {
			continue
		}
		bq := u.Query()
		m := 1
		t := len(aq) + len(bq)
		for k, v := range aq {
			if reflect.DeepEqual(v, bq[k]) {
				m++
			}
		}
		ratio := 2 * float64(m) / float64(t)
		if ratio > bestRatio ||
			// Map iteration order is non-deterministic, so we must break ties.
			(ratio == bestRatio && ustr < bestURL) {
			bestURL = ustr
			bestRatio = ratio
		}
	}

	// TODO: Try each until one succeeds with a matching request method.
	if bestURL != "" {
		return findExactMatch(hostMap[bestURL], req.Method, req.URL.Scheme)
	}

	return nil, nil, ErrNotFound
}

// findExactMatch returns the first request that exactly matches the given request method.
func findExactMatch(requests []*ArchivedRequest, method string, scheme string) (*http.Request, *http.Response, error) {
	for _, archivedRequest := range requests {
		req, resp, err := archivedRequest.unmarshal(scheme)
		if err != nil {
			log.Printf("Error unmarshaling request: %v\nAR.Request: %q\nAR.Response: %q",
				err, archivedRequest.SerializedRequest, archivedRequest.SerializedResponse)
			continue
		}
		if req.Method == method {
			return req, resp, nil
		}
	}
	return nil, nil, ErrNotFound
}

type AddMode int

const (
	AddModeAppend            AddMode = 0
	AddModeOverwriteExisting AddMode = 1
	AddModeSkipExisting      AddMode = 2
)

func (a *Archive) addArchivedRequest(req *http.Request, resp *http.Response, mode AddMode) error {
	// Always use the absolute URL in this mapping.
	assertCompleteURL(req.URL)

	archivedRequest, err := serializeRequest(req, resp)
	if err != nil {
		return err
	}

	if a.Requests[req.Host] == nil {
		a.Requests[req.Host] = make(map[string][]*ArchivedRequest)
	}

	urlStr := req.URL.String()
	requests := a.Requests[req.Host][urlStr]
	if mode == AddModeAppend {
		requests = append(requests, archivedRequest)
	} else if mode == AddModeOverwriteExisting {
		log.Printf("Overwriting existing request")
		requests = []*ArchivedRequest{archivedRequest}
	} else if mode == AddModeSkipExisting {
		if requests != nil {
			log.Printf("Skipping existing request: %s", urlStr)
			return nil
		}
		requests = append(requests, archivedRequest)
	}
	a.Requests[req.Host][urlStr] = requests
	return nil
}

// Edit iterates over all requests in the archive. For each request, it calls f to
// edit the request. If f returns a nil pair, the request is deleted.
// The edited archive is returned, leaving the current archive is unchanged.
func (a *Archive) Edit(edit func(req *http.Request, resp *http.Response) (*http.Request, *http.Response, error)) (*Archive, error) {
	clone := newArchive()
	err := a.ForEach(func(oldReq *http.Request, oldResp *http.Response) error {
		newReq, newResp, err := edit(oldReq, oldResp)
		if err != nil {
			return err
		}
		if newReq == nil || newResp == nil {
			if newReq != nil || newResp != nil {
				panic("programming error: newReq/newResp must both be nil or non-nil")
			}
			return nil
		}
		// TODO: allow changing scheme or protocol?
		return clone.addArchivedRequest(newReq, newResp, AddModeAppend)
	})
	if err != nil {
		return nil, err
	}
	return &clone, nil
}

// Merge adds all the request of the provided archive to the receiver.
func (a *Archive) Merge(other *Archive) error {
	var numAddedRequests = 0
	var numSkippedRequests = 0
	err := other.ForEach(func(req *http.Request, resp *http.Response) error {
		foundReq, _, notFoundErr := a.FindRequest(req)
		if notFoundErr == ErrNotFound || req.URL.String() != foundReq.URL.String() {
			if err := a.addArchivedRequest(req, resp, AddModeAppend); err != nil {
				return err
			}
			numAddedRequests++
		} else {
			numSkippedRequests++
		}
		return nil
	})
	log.Printf("Merged requests: added=%d duplicates=%d \n", numAddedRequests, numSkippedRequests)
	return err
}

// Add the result of a get request to the receiver.
func (a *Archive) Add(method string, urlString string, mode AddMode) error {
	req, err := http.NewRequest(method, urlString, nil)
	if err != nil {
		return fmt.Errorf("Error creating request object: %v", err)
	}

	url, _ := url.Parse(urlString)
	// Print a warning for duplicate requests since the replay server will only
	// return the first found response.
	if mode == AddModeAppend || mode == AddModeSkipExisting {
		if foundReq, _, notFoundErr := a.FindRequest(req); notFoundErr != ErrNotFound {
			if foundReq.URL.String() == url.String() {
				if mode == AddModeSkipExisting {
					log.Printf("Skipping existing request: %s %s", req.Method, urlString)
					return nil
				}
				log.Printf("Adding duplicate request:")
			}
		}
	}

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return fmt.Errorf("Error fetching url: %v", err)
	}

	if err = a.addArchivedRequest(req, resp, mode); err != nil {
		return err
	}

	fmt.Printf("Added request: (%s %s) %s\n", req.Method, resp.Status, urlString)
	return nil
}

// Serialize serializes this archive to the given writer.
func (a *Archive) Serialize(w io.Writer) error {
	gz := gzip.NewWriter(w)
	if err := json.NewEncoder(gz).Encode(a); err != nil {
		return fmt.Errorf("json marshal failed: %v", err)
	}
	return gz.Close()
}

// WriteableArchive wraps an Archive with writable methods for recording.
// The file is not flushed until Close is called. All methods are thread-safe.
type WritableArchive struct {
	Archive
	f  *os.File
	mu sync.Mutex
}

// OpenWritableArchive opens an archive file for writing.
// The output is gzipped JSON.
func OpenWritableArchive(path string) (*WritableArchive, error) {
	f, err := os.Create(path)
	if err != nil {
		return nil, fmt.Errorf("could not open %s: %v", path, err)
	}
	return &WritableArchive{Archive: newArchive(), f: f}, nil
}

// RecordRequest records a request/response pair in the archive.
func (a *WritableArchive) RecordRequest(req *http.Request, resp *http.Response) error {
	a.mu.Lock()
	defer a.mu.Unlock()
	return a.addArchivedRequest(req, resp, AddModeAppend)
}

// RecordTlsConfig records the cert used and protocol negotiated for a host.
func (a *WritableArchive) RecordTlsConfig(host string, der_bytes []byte, negotiatedProtocol string) {
	a.mu.Lock()
	defer a.mu.Unlock()
	if a.Certs == nil {
		a.Certs = make(map[string][]byte)
	}
	if _, ok := a.Certs[host]; !ok {
		a.Certs[host] = der_bytes
	}
	if a.NegotiatedProtocol == nil {
		a.NegotiatedProtocol = make(map[string]string)
	}
	a.NegotiatedProtocol[host] = negotiatedProtocol
}

// Close flushes the the archive and closes the output file.
func (a *WritableArchive) Close() error {
	a.mu.Lock()
	defer a.mu.Unlock()
	defer func() { a.f = nil }()
	if a.f == nil {
		return errors.New("already closed")
	}

	if err := a.Serialize(a.f); err != nil {
		return err
	}
	return a.f.Close()
}
