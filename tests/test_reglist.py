from rgscore import RegList, Register, FieldDef


def test_json_serialization():
    rgsl = RegList()
    rgsl.add(Register(
        bit_len=8, name="Moo", address=0x02,
        model=[FieldDef.value_of("a@[3:0]U4.1#ro"), FieldDef.value_of("b@[6:4]S3.0")]
    ))
    rgsl.add(Register(
        bit_len=8, name="Foo", address=0x01,
        model=[FieldDef.value_of("a@[3:0]U4.1#ro")]
    ))

    json_def = rgsl.to_json_def()

    rl = RegList.from_json_def(json_def)
    assert rl.to_json_def() == rgsl.to_json_def()
