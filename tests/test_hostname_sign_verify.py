from ipaddress import IPv6Address

from nacl.signing import SigningKey

import data_mesher


def test_save_load() -> None:
    key = SigningKey.generate()

    hostname = data_mesher.Hostname("a")
    hostname.update_signature(key)
    peer = data_mesher.Host(
        ip=IPv6Address("42::1"),
        port=7331,
        publicKey=key.verify_key,
        hostnames={"test": data_mesher.Hostname("test")},
    )
    peer.update_signature(key)
    peer.verify()
