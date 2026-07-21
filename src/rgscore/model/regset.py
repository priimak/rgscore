from typing import Optional

from rgscore.model.register import Register, RLink


class RegSet(object):
    def __init__(self, store: Optional[RLink] = None):
        self.registers: list[Register] = []
        self._reg_names: set[str] = set()
        self._reg_addresses: set[int] = set()
        self._store = store

    def add(self, r: Register):
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

    def read_all(self) -> None:
        for r in self.registers:
            r.read()

    def write_all(self) -> None:
        for r in self.registers:
            r.write()
