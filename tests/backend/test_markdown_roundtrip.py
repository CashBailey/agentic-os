"""Deterministic tarball round-trip — byte-equal across two packings."""

from app.services.markdown_io import pack_files, unpack_tarball


def test_pack_is_deterministic():
    files = {
        "projects/demo/project.json": b'{"slug":"demo"}\n',
        "projects/demo/memory/1.md": b"---\nkind: note\n---\nhello\n",
        "globals/context/user.md": b"# user\n",
    }
    a = pack_files(files)
    b = pack_files(files)
    assert a == b, "pack_files must be byte-deterministic"


def test_roundtrip_pack_unpack_pack():
    files = {
        "globals/context/global/coding-standards.md": b"# standards\n",
        "projects/x/decisions/3.md": b"---\ntitle: t\n---\nbody\n",
        "projects/x/memory/2.md": b"---\nkind: lesson\ntitle: A\n---\nbody\nhere\n",
    }
    blob = pack_files(files)
    extracted = unpack_tarball(blob)
    assert extracted == files
    blob2 = pack_files(extracted)
    assert blob == blob2


def test_insertion_order_does_not_affect_output():
    f1 = {"a.md": b"a", "b.md": b"b", "c.md": b"c"}
    f2 = {"c.md": b"c", "a.md": b"a", "b.md": b"b"}
    assert pack_files(f1) == pack_files(f2)
