{ pkgs ? import <nixpkgs> { }
}:


pkgs.python3.pkgs.buildPythonApplication {
  pname = "data-mesher";
  version = "1.0.0";
  src = ./.;
  format = "pyproject";
  buildInputs = [ pkgs.makeWrapper ];
  propagatedBuildInputs = [
    pkgs.python3Packages.aiohttp
    pkgs.python3Packages.pynacl
  ];
  nativeBuildInputs = [ pkgs.python311.pkgs.setuptools ];
  nativeCheckInputs = [
    pkgs.python311.pkgs.pytest
    # technically not test inputs, but we need it for development in PATH
    pkgs.nixVersions.stable
    pkgs.nix-prefetch-git
  ];
  checkPhase = ''
    PYTHONPATH= $out/bin/data-mesher --help
  '';
  shellHook = ''
    # workaround because `python setup.py develop` breaks for me
  '';
}
