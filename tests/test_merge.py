from datetime import datetime
from ipaddress import IPv6Address

from nacl.signing import SigningKey

import data_mesher

a_key = SigningKey.generate()
b_key = SigningKey.generate()

peerA = data_mesher.Host(
    ip=IPv6Address("42::1"),
    port=7331,
    publicKey=a_key.verify_key,
    hostnames=[data_mesher.Hostname("a")],
)
networkA = data_mesher.Network(
    lastUpdate=datetime.now(),
    tld="test",
    public=True,
    hostSigningKeys=[a_key.verify_key],
    hosts={peerA.ip: peerA},
)

peerB = data_mesher.Host(
    ip=IPv6Address("42::2"),
    port=7331,
    publicKey=a_key.verify_key,
    hostnames=[data_mesher.Hostname("a")],
)
networkB = data_mesher.Network(
    lastUpdate=datetime.now(),
    tld="test",
    public=True,
    hostSigningKeys=[a_key.verify_key],
    hosts={peerB.ip: peerB},
)

# networkA.merge(networkB)
# print(networkA.hosts[peerB.ip].hostnames)
