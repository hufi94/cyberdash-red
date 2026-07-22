#!/usr/bin/env python3
"""Texture and perspective helpers for the Civic floor reflection."""

from dataclasses import dataclass
from math import asin, cos, hypot, pi, pow, sin


@dataclass(frozen=True)
class Point:
    """One point in the source frame or mapped Kivy image area."""

    x: float
    y: float


# Fitted to the visible tyre contacts in the 576x264 Civic sequence. The two
# axes form a ground-plane rectangle which rotates through the same 220 angles
# as the car. Values are in source-frame pixels with y increasing downward.
FLOOR_FRAME_COUNT = 220
FLOOR_CENTER = Point(291.0, 209.0)
LONGITUDINAL_X = 355.0
LONGITUDINAL_DEPTH = 92.0
LATERAL_X = 215.0
LATERAL_DEPTH = 28.0
EDGE_GLOW_THICKNESS = 52.0
GLOW_MAXIMUM_ALPHA = 250
GLOW_FALLOFF_POWER = 1.55


def rotation_phase(frame_index: int, frame_count: int = FLOOR_FRAME_COUNT) -> float:
    return 2.0 * pi * (frame_index % frame_count) / frame_count


def projected_floor_corners(
    frame_index: int,
    frame_count: int = FLOOR_FRAME_COUNT,
) -> tuple[Point, Point, Point, Point]:
    """Project the four rotating underbody corners into the source frame."""

    phase = rotation_phase(frame_index, frame_count)
    long_axis = Point(
        LONGITUDINAL_X * sin(phase),
        LONGITUDINAL_DEPTH * cos(phase),
    )
    wide_axis = Point(
        LATERAL_X * cos(phase),
        -LATERAL_DEPTH * sin(phase),
    )
    center = FLOOR_CENTER
    return (
        Point(
            center.x - long_axis.x / 2.0 - wide_axis.x / 2.0,
            center.y - long_axis.y / 2.0 - wide_axis.y / 2.0,
        ),
        Point(
            center.x + long_axis.x / 2.0 - wide_axis.x / 2.0,
            center.y + long_axis.y / 2.0 - wide_axis.y / 2.0,
        ),
        Point(
            center.x + long_axis.x / 2.0 + wide_axis.x / 2.0,
            center.y + long_axis.y / 2.0 + wide_axis.y / 2.0,
        ),
        Point(
            center.x - long_axis.x / 2.0 + wide_axis.x / 2.0,
            center.y - long_axis.y / 2.0 + wide_axis.y / 2.0,
        ),
    )


def projected_edge_strengths(
    frame_index: int,
    corners: tuple[Point, Point, Point, Point],
    frame_count: int = FLOOR_FRAME_COUNT,
    fade_extension_fraction: float = 0.0,
) -> tuple[float, float, float, float]:
    """Favor the closest sides and extend their angular fade when requested."""

    if fade_extension_fraction < 0:
        raise ValueError("fade_extension_fraction cannot be negative")

    phase = rotation_phase(frame_index, frame_count)
    midpoints_y = [
        (corners[index].y + corners[(index + 1) % 4].y) / 2.0
        for index in range(4)
    ]
    minimum_y = min(midpoints_y)
    maximum_y = max(midpoints_y)
    y_range = max(maximum_y - minimum_y, 1.0)

    # Edges 0 and 2 are the two vehicle sides. Edges 1 and 3 are its front
    # and rear. This makes the glow visibly rotate instead of behaving like a
    # horizontal bar that merely changes width.
    base_facing = (
        abs(sin(phase)),
        abs(cos(phase)),
        abs(sin(phase)),
        abs(cos(phase)),
    )
    # Shift each fade curve outward on both sides. One second of a twelve-
    # second rotation is 1/12 of a turn, making the edge begin brightening one
    # second earlier and remain visible one second later.
    phase_extension = min(
        pi / 2.0,
        2.0 * pi * fade_extension_fraction,
    )
    facing = tuple(
        sin(min(pi / 2.0, asin(amount) + phase_extension))
        for amount in base_facing
    )
    strengths = []
    for index, (midpoint_y, facing_amount) in enumerate(
        zip(midpoints_y, facing)
    ):
        depth = (midpoint_y - minimum_y) / y_range
        if index % 2 == 0:
            depth_amount = 0.25 + 0.75 * pow(depth, 1.6)
        else:
            depth_amount = 0.08 + 0.92 * pow(depth, 2.1)
        strengths.append(facing_amount * depth_amount)
    return tuple(strengths)


def glow_strip_corners(
    start: Point,
    end: Point,
    thickness: float,
) -> tuple[Point, Point, Point, Point]:
    """Return a soft-texture strip around one projected floor-frame edge."""

    delta_x = end.x - start.x
    delta_y = end.y - start.y
    length = hypot(delta_x, delta_y)
    if length == 0:
        return (start, end, end, start)
    half = thickness / 2.0
    normal_x = -delta_y / length * half
    normal_y = delta_x / length * half
    return (
        Point(start.x - normal_x, start.y - normal_y),
        Point(end.x - normal_x, end.y - normal_y),
        Point(end.x + normal_x, end.y + normal_y),
        Point(start.x + normal_x, start.y + normal_y),
    )


def build_floor_glow_rgba(
    width: int = 256,
    height: int = 64,
    maximum_alpha: int = GLOW_MAXIMUM_ALPHA,
    falloff_power: float = GLOW_FALLOFF_POWER,
) -> bytes:
    """Return a soft red ellipse with fully transparent outer edges.

    The texture is generated in memory at startup.  It contains no line or
    hard-edged shape, so scaling it on the small display produces a pool of
    reflected light rather than a separate animated object.
    """

    if width < 3 or height < 3:
        raise ValueError("floor glow texture must be at least 3 by 3 pixels")
    if not 0 <= maximum_alpha <= 255:
        raise ValueError("maximum_alpha must be between 0 and 255")
    if falloff_power <= 0:
        raise ValueError("falloff_power must be greater than zero")

    center_x = (width - 1) / 2.0
    center_y = (height - 1) * 0.56
    radius_x = center_x
    radius_y_below = center_y
    radius_y_above = (height - 1) - center_y
    pixels = bytearray(width * height * 4)

    offset = 0
    for y in range(height):
        radius_y = radius_y_below if y <= center_y else radius_y_above
        normalized_y = (y - center_y) / max(radius_y, 1.0)

        for x in range(width):
            normalized_x = (x - center_x) / radius_x
            radius_squared = (
                normalized_x * normalized_x
                + normalized_y * normalized_y
            )

            alpha = 0
            if radius_squared < 1.0:
                # The broad falloff keeps the outer edge invisible while
                # spreading a much stronger neon reflection beneath the car.
                falloff = pow(1.0 - radius_squared, falloff_power)
                alpha = round(maximum_alpha * falloff)

            pixels[offset : offset + 4] = (255, 8, 18, alpha)
            offset += 4

    return bytes(pixels)
