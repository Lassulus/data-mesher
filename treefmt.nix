{ lib, inputs, ... }:
{
  imports = [ inputs.treefmt-nix.flakeModule ];

  perSystem =
    { pkgs, ... }:
    {
      treefmt = {
        # Used to find the project root
        projectRootFile = ".git/config";

        programs.prettier.enable = true;
        programs.mypy.enable = true;
        programs.nixfmt.enable = true;
        programs.nixfmt.package = pkgs.nixfmt-rfc-style;
        programs.deadnix.enable = true;

        settings.formatter = {
          python = {
            command = "sh";
            options = [
              "-eucx"
              ''
                ${lib.getExe pkgs.ruff} check --fix "$@"
                ${lib.getExe pkgs.ruff} format "$@"
              ''
              "--" # this argument is ignored by bash
            ];
            includes = [ "*.py" ];
          };
        };
      };
    };
}
