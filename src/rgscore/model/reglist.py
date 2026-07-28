import json
from typing import Optional, Self

from rgscore.model.register import Register, RLink


class RegList:
    def __init__(self, store: Optional[RLink] = None):
        super().__init__()
        self.registers: list[Register] = []
        self._reg_names: set[str] = set()
        self._reg_addresses: set[int] = set()
        self._reg_by_names: dict[str, Register] = {}
        self._reg_by_address: dict[int, Register] = {}
        self._store = store

    def add(self, rs: Register | list[Register]):
        rs = [rs] if isinstance(rs, Register) else rs
        for r in rs:
            if r.address is None:
                raise ValueError("To be added Register must have an address")

            if r.name is None:
                # create implicit register name if register does not an explicit one
                r.name = f"R{r.address}"

            if r.name in self._reg_names:
                raise ValueError(f"Register under a name [{r.name}] is already in the set")

            if r.address in self._reg_addresses:
                raise ValueError(f"Register at this address [{r.address}] is already in the set")

            if self._store is not None:
                r.link(self._store)

            self.registers.append(r)
            self._reg_names.add(r.name)
            self._reg_addresses.add(r.address)
            self._reg_by_names[r.name] = r
            self._reg_by_address[r.address] = r

        self.registers.sort(key=lambda r: r.address)

    def get_register_by_name(self, name: str) -> Register | None:
        return self._reg_by_names.get(name)

    def get_register_by_address(self, address: int) -> Register | None:
        return self._reg_by_address.get(address)

    def clear(self):
        """ Removes all registers from the list. """
        self.registers.clear()
        self._reg_names.clear()
        self._reg_addresses.clear()
        self._reg_by_names.clear()
        self._reg_by_address.clear()

    def read_all(self) -> None:
        """ Reads all registers in the regList from linked store if any provided. """
        for r in self.registers:
            r.read()

    def write_all(self) -> None:
        """ Writes all registers in the regList to linked store if any provided. """
        for r in self.registers:
            r.write()

    def to_json_def(self, indent: int | None = None) -> str:
        """ Exports register definition contained within regList as json text. """
        return json.dumps({
            "class": "RegList",
            "version": 1,
            "registers": [r.to_dict_def() for r in self.registers]
        }, indent=indent)

    @staticmethod
    def from_json_def(json_str: str) -> "RegList":
        """ Imports a RegList definition from a json string returning new instance of RegList. """
        return RegList().load_from_json_def(json_str)

    def load_from_json_def(self, json_str: str) -> Self:
        data = json.loads(json_str)
        if data["class"] != "RegList":
            raise ValueError("Provided json document does not represent regList")
        elif data["version"] != 1:
            raise ValueError(f"Provided regList json has unsupported version {data['version']}")
        else:
            self.clear()
            self.add([Register.from_dict_def(d) for d in data["registers"]])
        return self
