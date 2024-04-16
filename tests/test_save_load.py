from datetime import datetime
from ipaddress import IPv6Address
from pathlib import Path
from tempfile import NamedTemporaryFile

from nacl.signing import SigningKey

import data_mesher


def test_save_load() -> None:
    key = SigningKey.generate()

    hostnameA = data_mesher.Hostname("a")
    hostnameA.update_signature(key)
    peerA = data_mesher.Host(
        ip=IPv6Address("42::1"),
        port=7331,
        publicKey=key.verify_key,
        hostnames={"a": data_mesher.Hostname("a")},
    )
    peerA.update_signature(key)

    hostnameB = data_mesher.Hostname("b")
    hostnameB.update_signature(key)
    peerB = data_mesher.Host(
        ip=IPv6Address("42::2"),
        port=7331,
        publicKey=key.verify_key,
        hostnames={"b": hostnameB},
    )
    peerB.update_signature(key)
    network = data_mesher.Network(
        lastUpdate=datetime.now(),
        tld="test",
        public=True,
        hostSigningKeys=[key.verify_key],
        hosts={
            peerA.ip: peerA,
            peerB.ip: peerB,
        },
    )

    dm = data_mesher.DataMesher(
        networks={"test": network},
        name="testing",
        private_key=key,
    )
    with NamedTemporaryFile() as f:
        path = Path(f.name)
        dm.save(path)
        dm2 = data_mesher.load(path)
    dm2["test"].hosts[IPv6Address("42::1")].verify()
