{
  lib,
  pkgs,
  config,
  ...
}:
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
    hostnames = lib.mkOption {
      type = lib.types.listOf lib.types.str;
      default = [ config.networking.hostName ];
      defaultText = [ (lib.literalExpression "config.networking.hostName") ];
      description = "host to bind to";
    };
    log-level = lib.mkOption {
      type = lib.types.enum [
        "DEBUG"
        "INFO"
      ];
      default = "INFO";
      description = "Log level";
    };
    tld = lib.mkOption {
      type = lib.types.str;
      default = config.networking.domain;
      description = "Top level domain to use for the network";
    };
    openFirewall = lib.mkEnableOption "open port in firewall";
    initNetwork = lib.mkEnableOption "initialize networks on startup";
  };
  config = lib.mkIf cfg.enable {
    networking.firewall.allowedTCPPorts = lib.mkIf cfg.openFirewall [ cfg.port ];
    systemd.services.data-mesher = {
      description = "data-mesher data syncing daemon";
      wantedBy = [ "multi-user.target" ];
      after = [
        "network.target"
        "nsncd.service"
      ];
      serviceConfig = {
        ExecStart = pkgs.writers.writeBash "data-mesher" ''
          ${lib.optionalString cfg.initNetwork ''
            ${cfg.package}/bin/data-mesher \
              --ip ${cfg.ip} \
              --port ${toString cfg.port} \
              --key-file "$STATE_DIRECTORY"/key \
              --state-file "$STATE_DIRECTORY"/state \
              --log-level ${cfg.log-level} \
              --tld ${cfg.tld} \
              create
          ''}

          ${cfg.package}/bin/data-mesher \
            --ip ${cfg.ip} \
            --port ${toString cfg.port} \
            --key-file "$STATE_DIRECTORY"/key \
            --state-file "$STATE_DIRECTORY"/state \
            --dns-file "$STATE_DIRECTORY"/dns \
            --log-level ${cfg.log-level} \
            ${lib.concatMapStringsSep " " (hostname: "--hostname ${hostname}") cfg.hostnames} \
            ${lib.concatMapStringsSep " " (peer: "--bootstrap-peer ${peer}") cfg.bootstrapPeers} \
            server
        '';
        DynamicUser = true;
        StateDirectory = "data-mesher";
        WorkingDirectory = "/var/lib/data-mesher";
      };
    };
  };
}
