from ipaddress import IPv6Address

from nacl.signing import SigningKey

import data_mesher.data


def test_save_load() -> None:
    key = SigningKey.generate()

    hostname = data_mesher.data.Hostname("a")
    hostname.update_signature(key)
    peer = data_mesher.data.Host(
        ip=IPv6Address("42::1"),
        port=7331,
        public_key=key.verify_key,
        hostnames={"test": data_mesher.data.Hostname("test")},
    )
    peer.update_signature(key)
    peer.verify()
