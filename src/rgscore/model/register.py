import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import cache, reduce
from typing import Optional

from bitstring import BitArray
from i2c_api import I2CMaster


class RLink(ABC):
    @abstractmethod
    def read(self, addr: int, width: int) -> Optional[BitArray]:
        """
        Reads raw register value (of `width` bits) from address `addr`.
        If no register exist at this address, then returns None.
        """

    @abstractmethod
    def write(self, addr: int, value: BitArray) -> bool:
        """
        Writes register value `value` to address `addr`. If register does exist at this address the do write and
        return True, otherwise return False.
        """


class RLinkI2C(RLink):
    def __init__(self, i2c: I2CMaster, device_address: int):
        self.i2c = i2c
        self.device_address = device_address

    def read(self, addr: int, width: int) -> Optional[BitArray]:
        bytes_to_read = int(width / 8)
        if (width % 8) > 0:
            bytes_to_read += 1
        data = self.i2c.read_register(address=self.device_address, register=addr, num_bytes=bytes_to_read)
        if data is None:
            return None
        else:
            return BitArray(data[0:width])  # TODO: Check. This might be incorrect

    def write(self, addr: int, value: BitArray) -> bool:
        self.i2c.write_register(address=self.device_address, register=addr, data=value)


@dataclass(frozen=True)
class FieldDef:
    name: Optional[str]
    offset: int
    signed: str
    width: int
    fractional: int
    rw: bool

    @cache
    def range(self) -> tuple[float, float]:
        if self.signed == "U":
            return (0.0, (pow(2, self.width) - 1) / pow(2, self.fractional))
        else:
            return (
                -(pow(2, self.width - 1) / pow(2, self.fractional)),
                (pow(2, self.width - 1) - 1) / pow(2, self.fractional)
            )

    @cache
    def end_offset(self) -> int:
        return self.offset + self.width - 1

    @cache
    def idxs(self) -> list[int]:
        l = list(range(self.offset, self.end_offset() + 1))
        return l

    def format(self, value: float) -> str:
        return f"{int(value)}" if self.fractional == 0 else f"{value}"

    @cache
    def __repr__(self):
        rw = "rw" if self.rw else "ro"
        return (("" if self.name is None else f"{self.name}@") +
                f"[{self.end_offset()}:{self.offset}]{self.signed}{self.width}.{self.fractional}#{rw}")

    def read_raw(self, data: BitArray) -> BitArray:
        return data[(data.len - self.end_offset() - 1):(data.len - self.offset)]

    def read(self, data: BitArray) -> int:
        raw_field = self.read_raw(data)
        return (raw_field.int if self.signed == "S" else raw_field.uint) / pow(2, self.fractional)

    def write(self, data: BitArray, value: float) -> None:
        new_val = int(value * pow(2, self.fractional))
        tspec = (f"int:" if self.signed == "S" else f"uint:") + f"{self.width}={new_val}"
        data.overwrite(BitArray(tspec), data.len - self.end_offset() - 1)

    @staticmethod
    def value_of(field_definition: str) -> "FieldDef":
        m = Register.field_def_re.match(field_definition)
        if m:
            start_offset = int(m.group("start"))
            end_offset = int(m.group("end"))
            implied_width = end_offset - start_offset + 1
            width = int(m.group("w"))
            if implied_width != width:
                raise ValueError(f"Inconsistent field width {implied_width} != {width}")
            rw = m.group("rw")
            rw = rw if rw else "rw"
            return FieldDef(name=m.group("name"), offset=start_offset, signed=m.group("s"),
                            width=width, fractional=int(m.group("f")), rw=(rw == "rw"))
        else:
            raise ValueError(f"Invalid register field definition [{field_definition}]")


class Register:
    field_def_re = re.compile(
        r"^(?P<name>[a-zA-Z_]+[0-9]*)@\[(?P<end>\d+):(?P<start>\d+)\](?P<s>U|S)(?P<w>\d+)\.(?P<f>\d+)(#(?P<rw>rw|ro))?$"
    )

    def __init__(self, bit_len: int, model: Optional[list[FieldDef]] = None, address: Optional[int] = None,
                 name: Optional[str] = None):
        """
        Register in an object that encapsulates array of bits and field definitions and provides read and write
        access to these fields. Fields are defined in the model

        :param bit_len: width of register in bits
        :param model: model of register fields
        :param address: register address (optional)
        :param name: register name (optional)
        """
        if name is not None and not re.match("^[a-zA-Z]+[a-zA-Z0-9_]+$", name):
            raise ValueError("Invalid register name.")

        if bit_len <= 0:
            raise ValueError("Register width must be greater than zero")
        self.data = BitArray(bit_len)
        self.width = bit_len

        self._model = [FieldDef.value_of(f"val@[{bit_len - 1}:0]U{bit_len}.0")] if model is None else model
        if self._model == []:
            raise ValueError(
                "Register model must not be empty list. Leaving it None will create implicit field though."
            )
        self._fields_by_name: dict[str, FieldDef] = {fd.name: fd for fd in self._model}
        if len(self._fields_by_name) != len(self._model):
            raise ValueError("Duplicate field names in the model")
        for m in self._model:
            if m.end_offset() >= self.width or m.offset < 0:
                raise ValueError(f"Field \"{m.name}\" extends outside of register width.")

        fields_idxs = reduce(lambda x, y: x + y, [m.idxs() for m in self._model], [])
        if len(set(fields_idxs)) != len(fields_idxs):
            raise ValueError("Overlapping fields in register definition.")

        self.address = address
        self.name = name
        self._link: Optional[RLink] = None
        self.linked_address: Optional[int] = None

    def get_def(self) -> str:
        """ Returns human-readable register definition. """
        return "Register" + ("" if self.name is None else f" name:{self.name}") + \
            ("" if self.address is None else f" addr:0x{self.address:X}") + \
            f" width:{self.width} fields:{self._model}"

    def __repr__(self):
        retval = "Register" if self.name is None else self.name
        if self.address is not None:
            retval += f"[0x{self.address:X}]"
        return f"{retval}(" + ", ".join(
            [f"{field_def.name}={field_def.format(field_def.read(self.data))}" for field_def in self._model]
        ) + ")"

    def set_field_value(self, field: str, value: float) -> None:
        """
        Sets value to a field or raises exception if unable to do so.
        """
        field_def = self._fields_by_name.get(field)
        if field_def is None:
            raise ValueError(f"There is no field \"{field}\" in this register.")
        if not field_def.rw:
            raise ValueError(f"Field \"{field}\" is not writable.")
        min, max = field_def.range()
        if min <= value <= max:
            field_def.write(self.data, value)
        else:
            raise ValueError(f"Value {value} is out of range [{field_def.range()}] for field \"{field}\"")

    def get_field_value(self, field: str) -> float:
        field_def = self._fields_by_name.get(field)
        if field_def is None:
            raise ValueError(f"There is no field \"{field}\" in this register.")
        else:
            return field_def.read(self.data)

    def get_field_value_raw(self, field: str) -> BitArray:
        field_def = self._fields_by_name.get(field)
        if field_def is None:
            raise ValueError(f"There is no field \"{field}\" in this register.")
        else:
            return field_def.read_raw(self.data)

    def get_field_values(self) -> dict[str, float]:
        return {m.name: self.get_field_value(m.name) for m in self._model}

    def get_field_definition(self, field: str) -> FieldDef:
        return self._fields_by_name[field]

    def get_field_names(self) -> list[str]:
        return [m.name for m in self._model]

    def link(self, link: RLink, address: Optional[int] = None) -> None:
        """
        Links register to external store. If optional address is provided, then it will be used to access external store
        even if register has address in its definition. If optional address is not provided, then address defined in the
        register will be used. If no addresses are given and present in the internal register definition then ValueError
        will be raised.

        :param link: link to external store
        :param address: address of register in external store
        """
        self.linked_address = self.address if address is None else address
        if self.linked_address is None:
            raise ValueError(
                "To link register to external store address must be either set in the register "
                "or provided during linking."
            )
        self._link = link

    def read(self) -> None:
        if self._link is not None:
            raw_data = self._link.read(self.linked_address, self.width)
            if raw_data is None:
                raise RuntimeError(f"There is no register at the address {self.linked_address}.")
            self.data = raw_data

    def write(self, read_back: bool = False) -> None:
        if self._link is not None:
            self._link.write(self.linked_address, self.data)
            if read_back:
                self.read()
