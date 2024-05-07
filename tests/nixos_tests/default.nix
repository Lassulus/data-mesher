{ lib, pkgs, ... }:
let
  adminPeer-ip = "538:f40f:1c51:9bd9:9569:d3f6:d0a1:b2df";
  otherPeer-ip = "5b6:6776:fee0:c1f3:db00:b6a8:d013:d38f";
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
    start_all()

    adminPeer.wait_for_unit("network-online.target")
    otherPeer.wait_for_unit("network-online.target")
    adminPeer.wait_for_unit("mycelium.service")
    otherPeer.wait_for_unit("mycelium.service")

    adminPeer.succeed("ping -c5 ${otherPeer-ip}")
    otherPeer.succeed("ping -c5 ${adminPeer-ip}")

    # adminPeer.wait_for_unit("data-mesher.service")
    # otherPeer.wait_for_unit("data-mesher.service")
    import time
    time.sleep(25)
    otherPeer.execute("journalctl -u data-mesher.service >&2")
  '';
}
