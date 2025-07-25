// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package webpagereplay

import (
	"bytes"
	"compress/flate"
	"compress/gzip"
	"crypto/sha256"
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"io/ioutil"
	"log"
	"net/http"
	"net/url"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"

	"github.com/andybalholm/brotli"
	"github.com/tdewolff/minify/v2"
	"github.com/tdewolff/minify/v2/js"
)

type readerWithError struct {
	r   io.Reader
	err error
}

func (r *readerWithError) Read(p []byte) (int, error) {
	n, err := r.r.Read(p)
	if err == io.EOF && r.err != nil {
		err = r.err
	}
	return n, err
}

// cloneHeaders clones h.
func cloneHeaders(h http.Header) http.Header {
	hh := make(http.Header, len(h))
	for k, vv := range h {
		if vv == nil {
			hh[k] = nil
		} else {
			hh[k] = append([]string{}, vv...)
		}
	}
	return hh
}

// transformResponseBody applies a transformation function to the response
// body.
// tf is passed an uncompressed body and should return an uncompressed body.
// The final response will be compressed if allowed by
// resp.Header[ContentEncoding].
func transformResponseBody(resp *http.Response, f func([]byte) []byte) {
	oldBody, err := ioutil.ReadAll(resp.Body)
	resp.Body.Close()
	if err != nil {
		// We were unable to read the body, e.g. because it was ill-formed. Nothing
		// else we can do, just keep it as is.
		resp.Body = ioutil.NopCloser(bytes.NewReader(oldBody))
		log.Printf("Error while injecting script: %v", err)
		return
	}

	var isCompressed bool
	var ce string
	if encodings, ok := resp.Header["Content-Encoding"]; ok && len(encodings) > 0 {
		// TODO(xunjieli): Use the last CE for now. Support chained CEs.
		ce = strings.ToLower(encodings[len(encodings)-1])
		isCompressed = (ce != "" && ce != "identity")
	}

	// Decompress as needed.
	newBody := oldBody
	if isCompressed {
		newBody, err = decompressBody(ce, newBody)
		if err != nil {
			// It's possible the body uses an encryption algorithm supported by the
			// web but not by webpagereplay. We don't want the tool to fail completely
			// in that case, so just log the error and keep the body as is.
			resp.Body = ioutil.NopCloser(bytes.NewReader(oldBody))
			log.Printf("Error while injecting script: %v", err)
			return
		}
	}

	// Transform and recompress as needed.
	newBody = f(newBody)
	if isCompressed {
		newBody, _, err = CompressBody(ce, newBody)
		if err != nil {
			// Usually if it was possible to decompress the body, it should be
			// possible to recompress it. On the off-chance recompression fails, the
			// same comment as above applies: log the error, keep the body as is.
			resp.Body = ioutil.NopCloser(bytes.NewReader(oldBody))
			log.Printf("Error while injecting script: %v", err)
			return
		}
	}
	resp.Body = ioutil.NopCloser(bytes.NewReader(newBody))

	// ContentLength has changed, so update the outgoing headers accordingly.
	if resp.ContentLength >= 0 {
		resp.ContentLength = int64(len(newBody))
		resp.Header.Set("Content-Length", strconv.Itoa(len(newBody)))
	}
}

// Decompresses Response Body in place.
func DecompressResponse(resp *http.Response) error {
	ce := strings.ToLower(resp.Header.Get("Content-Encoding"))
	isCompressed := (ce != "" && ce != "identity")
	if isCompressed {
		body, err := ioutil.ReadAll(resp.Body)
		if err != nil {
			return err
		}
		resp.Body.Close()
		body, err = decompressBody(ce, body)
		if err != nil {
			return err
		}
		resp.ContentLength = int64(len(body))
		resp.Body = ioutil.NopCloser(bytes.NewReader(body))
	}
	return nil
}

// decompressBody reads a response body and decompresses according to the
// given Content-Encoding.
func decompressBody(ce string, compressed []byte) ([]byte, error) {
	var r io.ReadCloser
	switch strings.ToLower(ce) {
	case "gzip":
		var err error
		r, err = gzip.NewReader(bytes.NewReader(compressed))
		if err != nil {
			return nil, err
		}
	case "deflate":
		r = flate.NewReader(bytes.NewReader(compressed))
	case "br":
		return ioutil.ReadAll(brotli.NewReader(bytes.NewReader(compressed)))
	default:
		// Unknown compression type or uncompressed.
		return compressed, errors.New("unknown compression: " + ce)
	}
	defer r.Close()
	return ioutil.ReadAll(r)
}

// CompressBody reads a response body and compresses according to the given
// Accept-Encoding.
// The chosen compressed encoding is returned along with the compressed body.
func CompressBody(ae string, uncompressed []byte) ([]byte, string, error) {
	var buf bytes.Buffer
	var w io.WriteCloser
	outCE := ""
	ae = strings.ToLower(ae)
	switch {
	case strings.Contains(ae, "gzip"):
		w = gzip.NewWriter(&buf)
		outCE = "gzip"
	case strings.Contains(ae, "deflate"):
		w, _ = flate.NewWriter(&buf, flate.DefaultCompression) // never fails
		outCE = "deflate"
	case strings.Contains(ae, "br"):
		w = brotli.NewWriter(&buf)
		outCE = "br"
	default:
		// Unknown compression type or compression not allowed.
		return uncompressed, "identity", errors.New("unknown compression: " + ae)
	}
	if _, err := io.Copy(w, bytes.NewReader(uncompressed)); err != nil {
		return buf.Bytes(), outCE, err
	}
	err := w.Close()
	return buf.Bytes(), outCE, err
}

// getCSPScriptSrcDirectiveFromHeaders returns a Content-Security-Policy (CSP)
// header's script source directive. If a header set does not have a CSP
// header or if the CSP header does not have a script-src directive,
// getCSPScriptSrcDirectiveFromHeaders returns an empty string.
func getCSPScriptSrcDirectiveFromHeaders(header http.Header) string {
	// There might be multiple Content-Security-Policy instances. Look for
	// script-src across all of them first, then  default-src.
	for _, csp := range header.Values("Content-Security-Policy") {
		for _, directive := range strings.Split(csp, ";") {
			directive = strings.TrimSpace(directive)
			if strings.HasPrefix(directive, "script-src") {
				return directive
			}
		}
	}
	for _, csp := range header.Values("Content-Security-Policy") {
		for _, directive := range strings.Split(csp, ";") {
			directive = strings.TrimSpace(directive)
			if strings.HasPrefix(directive, "default-src") {
				return directive
			}
		}
	}
	return ""
}

// getScriptSrcNonceTokenFromCSPHeader returns the nonce token from a
// Content-Security-Policy (CSP) header's script source directive, or an empty
// string if the CSP header's script source
// does not contain a nonce.
// For more background information on CSP and nonce, please refer to
// https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/
// Content-Security-Policy/script-src
// https://developers.google.com/web/fundamentals/security/csp/
func getNonceTokenFromCSPHeaderScriptSrc(cspScriptSrc string) string {
	cspScriptSrc = strings.Trim(cspScriptSrc, " ")
	tokens := strings.Split(cspScriptSrc, " ")
	for _, token := range tokens {
		token = strings.TrimSpace(token)
		if strings.HasPrefix(token, "'nonce-") {
			token = strings.TrimPrefix(token, "'nonce-")
			token = strings.TrimSuffix(token, "'")
			return token
		}
	}

	return ""
}

// transformCSPHeader transforms a Content-Security-Policy (CSP) header to
// permit execution of inline scripts. Without this permission a page with a
// restrictive CSP will not execute WPR
// injected scripts.
// For more background information on CSP, please refer to
// https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/
// Content-Security-Policy/script-src
// https://developers.google.com/web/fundamentals/security/csp/
func transformCSPHeader(header http.Header, injectedScriptSha256 string) {
	csps := header.Values("Content-Security-Policy")
	for cspIndex, csp := range csps {
		// Some sites will have more than one csp entry.
		csps[cspIndex] = getUpdatedSingleCSPHeader(csp, injectedScriptSha256)
	}
}

// getUpdatedSingleCSPHeader looks at an existing single csp string and updates
// the script permissions if necessary. It always returns a csp string, only
// altered when needed.
func getUpdatedSingleCSPHeader(csp string, injectedScriptSha256 string) string {
	if csp == "" {
		return ""
	}
	// We prefer the 'script-src', but if it doesn't exist, we want to update a
	// 'default-src' directive if it exists.
	directives := strings.Split(csp, ";")
	updateIndex := -1
	for index, directive := range directives {
		directive = strings.TrimSpace(directive)
		if strings.HasPrefix(directive, "script-src") ||
		   strings.HasPrefix(directive, "default-src") {
			updateIndex = index
			if strings.HasPrefix(directive, "script-src") {
			  break
			}
		}
	}
	// No CSP policy to worry about updating.
	if updateIndex < 0 {
		return csp
	}
	updateDirective := directives[updateIndex]
	if getNonceTokenFromCSPHeaderScriptSrc(updateDirective) != "" {
		// If the CSP header's script-src contains a nonce, then
		// transformCSPHeader does nothing.
		// WPR will add the nonce token to any injected script to open the
		// permission.
		return csp
	}
	// Break the 'script-src' or 'default-src' directive into more tokens,
	// and examine each token.
	tokens := strings.Split(updateDirective, " ")
	newDirective := ""
	needsUnsafeInline := true
	lookingForSha := true
	for _, token := range tokens {
		token = strings.TrimSpace(token)
		// All keyword tokens ['unsafe-inline', 'none', 'nonce-...', 'sha...']
		// are single-quote wrapped in the CSP headers.
		if token == "'unsafe-inline'" {
			needsUnsafeInline = false
		}
		// If the CSP header contains a hash, append the hash of the injected
		// script.
		// If a CSP specifies a hash, only inline scripts matching the hash
		// may execute.
		if strings.HasPrefix(token, "'sha256-") ||
			strings.HasPrefix(token, "'sha384-") ||
			strings.HasPrefix(token, "'sha512-") {
			// Only add the injected script the first time we are at a block of sha
			// entries, otherwise we may repeat it several times.
			if lookingForSha {
				lookingForSha = false
				newDirective += "'sha256-" + injectedScriptSha256 + "' "
			}
			needsUnsafeInline = false
		} else {
			lookingForSha = true
		}
		// Don't add back 'none' to our set, as if it is the only item it
		// follows we will be adding 'unsafe-inline' below.
		if token == "'none'" {
			continue
		}
		newDirective += token + " "
	}

	if needsUnsafeInline {
		newDirective += "'unsafe-inline'"
	}

	directives[updateIndex] = newDirective
	newCsp := strings.Join(directives, ";")
	return newCsp
}

// ResponseTransformer is an interface for transforming HTTP responses.
type ResponseTransformer interface {
	// Transform attempts to apply transformations to the response, for example
	// updating resp.Header or wrapping resp.Body. The transformer may inspect
	// the request but should not modify the request.
	// Transformations can fail because the web is wild, e.g. `resp` could be
	// ill-formed, preventing reading. We don't want to stop recording nor
	// replaying in that case. So this method is best-effort and in doubt should
	// leave `resp` unchanged.
	// Failures that don't depend on `req` or `resp` should be raised before this
	// is invoked, e.g. attempting to inject a script file that doesn't exist.
	Transform(req *http.Request, resp *http.Response)
}

// NewScriptInjector constructs a transformer that injects the given script
// after the first <head>, <html>, or <!doctype html> tag. The script is
// minified before injection.
func NewScriptInjector(
	script []byte, replacements map[string]string) (ResponseTransformer, error) {
	for oldstr, newstr := range replacements {
		script = bytes.Replace(script, []byte(oldstr), []byte(newstr), -1)
	}
	m := minify.New()
	m.AddFunc("application/javascript", js.Minify)
	var minifiedJsBuffer bytes.Buffer
	err := m.Minify("application/javascript", &minifiedJsBuffer, bytes.NewReader(script))
	if err != nil {
		return nil, err
	}
	// Compute the sha256 hash of the script content.
	// WPR may need to use the sha256 hash in a CSP header to grant the injected
	// script execute permission.
	sha256Bytes := sha256.Sum256(minifiedJsBuffer.Bytes())
	sha256String := base64.URLEncoding.EncodeToString(sha256Bytes[:])
	return &scriptInjector{minifiedJsBuffer.Bytes(), sha256String}, nil
}

// NewScriptInjectorFromFile creates a script injector from a script stored in
// a file.
func NewScriptInjectorFromFile(
	filename string, replacements map[string]string) (
	ResponseTransformer, error) {
	script, err := ioutil.ReadFile(filename)
	if err != nil {
		return nil, err
	}
	return NewScriptInjector(script, replacements)
}

var (
	doctypeRE             = regexp.MustCompile(
		`(?is)^.*?(<!--.*-->)?.*?<!doctype html>`)
	htmlRE = regexp.MustCompile(
		`(?is)^.*?(<!--.*-->)?.*?<html.*?>`)
	headRE = regexp.MustCompile(
		`(?is)^.*?(<!--.*-->)?.*?<head.*?>`)
)

type scriptInjector struct {
	script []byte
	sha256 string
}

// Given a nonce, getScriptWithNonce returns the injected script text with the
// nonce.
// If nonce is an empty string, getScriptWithNonce returns the script block
// without attaching a nonce attribute.
// Some responses may specify a nonce inside their Content-Security-Policy,
// script-src directive.
// The script injector needs to set the injected script's nonce attribute to
// open execute permission for the injected script.
func (si *scriptInjector) getScriptWithNonce(nonce string) []byte {
	var buffer bytes.Buffer
	buffer.Write([]byte("<script"))
	if nonce != "" {
		buffer.Write([]byte(" nonce=\""+nonce+"\""))
	}
	buffer.Write([]byte(">"))
	buffer.Write(si.script)
	buffer.Write([]byte("</script>"))
	return buffer.Bytes()
}

func (si *scriptInjector) Transform(_ *http.Request, resp *http.Response) {
	// Skip non-HTML non-200 responses.
	if !strings.HasPrefix(
		strings.ToLower(resp.Header.Get("Content-Type")), "text/html") {
		return
	}
	if resp.StatusCode != http.StatusOK {
		return
	}

	transformResponseBody(resp, func(body []byte) []byte {
		// Don't inject if the script has already been injected.
		if bytes.Contains(body, si.script) {
			log.Printf("ScriptInjector(%s): already injected", resp.Request.URL)
			return body
		}

		// Find an appropriate place to inject the script, then inject.
		idx := headRE.FindIndex(body)
		if idx == nil {
			idx = htmlRE.FindIndex(body)
		}
		if idx == nil {
			idx = doctypeRE.FindIndex(body)
		}
		if idx == nil {
			log.Printf(
				"ScriptInjector(%s): no start tags found, skip injecting script",
				resp.Request.URL)
			return body
		}
		n := idx[1]

		// If the response has a content-script-policy script src directive that
		// specifies a nonce, add the nonce to the injected script.
		// If a CSP specifies a nonce, only script blocks containing a matching
		// nonce attribute may execute.
		// To open permission for WPR-injected scripts while preserving permission
		// for any page-src scripts containing the nonce, WPR must add the nonce
		// token to injected scripts. Please see http://crbug.com/904534 for a
		// detailed case study.
		nonce := ""
		if directive := getCSPScriptSrcDirectiveFromHeaders(resp.Header);
			directive != "" {
			nonce = getNonceTokenFromCSPHeaderScriptSrc(directive)
		}

		var buffer bytes.Buffer
		buffer.Write(body[:n])
		buffer.Write(si.getScriptWithNonce(nonce))
		buffer.Write(body[n:])

		// Having injected script, transform the response's
		// content-security-policy directive to allow the injected script to
		// execute.
		transformCSPHeader(resp.Header, si.sha256)

		log.Printf("ScriptInjector(%s): succesfully injected", resp.Request.URL)
		return buffer.Bytes()
	})
}

// NewRuleBasedTransformer creates a transformer that is controlled by a rules
// file.
// Rules are specified as a JSON-encoded array of TransformerRule objects.
func NewRuleBasedTransformer(filename string) (ResponseTransformer, error) {
	raw, err := ioutil.ReadFile(filename)
	if err != nil {
		return nil, err
	}
	var rules []*TransformerRule
	if err := json.Unmarshal(raw, &rules); err != nil {
		return nil, fmt.Errorf("json unmarshal failed: %v", err)
	}
	rulesDir := filepath.Dir(filename)
	for _, r := range rules {
		// Ensure relative paths are relative to the directory containing the
		// rules file, not the one where the binary got executed. This normalization
		// must happen before compile(), as that consumes the path.
		if r.InjectedScript != "" && !filepath.IsAbs(r.InjectedScript) {
			r.InjectedScript = filepath.Join(rulesDir, r.InjectedScript)
		}

		if err := r.compile(); err != nil {
			return nil, err
		}
	}
	return &ruleBasedTransformer{rules}, nil
}

// TransformerRule is a single JSON-encoded rule. Each rule matches either a
// specific URL (via URL) or a regexp pattern (via URLPattern).
type TransformerRule struct {
	// How to match URLs: exactly one of URL and URLPattern must be specified.
	URL        string
	URLPattern string

	// Rules to apply to these URLs.
	// Inject these extra headers into the response
	ExtraHeaders http.Header
	// Inject these HTTP/2 PUSH_PROMISE frames into the response
	Push []PushPromiseRule

	// Path to a script to inject in the response.
	InjectedScript string

	// Hidden state generated by compile. These are never used by json.Unmarshal()
	// nor json.Marshal(). They are computed early to raise failures early (ahead
	// of Transform() in the case of `scriptInjector`).
	urlRE *regexp.Regexp
	scriptInjector ResponseTransformer
}

// PushPromiseRule is a rule that adds pushes into the response stream.
type PushPromiseRule struct {
	// URL to push.
	URL string

	// Header for the request being simulated by this push. If empty, a default
	// set of headers are created by cloning the current request's headers and
	// setting
	// "referer" to the URL of the current (pusher) request.
	Headers http.Header
}

type ruleBasedTransformer struct {
	rules []*TransformerRule
}

func (r *TransformerRule) compile() error {
	raw, _ := json.Marshal(r)
	if r.URL == "" && r.URLPattern == "" {
		return fmt.Errorf("rule missing URL or URLPattern: %q", raw)
	}
	if r.URL != "" && r.URLPattern != "" {
		return fmt.Errorf("rule has both URL and URLPattern: %q", raw)
	}
	if r.URLPattern != "" {
		re, err := regexp.Compile(r.URLPattern)
		if err != nil {
			return fmt.Errorf("error compiling URLPattern %s: %v", r.URLPattern, err)
		}
		r.urlRE = re
	}
	if r.InjectedScript != "" {
		scriptInjector, err := NewScriptInjectorFromFile(r.InjectedScript,  make(map[string]string))
		if err != nil {
			return err
		}
		r.scriptInjector = scriptInjector
	}
	if len(r.ExtraHeaders) == 0 && len(r.Push) == 0 && len(r.InjectedScript) == 0 {
		return fmt.Errorf("rule has no effect: %q", raw)
	}
	for _, p := range r.Push {
		if p.URL == "" {
			return fmt.Errorf("push has empty URL: %q", raw)
		}
		if u, err := url.Parse(p.URL); err != nil || !u.IsAbs() ||
			(u.Scheme != "http" && u.Scheme != "https") {
			return fmt.Errorf("push has bad URL %s: %v", p.URL, err)
		}
	}
	return nil
}

func (r *TransformerRule) matches(req *http.Request) bool {
	if r.URL != "" {
		return r.URL == req.URL.String()
	}
	return r.urlRE.MatchString(req.URL.String())
}

func (r *TransformerRule) shortString() string {
	pushes := ""
	for _, p := range r.Push {
		pushes += p.URL + " "
	}
	return fmt.Sprintf("ExtraHeaders: %d; Push: [%s]", len(r.ExtraHeaders),
		pushes)
}

func (rt *ruleBasedTransformer) Transform(
	req *http.Request, resp *http.Response) {
	for _, r := range rt.rules {
		if !r.matches(req) {
			continue
		}
		log.Printf("Rule(%s): matched rule %v", req.URL, r.shortString())
		for k, v := range r.ExtraHeaders {
			resp.Header[k] = append(resp.Header[k], v...)
		}

		if r.scriptInjector != nil {
			r.scriptInjector.Transform(req, resp)
		}
		/*
			if disabled {
				for _, p := range r.Push {
					h := p.Headers
					if len(h) == 0 {
						h = cloneHeaders(req.Header)
						h.Set("Referer", req.URL.String())
					}
					rw.Push(p.URL, h)
				}
			}
		*/
	}
}
