{ pkgs ? import <nixpkgs> { }
}:
let
  aiohttp = pkgs.python3.pkgs.aiohttp.overrideAttrs (old: {
    name = "aiohttp-unstable-2024-06-06";
    src = pkgs.fetchFromGitHub {
      owner = "aio-libs";
      repo = "aiohttp";
      rev = "98eec45100822cc1092b7ea1fc9f734912cd2c82";
      sha256 = "sha256-eiYN1eBgKh/nysoKZrm3wXnJDIkA7uaXIokaj8IyQl4=";
    };
    propagatedBuildInputs = old.propagatedBuildInputs ++ [
      pkgs.python3.pkgs.aiohappyeyeballs
    ];
  });
in
pkgs.python3.pkgs.buildPythonApplication {
  pname = "data-mesher";
  version = "1.0.0";
  src = ./.;
  format = "pyproject";
  buildInputs = [ pkgs.makeWrapper ];
  propagatedBuildInputs = [
    aiohttp
    pkgs.python3Packages.pynacl
  ];
  nativeBuildInputs = [ pkgs.python3.pkgs.setuptools ];
  nativeCheckInputs = [
    pkgs.python3.pkgs.pytest
    pkgs.python3.pkgs.pytest-asyncio
  ];
  checkPhase = ''
    PYTHONPATH= $out/bin/data-mesher --help
  '';
  shellHook = ''
    # workaround because `python setup.py develop` breaks for me
  '';
}
