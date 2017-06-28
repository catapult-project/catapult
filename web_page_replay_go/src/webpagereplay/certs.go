// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package webpagereplay

import (
	"crypto/rand"
	"crypto/tls"
	"crypto/x509"
	"fmt"
	"io"
	"time"
)

// Returns a TLS configuration that serves a recorded server leaf cert signed by
// root CA.
func ReplayTLSConfig(root tls.Certificate, a *Archive) (*tls.Config, error) {
	root_cert, err := getRootCert(root)
	if err != nil {
		return nil, fmt.Errorf("bad local cert: %v", err)
	}
	tp := &tlsProxy{&root, root_cert, a, nil}
	return &tls.Config{
		GetConfigForClient: tp.getReplayConfigForClient,
	}, nil
}

// Returns a TLS configuration that serves a server leaf cert fetched over the
// network on demand.
func RecordTLSConfig(root tls.Certificate, w *WritableArchive) (*tls.Config, error) {
	root_cert, err := getRootCert(root)
	if err != nil {
		return nil, fmt.Errorf("bad local cert: %v", err)
	}
	tp := &tlsProxy{&root, root_cert, nil, w}
	return &tls.Config{
		GetConfigForClient: tp.getRecordConfigForClient,
	}, nil
}

func getRootCert(root tls.Certificate) (*x509.Certificate, error) {
	root_cert, err := x509.ParseCertificate(root.Certificate[0])
	if err != nil {
		return nil, err
	}
	root_cert.IsCA = true
	root_cert.BasicConstraintsValid = true
	return root_cert, nil
}

type tlsProxy struct {
	root             *tls.Certificate
	root_cert        *x509.Certificate
	archive          *Archive
	writable_archive *WritableArchive
}

// TODO: For now, this just returns a self-signed cert using the given ServerName.
// In the future, for better HTTP/2 support, we may want to record host equivalence
// classes in the archive, where an equivalence class contains all hosts that can be
// served by the same IP. We can then run a DNS proxy that maps all hostnames in the
// same equivalence class to the same local port, which models the possibility that
// every equivalence class of hostnames can be served over the same HTTP/2 connection.
func (tp *tlsProxy) getReplayConfigForClient(clientHello *tls.ClientHelloInfo) (*tls.Config, error) {
	h := clientHello.ServerName
	if h == "" {
		return &tls.Config{
			Certificates: []tls.Certificate{*tp.root},
		}, nil
	}

	der_bytes, negotiatedProtocol, err := tp.archive.FindHostTlsConfig(h)
	if err != nil || der_bytes == nil {
		return nil, fmt.Errorf("No archived cert for %s", h)
	}
	return &tls.Config{
		Certificates: []tls.Certificate{
			tls.Certificate{
				Certificate: [][]byte{der_bytes},
				PrivateKey:  tp.root.PrivateKey,
			}},
		NextProtos: []string{negotiatedProtocol},
	}, nil
}

func (tp *tlsProxy) getRecordConfigForClient(clientHello *tls.ClientHelloInfo) (*tls.Config, error) {
	h := clientHello.ServerName
	if h == "" {
		return &tls.Config{
			Certificates: []tls.Certificate{*tp.root},
		}, nil
	}
	der_bytes, negotiatedProtocol, err := tp.writable_archive.Archive.FindHostTlsConfig(h)
	if err == nil && der_bytes != nil {
		return &tls.Config{
			Certificates: []tls.Certificate{
				tls.Certificate{
					Certificate: [][]byte{der_bytes},
					PrivateKey:  tp.root.PrivateKey,
				}},
			NextProtos: []string{negotiatedProtocol},
		}, nil
	}

	conn, err := tls.Dial("tcp", fmt.Sprintf("%s:443", h), &tls.Config{
		NextProtos: []string{"h2", "http/1.1"},
	})
	if err != nil {
		return nil, fmt.Errorf("Couldn't reach host %s: %v", h, err)
	}
	defer conn.Close()
	conn.Handshake()
	template := conn.ConnectionState().PeerCertificates[0]

	template.Subject.CommonName = h
	template.NotBefore = time.Now()
	template.NotAfter = template.NotBefore.Add(87658 * time.Hour)
	template.PublicKey = tp.root_cert.PublicKey
	var buf [20]byte
	if _, err := io.ReadFull(rand.Reader, buf[:]); err != nil {
		return nil, err
	}
	template.SerialNumber.SetBytes(buf[:])
	template.Issuer = tp.root_cert.Subject
	template.KeyUsage = x509.KeyUsageCertSign | x509.KeyUsageKeyEncipherment | x509.KeyUsageDigitalSignature | x509.KeyUsageCRLSign
	template.ExtKeyUsage = []x509.ExtKeyUsage{x509.ExtKeyUsageClientAuth, x509.ExtKeyUsageServerAuth}

	der_bytes, err = x509.CreateCertificate(rand.Reader, template, tp.root_cert, template.PublicKey, tp.root.PrivateKey)
	if err != nil {
		return nil, fmt.Errorf("create cert failed: %v", err)
	}

	negotiatedProtocol = conn.ConnectionState().NegotiatedProtocol
	tp.writable_archive.RecordTlsConfig(h, der_bytes, negotiatedProtocol)

	return &tls.Config{
		Certificates: []tls.Certificate{
			tls.Certificate{
				Certificate: [][]byte{der_bytes},
				PrivateKey:  tp.root.PrivateKey}},
		NextProtos: []string{negotiatedProtocol},
	}, nil
}
