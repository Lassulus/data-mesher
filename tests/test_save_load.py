from datetime import datetime
from ipaddress import IPv6Address
from pathlib import Path
from tempfile import NamedTemporaryFile

from nacl.signing import SigningKey

import data_mesher.data


def test_save_load() -> None:
    key = SigningKey.generate()

    hostnameA = data_mesher.data.Hostname("a")
    hostnameA.update_signature(key)
    peerA = data_mesher.data.Host(
        ip=IPv6Address("42::1"),
        port=7331,
        publicKey=key.verify_key,
        hostnames={"a": data_mesher.data.Hostname("a")},
    )
    peerA.update_signature(key)

    hostnameB = data_mesher.data.Hostname("b")
    hostnameB.update_signature(key)
    peerB = data_mesher.data.Host(
        ip=IPv6Address("42::2"),
        port=7331,
        publicKey=key.verify_key,
        hostnames={"b": hostnameB},
    )
    peerB.update_signature(key)
    network = data_mesher.data.Network(
        lastUpdate=datetime.now(),
        tld="test",
        public=True,
        hostSigningKeys=[key.verify_key],
        hosts={
            peerA.ip: peerA,
            peerB.ip: peerB,
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
    dm2.networks["test"].hosts[IPv6Address("42::1")].verify()
