import time

import pytest
from i2capi_i2cdriver.i2cdriver_api import I2CMasterI2CDriver
from i2cdriver import I2CDriver
from rgscore import RLink, RLinkI2C, Register, FieldDef, RegSet

i2c_master = I2CMasterI2CDriver(I2CDriver())


@pytest.fixture
def bmp581_address() -> int:
    return 0x47


@pytest.fixture()
def link(bmp581_address: int) -> RLink:
    return RLinkI2C(i2c_master, bmp581_address)


rs = RegSet(RLinkI2C(I2CMasterI2CDriver(I2CDriver()), 0x47))
rs.add(Register(
    bit_len=8, address=0x37, name="ODR_CONFIG",
    model=[
        FieldDef.value_of("deep_dis@[7:7]U1.0"),
        FieldDef.value_of("odr@[6:2]U5.0"),
        FieldDef.value_of("pwr_mode@[1:0]U2.0")
    ]
))
rs.add(Register(bit_len=8, address=0x7E, name="CMD", model=[FieldDef.value_of("cmd@[7:0]U8.0")]))


class TestBMP581:
    def test_read_id_registers(self, bmp581_address: int):
        asic_id_regval = i2c_master.read_register(bmp581_address, 0x01)
        assert asic_id_regval.bin == "01010000"

    def test_odr_register(self, link: RLink):
        odr_register = rs["ODR_CONFIG"]
        odr_register.read()

        # this register should come up with all values reset to default values which are as follows:
        assert odr_register.get_field_value("deep_dis") == 0
        assert odr_register.get_field_value("odr") == 0x1C  # 1Hz frequency for measurements
        assert odr_register.get_field_value("pwr_mode") == 0

        # change frequency for measurements to 0x1F (measure every 1/4 of a second)
        odr_register.set_field_value("odr", 0x1F)
        assert odr_register.get_field_value("odr") == 0x1F  # 0.125Hz frequency for measurements
        # but data is not written out to the device; we will read it now to confirm that it is so
        odr_register.read()
        assert odr_register.get_field_value("odr") == 0x1C  # 1Hz frequency for measurements
        # change it again and now write it to the device
        odr_register.set_field_value("odr", 0x1F)
        odr_register.write()
        odr_register.read()
        assert odr_register.get_field_value("odr") == 0x1F  # 0.125Hz frequency for measurements

        # now issue reset and read back odr_register and confirm that odr value is back to default value
        rs["CMD"].set_field_value("cmd", 0xB6)
        rs["CMD"].write()
        # according to the spec device should be unresponsive for 2ms. So to proceed we will wait 5 millis.
        time.sleep(0.005)
        odr_register.read()
        assert odr_register.get_field_value("odr") == 0x1C  # 1Hz frequency for measurements
