from typing import Optional

import pytest
from bitstring import BitArray
from rgscore.model.register import Register, FieldDef, RLink


class MemLink(RLink):
    def __init__(self):
        self.store = {0x9: BitArray("uint:16=7"), 0xA: BitArray("uint:8=3")}

    def read(self, addr: int, width: int) -> Optional[BitArray]:
        raw_register = self.store.get(addr)
        return None if raw_register is None else raw_register.copy()

    def write(self, addr: int, value: BitArray) -> bool:
        if addr in self.store:
            self.store[addr] = value.copy()
            return True
        else:
            return False


def test_bare_register_valid():
    # create 7 bits wide register with no explicit fields defined, no name and no address.
    r = Register(7)
    assert r.width == 7
    assert r.name is None
    assert r.address is None

    # implicit field named "val" is created occupying the whole of the register of type U{r.width}.0
    assert r.get_field_names() == ["val"]
    assert r.get_field_definition("val") == FieldDef(name="val", offset=0, signed="U", width=7, fractional=0, rw=True)


def test_bare_register_invalid():
    # register with must be greater than 0
    with pytest.raises(ValueError):
        Register(0)

    with pytest.raises(ValueError):
        Register(-4)


def test_register_with_name():
    r = Register(7, name="Foo1")
    assert r.name == "Foo1"

    # check that error is raised if name is invalid
    with pytest.raises(ValueError):
        Register(7, name="Foo X")

    with pytest.raises(ValueError):
        Register(7, name="1")


def test_register_with_address():
    r = Register(7, address=0x42)
    assert r.address == 0x42


def test_register_with_valid_fields():
    # define register with just one r/o field.
    r = Register(7, address=0x42, name="AReg", model=[FieldDef.value_of("a@[3:0]U4.1#ro")])
    assert r.get_field_names() == ["a"]


def test_register_with_invalid_fields():
    # field width is larger than register width
    with pytest.raises(ValueError):
        Register(7, address=0x42, name="AReg", model=[FieldDef.value_of("a@[7:0]U8.1")])

    # fields overlap
    with pytest.raises(ValueError):
        Register(
            bit_len=7, address=0x42, name="AReg",
            model=[FieldDef.value_of("a@[6:0]U7.1"), FieldDef.value_of("b@[3:2]S2.0")]
        )

    # fields names not unique
    with pytest.raises(ValueError):
        Register(
            bit_len=7, address=0x42, name="AReg",
            model=[FieldDef.value_of("a@[3:0]U4.1"), FieldDef.value_of("a@[6:4]S3.0")]
        )


def test_register_access():
    r = Register(
        bit_len=7, address=0x42, name="AReg",
        model=[FieldDef.value_of("a@[3:0]U4.1#ro"), FieldDef.value_of("b@[6:4]S3.0")]
    )
    assert r.get_field_names() == ["a", "b"]
    assert r.get_field_values() == {"a": 0.0, "b": 0.0}
    assert r.get_field_value("a") == 0.0

    # error on non-existent field
    with pytest.raises(ValueError):
        r.get_field_value("x")

    # error on non-existent field
    with pytest.raises(ValueError):
        r.set_field_value("x", 1)

    r.set_field_value("b", 3)
    assert r.get_field_values() == {"a": 0.0, "b": 3.0}
    assert r.get_field_value("a") == 0.0
    assert r.get_field_value("b") == 3.0
    assert r.data.bin == "0110000"

    # error when trying to change r/o field
    with pytest.raises(ValueError):
        r.set_field_value("a", 1)

    # error when trying to set value outside valid range
    with pytest.raises(ValueError):
        r.set_field_value("b", 10)
    assert r.get_field_value("b") == 3.0

    # error when trying to set value outside valid range
    with pytest.raises(ValueError):
        r.set_field_value("b", -10)
    assert r.get_field_value("b") == 3.0

    r.set_field_value("b", -1)
    assert r.get_field_value("b") == -1.0

    # let us change field "a" to be r/w and check field valid range which is from 0 to +7.5 inclusive
    r = Register(
        bit_len=7, address=0x42, name="AReg",
        model=[FieldDef.value_of("a@[3:0]U4.1"), FieldDef.value_of("b@[6:4]S3.0")]
    )

    r.set_field_value("a", 7.5)
    assert r.get_field_value("a") == 7.5

    r.set_field_value("a", 0)
    assert r.get_field_value("a") == 0.0

    # setting outside of valid range should fail
    with pytest.raises(ValueError):
        r.set_field_value("a", -0.1)

    with pytest.raises(ValueError):
        r.set_field_value("a", 7.5001)


def test_field_def():
    # fully written out valid field definition
    fd = FieldDef.value_of("a@[10:3]U8.3#ro")
    assert fd.name == "a"
    assert fd.width == 8
    assert fd.offset == 3
    assert fd.signed == "U"
    assert fd.fractional == 3
    assert fd.rw == False

    # omitting rw flag implies "rw"
    fd = FieldDef.value_of("a@[10:3]U8.3")
    assert fd.name == "a"
    assert fd.width == 8
    assert fd.offset == 3
    assert fd.signed == "U"
    assert fd.fractional == 3
    assert fd.rw == True

    # field with width of 1 bit can be written as [offset] or [offset:offset]
    fd = FieldDef.value_of("a@[5:5]U1.0")
    assert fd.offset == 5
    assert fd.width == 1

    fd = FieldDef.value_of("a@[5]U1.0")
    assert fd.offset == 5
    assert fd.width == 1

    # field range [10:3] is of width 8 bits while numeric type is declared as unsigned 3 bits wide int. This is
    # iternally inconsistent and should give rise to ValueError
    with pytest.raises(ValueError):
        FieldDef.value_of("a@[10:3]U3.0")

    # check for various invalid/incomplete field definitions
    with pytest.raises(ValueError):  # missing field name
        FieldDef.value_of("@[10:3]U3.1")

    with pytest.raises(ValueError):  # missing numeric name
        FieldDef.value_of("x@[10:3]")

    with pytest.raises(ValueError):  # missing bit range
        FieldDef.value_of("x@S3.0")


def test_link():
    store = MemLink()
    r = Register(
        bit_len=8, address=0xA, name="AReg",
        model=[FieldDef.value_of("a@[3:0]U4.1"), FieldDef.value_of("b@[6:4]S3.0")]
    )
    # register is not linked yet, hence, r.linked_address must be None and write() should fail returning False
    assert r.linked_address is None
    assert r.write() == False

    assert r.is_changed() == False
    r.link(store)
    assert r.get_field_value("a") == 0.0
    r.read()
    assert r.is_changed() == False
    assert r.get_field_value("a") == 1.5

    # by default writing back just loaded value should happen
    assert r.write() == True

    # but writing back with if_changed_only set to True should not happen since we have not changed anything
    # in the register yet.
    assert r.write(if_changed_only=True) == False

    r.set_field_value("a", 0.5)
    assert r.is_changed() == True
    # calling read() should reset register value
    r.read()
    assert r.is_changed() == False
    assert r.get_field_value("a") == 1.5

    # now change register and write it to the store
    r.set_field_value("a", 0.5)
    assert r.get_field_value("a") == 0.5
    assert store.store[0xA] == BitArray("uint:8=3")
    assert r.write() == True
    assert r.is_changed() == False
    assert store.store[0xA] == BitArray("uint:8=1")

    # if register does not have an address and r.link(...) is missing address then error should be raised
    r = Register(8)
    with pytest.raises(ValueError):
        r.link(store)

    # but if address is provided than it is Ok
    r.link(store, 0xA)
    r.read()
    assert r.get_field_value("val") == 1.0

    # if register address is invalid then error "There is no register at the address ..." should be raised
    r.link(store, 0xB)
    with pytest.raises(RuntimeError):
        r.read()


def test_link_at_creation():
    store = MemLink()

    # linking at register construction time requires reg. address or ValueError should be raised
    with pytest.raises(ValueError):
        Register(bit_len=8, name="AReg", link=store)

    r = Register(bit_len=8, name="AReg", link=store, address=0xA)
    assert r.linked_address == 0xA
