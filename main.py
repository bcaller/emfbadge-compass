# Author: Ben Caller
# Description: A compass on your badge.
# License: MIT
# Copyright (c) 2016 Ben Caller.
# Would have been impossible without parts of compass.py Copyright Renze Nicolai


import ugfx, pyb, buttons, math
execfile('apps/bcaller~compass/compass.py')  # I'dve preferred an import, but __import__ ran out of memory

FRICTION = 0.3
COLOR = ugfx.html_color(0xFF7C11)


def calib(display, imu):
    display.area(0, 0, display.width(), display.height(), ugfx.BLACK)
    ugfx.text(5, ugfx.height() - 70, "Calibrating... slowly move & rotate", ugfx.RED)
    ugfx.text(5, ugfx.height() - 45, "Wave in figure-of-8s & upside-down", ugfx.RED)
    imu.calibrate()
    ugfx.area(0, ugfx.height() - 70, ugfx.width(), 70, ugfx.BLACK)


def polar_to_cartesian(theta, r):
    return int(r * math.cos(theta / 60)), int(r * math.sin(theta / 60))


def draw_compass(angle, container):
    container.area(0, 0, container.width(), container.height(), ugfx.BLACK)
    midx, midy = container.width() // 2, container.height() // 2
    radii = [midx - 35, midx - 18, midx - 7]
    container.circle(midx, midy, radii[0], ugfx.GRAY)
    draw_x, draw_y = polar_to_cartesian(angle, radii[1])
    shrink = 7
    container.fill_circle(midx, midy, radii[1] // shrink + 2, COLOR)
    container.fill_polygon(midx, midy, [[draw_y // shrink, -draw_x // shrink], [draw_x, draw_y],
                                        [-draw_y // shrink, draw_x // shrink]], COLOR)
    draw_x, draw_y = polar_to_cartesian(angle, radii[2])
    container.text(midx + draw_x - 2, midy + draw_y - 5, "N", COLOR)
    container.text(midx - draw_x - 2, midy - draw_y - 5, "S", ugfx.GRAY)
    container.text(midx - draw_y - 2, midy + draw_x - 5, "E", ugfx.GRAY)
    container.text(midx + draw_y - 2, midy - draw_x - 5, "W", ugfx.GRAY)


ugfx.init()
ugfx.clear(ugfx.BLACK)
ugfx.set_default_font(ugfx.FONT_TITLE)
ugfx.set_default_font(ugfx.FONT_SMALL)
ugfx.text(ugfx.width() - 40, ugfx.height() - 30, "(B) to", COLOR)
ugfx.text(ugfx.width() - 40, ugfx.height() - 15, "calib.", COLOR)
display = ugfx.Container(ugfx.width() // 2 - ugfx.height() // 2, 0, ugfx.height(), ugfx.height())
display.show()
ugfx.set_default_font(ugfx.FONT_MEDIUM)
magnet = CompassIMU()
magnet.set_compass_data_rate(5)
last_angle = None
while True:
    ugfx.area(2, ugfx.height() - 30, 30, 30, ugfx.BLACK)
    if buttons.is_triggered("BTN_B"):
        calib(display, magnet)

    angle = (magnet.get_compass_heading() + 360) % 360
    ugfx.text(2, ugfx.height() - 30, str(int(angle + 90) % 360), COLOR)

    if last_angle is None or not -1 < (angle - last_angle) < 1:
        last_angle = angle if last_angle is None else (
            last_angle * FRICTION + angle * (1 - FRICTION))  # stupid animation attempt
        draw_compass(last_angle, display)

    pyb.delay(30)
