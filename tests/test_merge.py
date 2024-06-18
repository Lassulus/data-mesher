from datetime import datetime
from ipaddress import IPv6Address

from nacl.signing import SigningKey

import data_mesher.data


def test_merge() -> None:
    a_key = SigningKey.generate()
    b_key = SigningKey.generate()

    peerA = data_mesher.data.Host(
        ip=IPv6Address("42::1"),
        port=7331,
        public_key=a_key.verify_key,
        hostnames={"a": data_mesher.data.Hostname("a")},
    )
    peerA.update_signature(a_key)
    networkA = data_mesher.data.Network(
        last_update=datetime.now(),
        tld="test",
        public=True,
        host_signing_keys=[a_key.verify_key],
        hosts={peerA.public_key: peerA},
    )

    peerB = data_mesher.data.Host(
        ip=IPv6Address("42::2"),
        port=7331,
        public_key=b_key.verify_key,
        hostnames={"b": data_mesher.data.Hostname("b")},
    )
    peerB.update_signature(b_key)
    networkB = data_mesher.data.Network(
        last_update=datetime.now(),
        tld="test",
        public=True,
        host_signing_keys=[a_key.verify_key],
        hosts={peerB.public_key: peerB},
    )

    networkA.merge(networkB)
    networkA.hosts[peerB.public_key].verify()
