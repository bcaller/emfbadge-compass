# Compass example (not finished)
# Copyright (c) 2016 Renze Nicolai & Ben Caller

# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
# documentation files (the "Software"), to deal in the Software without restriction, including without limitation the
# rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit
# persons to whom the Software is furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all copies or substantial portions of the
# Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE
# WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
# COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
# OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import math
import pyb
import ustruct
from database import *

from imu import *

# Default value: 0x00
# [7] DRDY_ON_INT1:Manage the DRDY signal on INT1 pad. Default: 0
# [6] DATA_VALID_SEL_FIFO: Selection of FIFO data-valid signal. Default value: 0
# [5] This bit must be set to 0 for the correct operation of the device
# [4] START_CONFIG: Sensor Hub trigger signal selection. Default value: 0
# [3] PULL_UP_EN: Auxiliary I2C pull-up. Default value: 0
# [2] PASS_THROUGH_MODE: I2C interface pass-through. Default value: 0
# [1] IRON_EN:Enable soft iron correction algorithm for magnetometer. Default value: 0.
# [0] MASTER_ON: Sensor Hub I2C master enable. Default: 0
IMU_MASTER_CONFIG_REG = 0x1A

# IMU_CTRL9_XL = 0x18
# IMU_CTRL10_C = 0x19

COMPASS_ADDRESS = 0x1E
COMPASS_REG_WHO_AM_I = 0x0F
COMPASS_REG_CTRL1 = 0x20
COMPASS_REG_CTRL3 = 0x22
COMPASS_REG_DATA = 0x28

DATABASE_KEY_HARD = "compass-correction-hard"
DATABASE_KEY_SOFT = "compass-correction-soft"
DEFAULT_CALIBRATION = [163, 1584, -7742]


class CompassIMU(IMU):
    """
    Extended IMU class with compass
    """
    def __init__(self, auto_init_compass=True):
        super().__init__()
        self._hard_correction_vector = database_get(DATABASE_KEY_HARD, DEFAULT_CALIBRATION)
        self._soft_correction_vector = database_get(DATABASE_KEY_SOFT, [1, 1, 1])
        if auto_init_compass:
            self.init_compass()

    def _enable_passthrough(self):
        def write(val):
            self.i2c.mem_write(val, IMU_ADDRESS, IMU_MASTER_CONFIG_REG)

        master_config = self.i2c.mem_read(1, IMU_ADDRESS, IMU_MASTER_CONFIG_REG)[0]
        master_config |= 0x10  # set start_config (disable sensor hub trigger)
        write(master_config)
        pyb.delay(10)  # wait at least 5ms
        master_config &= 0xFE  # unset master_on (disable embedded sensor hub)
        write(master_config)
        master_config &= 0xEF  # unset start_config (restore sensor hub trigger)
        write(master_config)
        master_config &= 0xF7  # unset pull_up_en (disable built-in pullup)
        write(master_config)
        master_config |= 0x04  # set pass_through_mode (enable pass-through)
        write(master_config)

    def _correct_hard_iron(self, *args):
        # Remove interference due to components on chip e.g. buzzer
        # Calibration is required to get correction vector
        return map(sum, zip(args, self._hard_correction_vector))

    def _correct_soft_iron(self, *args):
        # Remove interference due to components on chip e.g. buzzer
        # Calibration is required to get correction vector
        return map(lambda a: a[0] * a[1], zip(args, self._soft_correction_vector))

    def init_compass(self):
        self._enable_passthrough()
        self._wait_for_address_ready(COMPASS_ADDRESS)
        if self.i2c.mem_read(1, COMPASS_ADDRESS, COMPASS_REG_WHO_AM_I)[0] != 0x3D:
            raise OSError("COMPASS self check failed")

        ctrl_reg3 = 0
        self.i2c.mem_write(ctrl_reg3, COMPASS_ADDRESS, COMPASS_REG_CTRL3)
        pyb.delay(10)

    def set_compass_data_rate(self, speed=4):
        """
        Actual data rate will be 0.625 * 2 ^ speed Hz
        0.625 Hz, 1.25 Hz, etc
        Max speed is 7 for 80 Hz
        Higher data rates possible with FAST_ODR
        :param speed: number 1-7 for between 0.625 and 80 Hz
        """
        assert 0 <= speed < 8
        speed <<= 2
        ctrl_1 = self.i2c.mem_read(1, COMPASS_ADDRESS, COMPASS_REG_CTRL1)[0]
        self.i2c.mem_write((ctrl_1 | speed) & (0b11100011 | speed), COMPASS_ADDRESS, COMPASS_REG_CTRL1)

    def get_compass_data_rate(self):
        """
        :return: data rate in Hz
        """
        ctrl_1 = self.i2c.mem_read(1, COMPASS_ADDRESS, COMPASS_REG_CTRL1)[0]
        speed = (ctrl_1 & 0b00011100) >> 2
        return (1 << speed) * 0.625

    @staticmethod
    def _make_dict(x, y, z, t=None):
        d = {
            'x': x,
            'y': y,
            'z': z
        }
        if t is not None:
            d['temperature'] = t
        return d

    def _wait_for_address_ready(self, address, max_retries=100, delay=10):
        for i in range(max_retries + 1):
            if self.i2c.is_ready(address):
                return
            pyb.delay(delay)
        raise OSError("Can't connect to I2C " + hex(address))

    def get_acceleration(self):
        data = self.i2c.mem_read(6, IMU_ADDRESS, IMU_REG_ACCEL_DATA)
        return self._make_dict(*map(lambda c: 6.1E-5 * self.accuracy * c, ustruct.unpack_from("3h", data)))

    def get_compass_heading(self):
        """
        Compass heading in degrees after correction
        :return:
        """
        x, y, z, t = self._compass_data()
        print(x, y, z)
        angle = 360 - math.atan2(x, y) * (180 / math.pi)
        return angle

    def _compass_data(self, correct_iron=True):
        data = self.i2c.mem_read(8, COMPASS_ADDRESS, COMPASS_REG_DATA)
        x, y, z, t = ustruct.unpack_from("4h", data)
        if correct_iron:
            x, y, z = self._correct_soft_iron(*self._correct_hard_iron(x, y, z))
        return x, y, z, t

    def get_magnetometer_reading(self):
        """
        :return: dict of x, y, z and temperature (corrected)
        """
        return self._make_dict(*self._compass_data())

    def calibrate(self, samples=700):
        """
        Measures the device's hard-iron interference - a constant magnetic field vector
        Get many samples on a sphere. Then calibrate to the origin of the sphere.
        Really the LSM6DS3 should be capable of doing this for us and of dealing with soft iron correction as well.
        Maybe somebody can figure the sensor hub out.
        :param samples: Number of compass readings to use for calibration
        """
        self._hard_correction_vector = [0, 0, 0]
        self._soft_correction_vector = [1, 1, 1]
        delay_between_samples = int(1000 / self.get_compass_data_rate() * 1.1)
        min_coords, max_coords = [0, 0, 0], [0, 0, 0]
        for i in range(samples):
            data = self._compass_data(correct_iron=False)
            for j in range(3):
                min_coords[j], max_coords[j] = min(min_coords[j], data[j]), max(max_coords[j], data[j])
            pyb.delay(delay_between_samples)
        avg_diff = (sum(max_coords) - sum(min_coords)) / 3
        for j in range(3):
            self._hard_correction_vector[j] = -int((max_coords[j] + min_coords[j]) / 2)
            self._soft_correction_vector[j] = avg_diff / (max_coords[j] - min_coords[j])
        database_set(DATABASE_KEY_HARD, self._hard_correction_vector)
        database_set(DATABASE_KEY_SOFT, self._soft_correction_vector)

    def is_calibrated(self):
        return self._hard_correction_vector != DEFAULT_CALIBRATION
