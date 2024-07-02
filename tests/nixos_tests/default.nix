{ lib, pkgs, ... }:
let
  adminPeer-ip = "538:f40f:1c51:9bd9:9569:d3f6:d0a1:b2df";
  otherPeer-ip = "5b6:6776:fee0:c1f3:db00:b6a8:d013:d38f";
  data-mesher = pkgs.callPackage ../../default.nix { };
in
lib.nixos.runTest {
  hostPkgs = pkgs;
  name = "data-mesher";
  meta.maintainers = with lib.maintainers; [ lassulus ];

  nodes = {

    adminPeer = { ... }: {
      imports = [
        ../../module.nix
      ];
      virtualisation.vlans = [ 1 ];
      networking.interfaces.eth1.ipv4.addresses = [{
        address = "192.168.1.11";
        prefixLength = 24;
      }];

      services.mycelium = {
        enable = true;
        addHostedPublicNodes = false;
        openFirewall = true;
        keyFile = ./adminPeer.key;
        peers = [
          "quic://192.168.1.12:9651"
        ];
      };

      services.data-mesher = {
        enable = true;
        ip = adminPeer-ip;
        openFirewall = true;
        log-level = "DEBUG";
        initNetwork = true;
        tld = "test";
      };
    };

    otherPeer = { ... }: {
      imports = [
        ../../module.nix
      ];
      virtualisation.vlans = [ 1 ];
      networking.interfaces.eth1.ipv4.addresses = [{
        address = "192.168.1.12";
        prefixLength = 24;
      }];

      services.mycelium = {
        enable = true;
        addHostedPublicNodes = false;
        openFirewall = true;
        keyFile = ./otherPeer.key;
        peers = [
          "quic://192.168.1.11:9651"
        ];
      };

      services.data-mesher = {
        enable = true;
        ip = otherPeer-ip;
        bootstrapPeers = [
          "http://[${adminPeer-ip}]:7331"
        ];
        openFirewall = true;
        log-level = "DEBUG";
      };
    };
  };

  testScript = ''
    import time
    import json


    start_all()

    adminPeer.wait_for_unit("network-online.target")
    otherPeer.wait_for_unit("network-online.target")
    adminPeer.wait_for_unit("mycelium.service")
    otherPeer.wait_for_unit("mycelium.service")

    adminPeer.succeed("ping -c5 ${otherPeer-ip}")
    otherPeer.succeed("ping -c5 ${adminPeer-ip}")

    adminPeer.wait_for_unit("data-mesher.service")
    otherPeer.wait_for_unit("data-mesher.service")
    time.sleep(10)
    json_data_other = otherPeer.succeed("cat /var/lib/data-mesher/dns")
    json_data_admin = otherPeer.succeed("cat /var/lib/data-mesher/dns")
    print({
        "other": json_data_other,
        "admin": json_data_admin,
    })
    success=False
    for line in json_data_other.split("\n"):
        try:
            if "adminPeer" in json.loads(line)["hostname"]:
                success=True
        except:
            pass
    assert success, "adminPeer not found in dns file"

  '';
}
