import ipaddress
import json
import logging
import os
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
    publicKey: VerifyKey
    lastSeen: datetime
    hostnames: dict[str, Hostname]
    signature: bytes | None

    def __init__(
        self,
        ip: ipaddress.IPv6Address,
        port: int,
        publicKey: VerifyKey,
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
        hostnames: dict[str, Hostname_json_type] = {}
        for hostname in self.hostnames:
            hostnames[hostname] = self.hostnames[hostname].__json__()
        hostnames = dict(sorted(hostnames.items()))
        data: Host_json_type = {
            "port": self.port,
            "ip": str(self.ip),
            "lastSeen": int(self.lastSeen.timestamp()),
            "hostnames": hostnames,
        }
        return dict(sorted(data.items()))

    def __json__(self) -> Host_json_type:  # TODO more types
        data = self.data_to_sign()
        if self.signature:
            data["signature"] = self.signature.decode()
        return dict(sorted(data.items()))

    def verify(self) -> bool:
        if self.signature:
            return (
                self.publicKey.verify(self.signature, encoder=Base64Encoder)
                == json.dumps(self.data_to_sign()).encode()
            )
        else:
            log.debug("[verify] No signature")
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

    def is_up2date(self) -> bool:
        if self.lastSeen:
            return (datetime.now() - self.lastSeen).total_seconds() < 60
        return False

    def __str__(self) -> str:
        return f"{self.ip}:{self.port} {self.publicKey.encode(encoder=Base64Encoder)}"

    def __repr__(self) -> str:
        return self.__str__()


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
    hosts: dict[VerifyKey, Host]

    def __init__(
        self,
        tld: str,
        public: bool = True,
        lastUpdate: datetime = datetime.now(),
        hostSigningKeys: list[VerifyKey] = [],
        bannedKeys: list[str] = [],
        hostnameOverrides: list = [],
        hosts: dict[VerifyKey, Host] = {},
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
        log.debug(f"hosts: {self.hosts}")
        for host in self.hosts:
            hosts[self.hosts[host].publicKey.encode(encoder=Base64Encoder).decode()] = (
                self.hosts[host].__json__()
            )

        return {
            "hosts": hosts,
            "settings": settings,
        }

    def get_hosts_older_than(self, seconds: int) -> list[Host]:
        hosts: list[Host] = []
        now = datetime.now()
        for host in self.hosts:
            if (now - self.hosts[host].lastSeen).total_seconds() > seconds:
                hosts.append(self.hosts[host])
        return hosts

    def merge(self, other: "Network") -> None:
        if other.lastUpdate > self.lastUpdate:
            log.debug(
                f"[network merge] timestamp of other is newer: {other.lastUpdate}"
            )
            self.tld = other.tld
            self.public = other.public
            self.hostSigningKeys = other.hostSigningKeys
            self.bannedKeys = other.bannedKeys
            self.hostnameOverrides = other.hostnameOverrides
        for host in other.hosts:
            if host in self.hosts:
                self.hosts[host].merge(other.hosts[host])
            else:
                # TODO verify
                # verifying is a bit complicated because we don't get the public key if the other hosst desn't have it yet
                # if other.hosts[host].verify():
                #     self.hosts[host] = other.hosts[host]
                # else:
                #     log.debug(f"[network merge] invalid signature for host: {host}")
                self.hosts[host] = other.hosts[host]

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
                        ].encode(),
                    )
                else:
                    hostnames[hostname] = Hostname(
                        hostname=hostname,
                    )
                log.debug(f"[load] parsed hostnames: {hostnames}")

            try:
                if "signature" in data[network]["hosts"][host]:
                    signature = data[network]["hosts"][host]["signature"]
                else:
                    signature = None
                hosts[VerifyKey(host, encoder=Base64Encoder)] = Host(
                    ip=ipaddress.IPv6Address(data[network]["hosts"][host]["ip"]),
                    port=data[network]["hosts"][host]["port"],
                    publicKey=VerifyKey(host, encoder=Base64Encoder),
                    lastSeen=datetime.fromtimestamp(
                        data[network]["hosts"][host]["lastSeen"]
                    ),
                    hostnames=hostnames,
                    signature=signature,
                )
            except Exception as e:
                log.info(f"[load] triggered exception: {repr(e)}")
            log.debug(f"[load] parsed hosts: {hosts}")
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
    log.debug(f"[load] returning: {networks}")
    return networks


class DataMesher:
    networks: dict[str, Network] = {}
    state_file: Path | None
    key: SigningKey | None
    host: Host | None

    def __init__(
        self,
        host: Host | None = None,
        networks: dict[str, Network] = {},
        state_file: Path | None = None,
        key: SigningKey | None = None,
    ) -> None:
        self.state_file = state_file
        if state_file and state_file.exists():
            try:
                data = json.loads(state_file.read_text())
            except json.JSONDecodeError:
                data = {}
            self.networks = load(data)
        self.networks = self.networks | networks
        self.host = host
        self.key = key

    def merge(self, other: "DataMesher") -> None:
        for network in other.networks:
            if network in self.networks:
                self.networks[network].merge(other.networks[network])
            else:
                self.networks[network] = other.networks[network]
        log.debug(f"[dm merge] merged networks: {self.networks}")

    def __json__(self) -> dict[str, Network_json_type]:
        output: dict[str, Network_json_type] = {}
        for network in self.networks:
            output[network] = self.networks[network].__json__()
        return output

    def save(self) -> None:  # TODO make atomic
        if self.state_file is None:
            raise ValueError("No state_file set")
        data: dict[str, dict] = {}  # TODO more types
        for network in self.networks:
            data[network] = self.networks[network].__json__()
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(dir=self.state_file.parent, delete=False) as f:
            with open(f.name, "w") as file:
                json.dump(data, file)
            os.rename(f.name, str(self.state_file))

    @property
    def all_hosts(self) -> list[Host]:
        hosts: list[Host] = []
        for network in self.networks:
            for host in self.networks[network].hosts:
                hosts.append(self.networks[network].hosts[host])
        return hosts
