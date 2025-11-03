// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package webpagereplay

import (
	"crypto"
	"crypto/rand"
	"crypto/tls"
	"crypto/x509"
	"crypto/x509/pkix"
	"fmt"
	"net"
	"sync"
	"time"
)

// Returns a TLS configuration that serves a recorded server leaf cert signed by
// root CA.
func ReplayTLSConfig(roots []tls.Certificate, a *Archive, useArchiveCertificates bool) (*tls.Config, error) {
	root_certs, err := getRootCerts(roots)
	if err != nil {
		return nil, fmt.Errorf("bad local certs: %v", err)
	}
	tp := &tlsProxy{roots, root_certs, a, nil, sync.Mutex{}, make(map[string][]byte), useArchiveCertificates}
	return &tls.Config{
		GetConfigForClient: tp.getReplayConfigForClient,
	}, nil
}

// Returns a TLS configuration that serves a server leaf cert fetched over the
// network on demand.
func RecordTLSConfig(roots []tls.Certificate, w *WritableArchive, useArchiveCertificates bool) (*tls.Config, error) {
	root_certs, err := getRootCerts(roots)
	if err != nil {
		return nil, fmt.Errorf("bad local certs: %v", err)
	}
	tp := &tlsProxy{roots, root_certs, nil, w, sync.Mutex{}, nil, useArchiveCertificates}
	return &tls.Config{
		GetConfigForClient: tp.getRecordConfigForClient,
	}, nil
}

func getRootCerts(roots []tls.Certificate) ([]*x509.Certificate, error) {
	root_certs := []*x509.Certificate{}
	for _, root := range roots {
		root_cert, err := x509.ParseCertificate(root.Certificate[0])
		if err != nil {
			return nil, err
		}
		root_cert.IsCA = true
		root_cert.BasicConstraintsValid = true
		root_certs = append(root_certs, root_cert)
	}
	return root_certs, nil
}

// Returns DER encoded server cert.
func MintCertificate(serverName string, rootCert *x509.Certificate, rootKey crypto.PrivateKey) ([]byte, error) {
	// Slightly before now, in case clocks are off.
	notBefore := time.Now().Add(-24 * time.Hour)
	template := x509.Certificate{
		Issuer: rootCert.Subject,
		Subject: pkix.Name{
			CommonName: serverName,
		},
		KeyUsage:    x509.KeyUsageKeyEncipherment | x509.KeyUsageDigitalSignature,
		ExtKeyUsage: []x509.ExtKeyUsage{x509.ExtKeyUsageServerAuth},
		NotBefore:   notBefore,
		// Certificates cannot be valid for more than ~1 year in most platforms.
		NotAfter: notBefore.Add(12 * 30 * 24 * time.Hour),
	}
	if ip := net.ParseIP(serverName); ip != nil {
		template.IPAddresses = []net.IP{ip}
	} else {
		template.DNSNames = []string{serverName}
	}
	derBytes, err := x509.CreateCertificate(rand.Reader, &template, rootCert, rootCert.PublicKey, rootKey)
	if err != nil {
		return nil, fmt.Errorf("create cert failed: %v", err)
	}
	return derBytes, err
}

func TryNegotiateWPRSupportedProtocol(serverName string) (string, error) {
	dialer := &net.Dialer{
		Timeout:   30 * time.Second,
		KeepAlive: 30 * time.Second,
		DualStack: true,
	}
	conn, err := tls.DialWithDialer(dialer, "tcp", fmt.Sprintf("%s:443", serverName), &tls.Config{
		NextProtos:         []string{"h2", "http/1.1"},
		InsecureSkipVerify: true,
	})
	if err != nil {
		return "", fmt.Errorf("Couldn't reach host %s: %v", serverName, err)
	}
	defer conn.Close()
	conn.Handshake()
	// From go docs: "if the peer doesn't support ALPN, the connection will
	// succeed and ConnectionState.NegotiatedProtocol will be empty". In that
	// case, the connection will be http/1.1.
	return conn.ConnectionState().NegotiatedProtocol, nil
}

type tlsProxy struct {
	roots                    []tls.Certificate
	root_certs               []*x509.Certificate
	archive                  *Archive
	writable_archive         *WritableArchive
	mu                       sync.Mutex
	dummy_certs_map          map[string][]byte
	use_archive_certificates bool
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
			Certificates: tp.roots,
		}, nil
	}

	negotiatedProtocol, err := tp.archive.FindHostNegotiatedProtocol(h)
	if err != nil {
		// This code predates me, it seems dangerous. My understanding is sending
		// a stored HTTP2 response to a client via HTTP1 won't work. Might be better
		// to panic, or better yet, derive the protocol from the stored requests.
		negotiatedProtocol = ""
	}

	derBytes, err := tp.archive.FindHostCertificate(h)
	tp.mu.Lock()
	defer tp.mu.Unlock()
	if err != nil || derBytes == nil || !tp.use_archive_certificates {
		if _, ok := tp.dummy_certs_map[h]; !ok {
			for i := 0; i < len(tp.root_certs); i++ {
				derBytes, err = MintCertificate(h, tp.root_certs[i], tp.roots[i].PrivateKey)
				if err != nil {
					return nil, err
				}
				tp.dummy_certs_map[h] = append(tp.dummy_certs_map[h], derBytes...)
			}
		}
		derBytes = tp.dummy_certs_map[h]
	}

	certBytes := parseDerBytes(derBytes)

	certificates := []tls.Certificate{}
	for i := 0; i < len(certBytes); i++ {
		certificates = append(certificates, tls.Certificate{
			Certificate: [][]byte{certBytes[i]},
			PrivateKey:  tp.roots[i].PrivateKey,
		})
	}
	return &tls.Config{
		Certificates: certificates,
		NextProtos:   buildNextProtos(negotiatedProtocol),
	}, nil
}

// This code predates me, it seems dangerous. My understanding is that sending a
// stored response with the wrong protocol won't work. Sending
// {negotiatedProtocol} as nextProtos might be best.
func buildNextProtos(negotiatedProtocol string) []string {
	if negotiatedProtocol == "h2" {
		return []string{"h2", "http/1.1"}
	}
	return []string{"http/1.1"}
}

// Extract ASN.1 DER encoded certificates from byte array.
// ASN.1 DER encoding is a tag, length, value encoding system for each element.
// Depending on the length of the certificate, there are three possible sequence starts:
//  1. 0x30, one byte of length field
//  2. 0x30, 0x81, one byte of length field
//  3. 0x30, 0x82, two bytes of length field
func parseDerBytes(derBytes []byte) [][]byte {
	var certBytes [][]byte
	for i := 0; i < len(derBytes); {
		certEndIndex := 0
		switch derBytes[i+1] {
		case 0x81:
			certEndIndex = i + 3 + int(derBytes[i+2])
		case 0x82:
			certEndIndex = i + 4 + int(derBytes[i+2])*256 + int(derBytes[i+3])
		default:
			certEndIndex = i + 2 + int(derBytes[i+1])
		}
		certBytes = append(certBytes, derBytes[i:certEndIndex])
		i = certEndIndex
	}
	return certBytes
}

func (tp *tlsProxy) getRecordConfigForClient(clientHello *tls.ClientHelloInfo) (*tls.Config, error) {
	h := clientHello.ServerName
	if h == "" {
		return &tls.Config{
			Certificates: tp.roots,
		}, nil
	}

	negotiatedProtocol, err := tp.writable_archive.Archive.FindHostNegotiatedProtocol(h)
	if err != nil {
		negotiatedProtocol, err = TryNegotiateWPRSupportedProtocol(h)
	}
	if err != nil {
		return nil, fmt.Errorf("failed to negotiate supported http protocol: %v", err)
	}

	certificates := []tls.Certificate{}
	derBytes, err := tp.writable_archive.Archive.FindHostCertificate(h)
	if err == nil && derBytes != nil && tp.use_archive_certificates {
		certBytes := parseDerBytes(derBytes)
		for i := 0; i < len(certBytes); i++ {
			certificates = append(certificates, tls.Certificate{
				Certificate: [][]byte{certBytes[i]},
				PrivateKey:  tp.roots[i].PrivateKey,
			})
		}
		return &tls.Config{
			Certificates: certificates,
			NextProtos:   buildNextProtos(negotiatedProtocol),
		}, nil
	}

	totalDerBytes := []byte{}
	for i := 0; i < len(tp.roots); i++ {
		derBytes, err = MintCertificate(h, tp.root_certs[i], tp.roots[i].PrivateKey)
		if err != nil {
			return nil, fmt.Errorf("create cert failed: %v", err)
		}
		certificates = append(certificates, tls.Certificate{
			Certificate: [][]byte{derBytes},
			PrivateKey:  tp.roots[i].PrivateKey})
		totalDerBytes = append(totalDerBytes, derBytes...)
	}
	if tp.use_archive_certificates {
		tp.writable_archive.RecordHostCertificate(h, totalDerBytes)
	}
	tp.writable_archive.RecordHostNegotiatedProtocol(h, negotiatedProtocol)

	return &tls.Config{
		Certificates: certificates,
		NextProtos:   buildNextProtos(negotiatedProtocol),
	}, nil
}
