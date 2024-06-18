from datetime import datetime
from ipaddress import IPv6Address
from pathlib import Path
from tempfile import NamedTemporaryFile

from nacl.signing import SigningKey

import data_mesher.data


def test_save_load() -> None:
    keyA = SigningKey.generate()
    hostnameA = data_mesher.data.Hostname("a")
    hostnameA.update_signature(keyA)
    peerA = data_mesher.data.Host(
        ip=IPv6Address("42::1"),
        port=7331,
        public_key=keyA.verify_key,
        hostnames={"a": data_mesher.data.Hostname("a")},
        signing_key=keyA,
    )
    peerA.update_signature(keyA)

    keyB = SigningKey.generate()
    hostnameB = data_mesher.data.Hostname("b")
    hostnameB.update_signature(keyB)
    peerB = data_mesher.data.Host(
        ip=IPv6Address("42::2"),
        port=7331,
        public_key=keyB.verify_key,
        hostnames={"b": hostnameB},
        signing_key=keyB,
    )
    peerB.update_signature(keyB)
    network = data_mesher.data.Network(
        last_update=datetime.now(),
        tld="test",
        public=True,
        host_signing_keys=[keyA.verify_key],
        hosts={
            keyA.verify_key: peerA,
            keyB.verify_key: peerB,
        },
    )

    with NamedTemporaryFile() as f:
        path = Path(f.name)
        dm = data_mesher.data.DataMesher(
            state_file=path,
            networks={"test": network},
            host=peerA,
        )
        dm.save()
        dm2 = data_mesher.data.DataMesher(state_file=path, host=peerA)
        dm2.networks["test"].hosts[keyA.verify_key].verify()
