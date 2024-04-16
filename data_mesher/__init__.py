import argparse
import ipaddress
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile

from nacl.encoding import Base64Encoder
from nacl.signing import SigningKey, VerifyKey

"""
{
  "somepublickeyXXXXxxx" {
    "settings": {
      "lastUpdate":1238918291823 # some timestamp, oldest timestamp wins
      "tld": "n",
      "public": false, # a public network doesn't need the adminSignature on the host level
      "additionalHostSigningKeys": [
        "1asdaasd", # the additional keys can be used to sign hostnames or hosts
      ],
      "bannedKeys": [
        "dasodaosidjaosdijas" # banned hostKeys
      ],
      "hostnameOverrides": [
        { "hostname": "wiki", "address": "dcc:c5da:5295:c853:d499:935e:6b45:fd2f" }
      ],
      "signature": "yadayada" # the signature of the settings, signed by the networks adminKey
      ...
    },
    "hosts": {
      "fdcc:c5da:5295:c853:d499:935e:6b45:fd2f": {
        "publicKey": "asdasduhiuahsidua", # since we can't deduce the public key from the ip address (but we can verify it), we need to transmit it also
        "lastSeen": "2024-02-21T06:17:27+01:00", # when this host was last seen, this is used for connection retry or decaying the host
        "hostnames": [
          { "hostname": "ignavia", "signed_at": "8768768778", "signature": "asdasdasdad" } # signature is used in case of conflict, is signed by the networks adminKey or any additionalHostSigningKeys
          # if multiple hosts claim the same hostnames the earlier signing date wins
          # if there are multiple signatures for the same hostnames the oldest one wins, if 2 have the same time, the lexicographically first signature wins
          { "hostname": "wiki-backup" } # hostnames which are not signed yet don't have a signature and a timestamp, other peers will only accept them if they don't conflict with another existing hostname
        ],
        "signature": "sha256:oaisjdoaisjd" # the signature of the content without the signature, signed by the host
        "adminSignature": "jiuasiduashdiausdh" # if the network is not public, we can use this signature to aknowledge that this host is part of the network, the admin signature is just signing the ip address of the host (with which we can check if the publicKey is correct)
      },
      "fdcc:c5da:5295:c853:d499:935e:6b45:fefe": {
        ...
      }
    }
  }
}
"""

Hostname_json_type = dict[str, str | int]


class Hostname:
    hostname: str
    signature: bytes | None
    signed_at: datetime | None

    def __init__(
        self,
        hostname: str,
        signed_at: datetime | None = None,
        signature: bytes | None = None,
    ) -> None:
        self.hostname = hostname
        self.signed_at = signed_at
        self.signature = signature

    def data_to_sign(self) -> dict[str, str | int]:
        data: dict[str, str | int] = {
            "hostname": self.hostname,
        }
        if self.signed_at and self.signature:
            data["signed_at"] = int(self.signed_at.timestamp())
        return dict(sorted(data.items()))

    def __json__(self) -> Hostname_json_type:
        data: dict[str, str | int] = {}
        if self.signed_at and self.signature:
            data["signature"] = self.signature.decode()
            data["signed_at"] = int(self.signed_at.timestamp())
        return dict(sorted(data.items()))

    def verify_signature(self, pubkeys: list[VerifyKey]) -> bool:
        for pubkey in pubkeys:
            if pubkey.verify(json.dumps(self.data_to_sign()).encode(), self.signature):
                return True
        return False

    def update_signature(self, signingKey: SigningKey) -> None:
        """
        Sign the content of the host with the given signingKey and update the signature.
        """
        self.signed_at = datetime.now()
        self.signature = signingKey.sign(
            json.dumps(self.data_to_sign()).encode(),
            encoder=Base64Encoder,
        )


Host_json_type = dict[str, str | int | dict[str, Hostname_json_type]]


class Host:
    """
    Represents a host in the network.

    A host needs an ip address
    For correct operation a publicKey is needed
    The signature is used to verify the content of the host, it is signed by the host itself.
    The adminSignature is used to verify that the host is part of the network, it is signed by on of the hostSigningKeys.
    """

    ip: ipaddress.IPv6Address
    port: int
    publicKey: VerifyKey | None
    lastSeen: datetime
    hostnames: dict[str, Hostname]
    signature: bytes | None

    def __init__(
        self,
        ip: ipaddress.IPv6Address,
        port: int,
        publicKey: VerifyKey | None = None,
        lastSeen: datetime = datetime.now(),
        hostnames: dict[str, Hostname] = {},
        signature: bytes | None = None,
    ) -> None:
        self.ip = ip
        self.port = port
        self.publicKey = publicKey
        self.lastSeen = lastSeen
        self.hostnames = hostnames
        self.signature = signature

    def data_to_sign(
        self,
    ) -> Host_json_type:
        if self.publicKey:
            hostnames: dict[str, Hostname_json_type] = {}
            for hostname in self.hostnames:
                hostnames[hostname] = self.hostnames[hostname].__json__()
            hostnames = dict(sorted(hostnames.items()))
            data: Host_json_type = {
                "port": self.port,
                "publicKey": self.publicKey.encode(Base64Encoder).decode(),
                "lastSeen": int(self.lastSeen.timestamp()),
                "hostnames": hostnames,
            }
        else:
            raise ValueError("No publicKey set")
        return dict(sorted(data.items()))

    def __json__(self) -> Host_json_type:  # TODO more types
        data = self.data_to_sign()
        if self.signature:
            data["signature"] = self.signature.decode()
        return dict(sorted(data.items()))

    def verify(self) -> bool:
        if self.publicKey and self.signature:
            return (
                self.publicKey.verify(self.signature, encoder=Base64Encoder)
                == json.dumps(self.data_to_sign()).encode()
            )
        return False

    def merge(self, other: "Host") -> None:
        if other.lastSeen > self.lastSeen:
            if other.verify():
                self.port = other.port
                self.publicKey = other.publicKey
                self.lastSeen = other.lastSeen
                self.signature = other.signature
                # TODO merge hostnames from others if they have a signature and it is our host
                self.hostnames = other.hostnames
            else:
                print("Invalid signature")

    def update_signature(self, signingKey: SigningKey) -> None:
        """
        Sign the content of the host with the given signingKey and return the signature.
        """
        self.lastSeen = datetime.now()
        self.signature = signingKey.sign(
            json.dumps(self.data_to_sign()).encode(),
            encoder=Base64Encoder,
        )


Network_json_type = dict[
    str, dict[str, str | int | list[str]] | dict[str, Host_json_type]
]


class Network:
    lastUpdate: datetime
    tld: str
    public: bool
    hostSigningKeys: list[VerifyKey]  # TODO proper class
    bannedKeys: list[str]  # TODO proper class
    hostnameOverrides: list  # TODO proper class
    hosts: dict[ipaddress.IPv6Address, Host]

    def __init__(
        self,
        tld: str,
        public: bool = True,
        lastUpdate: datetime = datetime.now(),
        hostSigningKeys: list[VerifyKey] = [],
        bannedKeys: list[str] = [],
        hostnameOverrides: list = [],
        hosts: dict[ipaddress.IPv6Address, Host] = {},
    ) -> None:
        self.tld = tld
        self.public = public
        self.lastUpdate = lastUpdate
        self.hostSigningKeys = hostSigningKeys
        self.bannedKeys = bannedKeys
        self.hostnameOverrides = hostnameOverrides
        self.hosts = hosts

    def __json__(self) -> Network_json_type:
        settings: dict[str, str | int | list[str]] = {
            "lastUpdate": int(self.lastUpdate.timestamp()),
            "tld": self.tld,
            "public": self.public,
            "hostSigningKeys": [
                k.encode(encoder=Base64Encoder).decode() for k in self.hostSigningKeys
            ],
            "bannedKeys": self.bannedKeys,
            "hostnameOverrides": self.hostnameOverrides,
        }
        settings = dict(sorted(settings.items()))

        hosts: dict[str, Host_json_type] = {}
        for host in dict(sorted(self.hosts.items())):
            hosts[str(self.hosts[host].ip)] = self.hosts[host].__json__()

        return {
            "hosts": hosts,
            "settings": settings,
        }

    def merge(self, other: "Network") -> None:
        if other.lastUpdate > self.lastUpdate:
            self.tld = other.tld
            self.public = other.public
            self.hostSigningKeys = other.hostSigningKeys
            self.bannedKeys = other.bannedKeys
            self.hostnameOverrides = other.hostnameOverrides
        for host in other.hosts:
            if host in self.hosts:
                self.hosts[host].merge(other.hosts[host])
            else:
                if other.hosts[host].verify():
                    self.hosts[host] = other.hosts[host]

        # TODO decay hosts


class DataMesher:
    networks: dict[str, Network]
    name: str
    private_key: SigningKey

    def __init__(
        self, networks: dict[str, Network], name: str, private_key: SigningKey
    ) -> None:
        self.networks = networks
        self.name = name
        self.private_key = private_key

    def save(self, path: Path) -> None:
        data: dict[str, dict] = {}  # TODO more types
        for network in self.networks:
            data[network] = self.networks[network].__json__()
        path.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile() as f:
            with open(f.name, "w") as file:
                json.dump(data, file)
            shutil.copy(f.name, str(path))


def load(path: Path) -> dict[str, Network]:
    data = json.loads(path.read_text())
    networks: dict[str, Network] = {}
    for network in data:
        hosts: dict[ipaddress.IPv6Address, Host] = {}
        for host in data[network]["hosts"]:
            hostnames: dict[str, Hostname] = {}
            for hostname in data[network]["hosts"][host]["hostnames"]:
                if (
                    "signed_at" in data[network]["hosts"][host]["hostnames"][hostname]
                    and "signature"
                    in data[network]["hosts"][host]["hostnames"][hostname]
                ):
                    hostnames[hostname] = Hostname(
                        hostname=hostname,
                        signed_at=datetime.fromtimestamp(
                            data[network]["hosts"][host]["hostnames"][hostname][
                                "signed_at"
                            ]
                        ),
                        signature=data[network]["hosts"][host]["hostnames"][hostname][
                            "signature"
                        ],
                    )
                else:
                    hostnames[hostname] = Hostname(
                        hostname=hostname,
                    )

            hosts[ipaddress.IPv6Address(host)] = Host(
                ip=ipaddress.IPv6Address(host),
                port=data[network]["hosts"][host]["port"],
                publicKey=VerifyKey(
                    data[network]["hosts"][host]["publicKey"], encoder=Base64Encoder
                ),
                lastSeen=datetime.fromtimestamp(
                    data[network]["hosts"][host]["lastSeen"]
                ),
                hostnames=hostnames,
                signature=data[network]["hosts"][host]["signature"],
            )
        networks[network] = Network(
            tld=data[network]["settings"]["tld"],
            public=data[network]["settings"]["public"],
            lastUpdate=datetime.fromtimestamp(data[network]["settings"]["lastUpdate"]),
            hostSigningKeys=[
                VerifyKey(k, encoder=Base64Encoder)
                for k in data[network]["settings"]["hostSigningKeys"]
            ],
            bannedKeys=data[network]["settings"]["bannedKeys"],
            hostnameOverrides=data[network]["settings"]["hostnameOverrides"],
            hosts=hosts,
        )
    return networks


def main(args: list[str] = sys.argv[1:]) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        choices=["create", "add-host", "add-hostname", "add-host-signing-key"],
    )
