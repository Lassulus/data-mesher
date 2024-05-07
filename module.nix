{ lib, pkgs, config, ... }:
let
  cfg = config.services.data-mesher;
in
{
  options.services.data-mesher = {
    enable = lib.mkEnableOption "data-mesher, data syncing daemon";
    package = lib.mkOption {
      type = lib.types.package;
      default = pkgs.callPackage ./default.nix { };
    };
    bootstrapPeers = lib.mkOption {
      type = lib.types.listOf lib.types.str;
      default = [ ];
      description = "List of bootstrap peers to connect to";
    };
    port = lib.mkOption {
      type = lib.types.int;
      default = 7331;
      description = "Port to listen on";
    };
    ip = lib.mkOption {
      type = lib.types.str;
      description = "ip address to bind to and used to identify ourself in the network, this can't be 0.0.0.0 or ::";
    };
    log-level = lib.mkOption {
      type = lib.types.enum [ "DEBUG" "INFO" ];
      default = "INFO";
      description = "Log level";
    };
    openFirewall = lib.mkEnableOption "open port in firewall";
  };
  config = lib.mkIf cfg.enable {
    networking.firewall.allowedTCPPorts = lib.mkIf cfg.openFirewall [ cfg.port ];
    systemd.services.data-mesher = {
      description = "data-mesher data syncing daemon";
      wantedBy = [ "multi-user.target" ];
      after = [ "network.target" ];
      serviceConfig = {
        ExecStart = pkgs.writers.writeBash "data-mesher" ''
          ${cfg.package}/bin/data-mesher \
            --ip ${cfg.ip} \
            --port ${toString cfg.port} \
            --key-file "$STATE_DIRECTORY"/key \
            --log-level ${cfg.log-level} \
            ${lib.concatMapStringsSep " " (peer: "--bootstrap-peer ${peer}") cfg.bootstrapPeers} \
            server
        '';
        DynamicUser = true;
        StateDirectory = "data-mesher";
      };
    };
  };
}
