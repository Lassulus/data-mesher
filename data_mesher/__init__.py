import argparse
import ipaddress
import json
import sys
from datetime import datetime

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

    def data_to_sign(self) -> dict[str, bytes | str | int]:
        data: dict[str, bytes | str | int] = {
            "hostname": self.hostname,
        }
        if self.signed_at and self.signature:
            data["signed_at"] = int(self.signed_at.timestamp())
        return dict(sorted(data.items()))

    def __json__(self) -> dict[str, bytes | str | int]:
        data = self.data_to_sign()
        if self.signed_at and self.signature:
            data["signature"] = self.signature
        return dict(sorted(data.items()))

    def update_from_data(self, hostname: str, signedAt: int, signature: bytes) -> None:
        self.hostname = hostname
        self.signedAt = datetime.fromtimestamp(signedAt)
        self.signature = signature

    def check_signature(self, pubkeys: list[VerifyKey]) -> bool:
        for pubkey in pubkeys:
            if pubkey.verify(json.dumps(self.data_to_sign()).encode(), self.signature):
                return True
        return False

    def merge(self, other: "Hostname") -> None:
        if self.signed_at and other.signed_at:
            if self.signed_at < other.signed_at:
                self.hostname = other.hostname
                self.signed_at = other.signed_at
                self.signature = other.signature
        elif other.signed_at:
            self.hostname = other.hostname
            self.signed_at = other.signed_at
            self.signature = other.signature

    def update_signature(self, signingKey: SigningKey) -> None:
        """
        Sign the content of the host with the given signingKey and update the signature.
        """
        self.signed_at = datetime.now()
        self.signature = signingKey.sign(
            json.dumps(self.data_to_sign()).encode(), encoder=Base64Encoder
        )


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
    hostnames: list[Hostname]  # TODO proper class
    signature: bytes | None

    def __init__(
        self,
        ip: ipaddress.IPv6Address,
        port: int,
        publicKey: VerifyKey | None = None,
        lastSeen: datetime = datetime.now(),
        hostnames: list[Hostname] = [],
        signature: bytes | None = None,
    ) -> None:
        self.ip = ip
        self.port = port
        self.publicKey = publicKey
        self.lastSeen = lastSeen
        self.hostnames = hostnames
        self.signature = signature

    def data_to_sign(self) -> dict[str, str | bytes | int | list]:
        if self.publicKey:
            data: dict[str, str | int | list] = {
                "port": self.port,
                "publicKey": self.publicKey.encode(Base64Encoder).decode(),
                "lastSeen": int(self.lastSeen.timestamp()),
                "hostnames": [h.data_to_sign() for h in self.hostnames],
            }
        else:
            raise ValueError("No publicKey set")
        return dict(sorted(data.items()))

    def __json__(self) -> dict:
        data = self.data_to_sign()
        if self.signature:
            data["signature"] = self.signature
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
                # TODO better merging for hostnames
                self.hostnames = other.hostnames
                self.signature = other.signature
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

    def __json__(self) -> dict:
        settings = dict(
            sorted(
                {
                    "lastUpdate": int(self.lastUpdate.timestamp()),
                    "tld": self.tld,
                    "public": self.public,
                    "hostSigningKeys": [k.encode() for k in self.hostSigningKeys],
                    "bannedKeys": self.bannedKeys,
                    "hostnameOverrides": self.hostnameOverrides,
                }.items()
            )
        )
        hosts = {str(ip): host.__json__() for ip, host in sorted(self.hosts.items())}
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


def main(args: list[str] = sys.argv[1:]) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        choices=["create", "add-host", "add-hostname", "add-host-signing-key"],
    )
