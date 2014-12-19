# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This module provides implementations of common computer Vision operations."""

from __future__ import division
from telemetry.util import external_modules

np = external_modules.ImportRequiredModule('numpy')


def AreLinesOrthogonal(line1, line2, tolerance):
  """Returns true if lines are within tolerance radians of being orthogonal."""
  # Map each line onto an angle between 0 and 180.
  theta1 = np.arctan2(np.float(line1[0][1] - line1[1][1]),
                      np.float(line1[0][0] - line1[1][0]))
  theta2 = np.arctan2(np.float(line2[0][1] - line2[1][1]),
                      np.float(line2[0][0] - line2[1][0]))
  angle2 = abs(theta2 - theta1)
  if angle2 >= np.pi:
    angle2 -= np.pi
  # If the difference between the angles is more than pi/2 - tolerance, the
  # lines are not orthogonal.
  return not abs(angle2 - (np.pi / 2.0)) > tolerance


def FindLineIntersection(line1, line2):
  """If the line segments intersect, returns True and their intersection.
  Otherwise, returns False and the intersection of the line segments if they
  were to be extended."""
  # Compute g, and h, the factor by which each line must be extended to
  # exactly touch the other line. If both are between 0 and 1, then the lines
  # currently intersect. We use h to compute their intersection.
  line1p1 = np.asfarray(line1[1])
  line1p0 = np.asfarray(line1[0])
  line2p1 = np.asfarray(line2[1])
  line2p0 = np.asfarray(line2[0])
  E = np.subtract(line1p1, line1p0)
  F = np.subtract(line2p1, line2p0)
  Pe = np.asfarray((-E[1], E[0]))
  Pf = np.asfarray((-F[1], F[0]))
  h = np.dot(np.subtract(line1p0, line2p0), Pe)
  h = np.divide(h, np.dot(F, Pe))
  g = np.dot(np.subtract(line2p0, line1p0), Pf)
  g = np.divide(g, np.dot(E, Pf))
  intersection = np.add(line2p0, np.dot(F, h))
  if h >= -0.000001 and h <= 1.000001 and g >= -0.000001 and g <= 1.000001:
    return True, (intersection[0], intersection[1])
  return False, (intersection[0], intersection[1])


def ExtendLines(lines, length):
  """Extends lines in an array to a given length, maintaining the center
  point. Does not necessarily maintain point order."""
  extended = []
  half_length = length / 2.0
  for x1, y1, x2, y2 in lines:
    angle = np.arctan2(np.float(y1 - y2), np.float(x1 - x2))
    xoffset = half_length * np.cos(angle)
    yoffset = half_length * np.sin(angle)
    centerx = (x1 + x2) / 2.0
    centery = (y1 + y2) / 2.0
    x1 = centerx - xoffset
    x2 = centerx + xoffset
    y1 = centery - yoffset
    y2 = centery + yoffset
    extended.append(((x1, y1), (x2, y2)))
  return extended


def IsPointApproxOnLine(point, line, tolerance=1):
  """Approximates distance between point and line for small distances using
  the determinant and checks whether it's within the tolerance. Tolerance is
  an approximate distance in pixels, precision decreases with distance."""
  xd = line[0][0] - line[1][0]
  yd = line[0][1] - line[1][1]
  det = (((xd) * (point[1] - line[1][1])) -
         ((yd) * (point[0] - line[1][0])))
  tolerance = float(tolerance) * (abs(xd) + abs(yd))
  return abs(det) * 2.0 <= tolerance


def SqDistance(point1, point2):
  """Computes the square of the distance between two points."""
  x = point1[0] - point2[0]
  y = point1[1] - point2[1]
  return (x * x) + (y * y)
