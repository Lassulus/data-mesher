import ipaddress
import json
import logging
import os
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile

from nacl.encoding import Base64Encoder
from nacl.signing import SigningKey, VerifyKey

log = logging.getLogger(__name__)

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
        data: dict[str, str | int] = self.data_to_sign()
        if self.signed_at and self.signature:
            data["signature"] = self.signature.decode()
            data["signed_at"] = int(self.signed_at.timestamp())
        return dict(sorted(data.items()))

    def verify_signature(self, pubkeys: list[VerifyKey]) -> bool:
        for pubkey in pubkeys:
            if pubkey.verify(json.dumps(self.data_to_sign()).encode(), self.signature):
                return True
        return False

    def update_signature(self, signing_key: SigningKey) -> None:
        """
        Sign the content of the host with the given signingKey and update the signature.
        """
        self.signed_at = datetime.now()
        self.signature = signing_key.sign(
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
    public_key: VerifyKey
    last_seen: datetime
    hostnames: dict[str, Hostname]
    signature: bytes

    def __init__(
        self,
        ip: ipaddress.IPv6Address,
        port: int,
        public_key: VerifyKey,
        last_seen: datetime = datetime.now(),
        hostnames: dict[str, Hostname] = {},
        signature: bytes | None = None,
        signing_key: SigningKey | None = None,
    ) -> None:
        # we either need a signature or the signing key to create the signature
        assert signature or signing_key
        self.ip = ip
        self.port = port
        self.public_key = public_key
        self.last_seen = last_seen
        self.hostnames = hostnames
        if signature:
            self.signature = signature
        elif signing_key:
            self.update_signature(signing_key)

    def data_to_sign(
        self,
    ) -> Host_json_type:
        hostnames: dict[str, Hostname_json_type] = {}
        for hostname in self.hostnames:
            hostnames[hostname] = self.hostnames[hostname].__json__()
        hostnames = dict(sorted(hostnames.items()))
        data: Host_json_type = {
            "port": self.port,
            "ip": str(self.ip),
            "last_seen": int(self.last_seen.timestamp()),
            "hostnames": hostnames,
        }
        return dict(sorted(data.items()))

    def __json__(self) -> Host_json_type:  # TODO more types
        data = self.data_to_sign()
        data["signature"] = self.signature.decode()
        return dict(sorted(data.items()))

    def verify(self) -> bool:
        return (
            self.public_key.verify(self.signature, encoder=Base64Encoder)
            == json.dumps(self.data_to_sign()).encode()
        )

    def merge(self, other: "Host") -> None:
        if other.last_seen > self.last_seen:
            if other.verify():
                self.ip = other.ip
                self.port = other.port
                # should always be the same anyways
                self.public_key = other.public_key
                self.last_seen = other.last_seen
                self.signature = other.signature
                # TODO merge hostnames from others if they have a signature and it is our host
                self.hostnames = other.hostnames
            else:
                log.info(f"Invalid signature for host {other.ip}")

    def update_signature(self, signing_key: SigningKey) -> None:
        """
        Sign the content of the host with the given signing_key and return the signature.
        """
        self.last_seen = datetime.now()
        self.signature = signing_key.sign(
            json.dumps(self.data_to_sign()).encode(),
            encoder=Base64Encoder,
        )

    def is_up2date(self) -> bool:
        if self.last_seen:
            return (datetime.now() - self.last_seen).total_seconds() < 60
        return False

    def __str__(self) -> str:
        return f"{self.ip}:{self.port} {self.public_key.encode(encoder=Base64Encoder)}"

    def __repr__(self) -> str:
        return self.__str__()


Network_json_type = dict[
    str, dict[str, str | int | list[str]] | dict[str, Host_json_type]
]


class Network:
    last_update: datetime
    data_mesher: "DataMesher | None"
    tld: str
    public: bool
    host_signing_keys: list[VerifyKey]  # TODO proper class
    banned_keys: list[str]  # TODO proper class
    hostname_overrides: list  # TODO proper class
    _hosts: dict[VerifyKey, Host]

    def __init__(
        self,
        tld: str,
        public: bool = True,
        last_update: datetime = datetime.now(),
        host_signing_keys: list[VerifyKey] = [],
        banned_keys: list[str] = [],
        hostname_overrides: list = [],
        hosts: dict[VerifyKey, Host] = {},
    ) -> None:
        self.tld = tld
        self.public = public
        self.last_update = last_update
        self.host_signing_keys = host_signing_keys
        self.banned_keys = banned_keys
        self.hostname_overrides = hostname_overrides
        self._hosts = hosts
        self.data_mesher = None

    @property
    def hosts(self) -> dict[VerifyKey, Host]:
        hosts = self._hosts
        if self.data_mesher and self.data_mesher.host:
            if self.data_mesher.key:
                self.data_mesher.host.update_signature(self.data_mesher.key)

            hosts[self.data_mesher.host.public_key] = self.data_mesher.host
        return hosts

    def __json__(self) -> Network_json_type:
        settings: dict[str, str | int | list[str]] = {
            "last_update": int(self.last_update.timestamp()),
            "tld": self.tld,
            "public": self.public,
            "host_signing_keys": [
                k.encode(encoder=Base64Encoder).decode() for k in self.host_signing_keys
            ],
            "banned_keys": self.banned_keys,
            "hostname_overrides": self.hostname_overrides,
        }
        settings = dict(sorted(settings.items()))

        hosts: dict[str, Host_json_type] = {}
        log.debug(f"[network] hosts: {self.hosts}")
        for host in self.hosts:
            hosts[
                self.hosts[host].public_key.encode(encoder=Base64Encoder).decode()
            ] = self.hosts[host].__json__()
        log.debug(f"[network] parsed hosts: {hosts}")

        return {
            "hosts": hosts,
            "settings": settings,
        }

    def get_hosts_older_than(self, seconds: int) -> list[Host]:
        hosts: list[Host] = []
        now = datetime.now()
        for host in self.hosts:
            if (now - self.hosts[host].last_seen).total_seconds() > seconds:
                hosts.append(self.hosts[host])
        return hosts

    def merge(self, other: "Network") -> None:
        if other.last_update > self.last_update:
            log.debug(
                f"[network merge] timestamp of other is newer: {other.last_update}"
            )
            self.tld = other.tld
            self.public = other.public
            self.host_signing_keys = other.host_signing_keys
            self.banned_keys = other.banned_keys
            self.hostname_overrides = other.hostname_overrides
        for host in other.hosts:
            if host in self.hosts:
                self._hosts[host].merge(other.hosts[host])
            else:
                # TODO verify
                # verifying is a bit complicated because we don't get the public key if the other hosst desn't have it yet
                # if other.hosts[host].verify():
                #     self.hosts[host] = other.hosts[host]
                # else:
                #     log.debug(f"[network merge] invalid signature for host: {host}")
                self._hosts[host] = other.hosts[host]

        # TODO decay hosts


def load(data: dict) -> dict[str, Network]:
    networks: dict[str, Network] = {}
    for network in data:
        log.debug(f"[load] network: {data[network]}")
        hosts: dict[VerifyKey, Host] = {}
        for host in data[network]["hosts"]:
            log.debug(f"[load] host: {data[network]['hosts'][host]}")
            hostnames: dict[str, Hostname] = {}
            for hostname in data[network]["hosts"][host]["hostnames"]:
                log.debug(f"[load] hostname: {hostname}")
                if "signed_at" in data[network]["hosts"][host]["hostnames"][hostname]:
                    hostnames[hostname] = Hostname(
                        hostname=hostname,
                        signed_at=datetime.fromtimestamp(
                            data[network]["hosts"][host]["hostnames"][hostname][
                                "signed_at"
                            ]
                        ),
                        signature=data[network]["hosts"][host]["hostnames"][hostname][
                            "signature"
                        ].encode(),
                    )
                else:
                    hostnames[hostname] = Hostname(
                        hostname=hostname,
                    )
                log.debug(f"[load] parsed hostnames: {hostnames}")

            try:
                hosts[VerifyKey(host, encoder=Base64Encoder)] = Host(
                    ip=ipaddress.IPv6Address(data[network]["hosts"][host]["ip"]),
                    port=data[network]["hosts"][host]["port"],
                    public_key=VerifyKey(host, encoder=Base64Encoder),
                    last_seen=datetime.fromtimestamp(
                        data[network]["hosts"][host]["last_seen"]
                    ),
                    hostnames=hostnames,
                    signature=data[network]["hosts"][host]["signature"].encode(),
                )
            except Exception as e:
                log.error(f"[load] triggered exception: {repr(e)}")
        log.debug(f"[load] parsed hosts: {hosts}")
        networks[network] = Network(
            tld=data[network]["settings"]["tld"],
            public=data[network]["settings"]["public"],
            last_update=datetime.fromtimestamp(
                data[network]["settings"]["last_update"]
            ),
            host_signing_keys=[
                VerifyKey(k, encoder=Base64Encoder)
                for k in data[network]["settings"]["host_signing_keys"]
            ],
            banned_keys=data[network]["settings"]["banned_keys"],
            hostname_overrides=data[network]["settings"]["hostname_overrides"],
            hosts=hosts,
        )
        log.debug(f"[load] parsed network: {networks[network].__json__()}")
    return networks


class DataMesher:
    networks: dict[str, Network] = {}
    state_file: Path | None
    dns_file: Path | None
    key: SigningKey | None
    host: Host | None

    def __init__(
        self,
        host: Host | None = None,
        networks: dict[str, Network] = {},
        state_file: Path | None = None,
        dns_file: Path | None = None,
        key: SigningKey | None = None,
    ) -> None:
        self.state_file = state_file
        if state_file and state_file.exists():
            try:
                data = json.loads(state_file.read_text())
            except json.JSONDecodeError:
                data = {}
            self.networks = load(data)
        self.dns_file = dns_file
        self.networks = self.networks | networks
        log.debug(f"[dm init] networks: {self.networks}")
        for network in self.networks:
            log.debug("[dm init] setting self")
            self.networks[network].data_mesher = self
        self.host = host
        self.key = key

    def merge(self, other: "DataMesher") -> None:
        log.debug(f"[dm merge] merging networks: {self.networks}")
        for network in other.networks:
            if network in self.networks:
                self.networks[network].merge(other.networks[network])
            else:
                self.networks[network] = other.networks[network]
            self.networks[network].data_mesher = self
        log.debug(f"[dm merge] merged networks: {self.networks}")

    def __json__(self) -> dict[str, Network_json_type]:
        output: dict[str, Network_json_type] = {}
        for network in self.networks:
            output[network] = self.networks[network].__json__()
        return output

    def get_hostnames(self) -> Iterator[dict]:
        for network in self.networks:
            for host in self.networks[network].hosts:
                for hostname in self.networks[network].hosts[host].hostnames:
                    yield {
                        "hostname": f"{self.networks[network].hosts[host].hostnames[hostname].hostname}.{self.networks[network].tld}",
                        "ip": str(self.networks[network].hosts[host].ip),
                    }

    def save(self) -> None:
        if self.state_file is None:
            raise ValueError("No state_file set")
        data: dict[str, dict] = {}  # TODO more types
        for network in self.networks:
            data[network] = self.networks[network].__json__()
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(dir=self.state_file.parent, delete=False) as f:
            with open(f.name, "w+") as file:
                json.dump(data, file)
            os.rename(f.name, str(self.state_file))
        if self.dns_file:
            with NamedTemporaryFile(dir=self.dns_file.parent, delete=False) as f:
                with open(f.name, "w+") as file:
                    for hostname in self.get_hostnames():
                        log.debug(f"[save] hostname: {hostname}")
                        file.write(json.dumps(hostname) + "\n")
                os.rename(f.name, str(self.dns_file))
                log.debug(f"[save] moved {f.name} to {self.dns_file}")

    @property
    def all_hosts(self) -> list[Host]:
        hosts: list[Host] = []
        for network in self.networks:
            for host in self.networks[network].hosts:
                hosts.append(self.networks[network].hosts[host])
        return hosts
