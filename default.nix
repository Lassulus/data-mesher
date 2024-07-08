{ pkgs ? import <nixpkgs> { }
}:
let
  aiohttp = pkgs.python3.pkgs.aiohttp.overrideAttrs (old: {
    name = "aiohttp-master_2024-05-07";
    src = pkgs.fetchFromGitHub {
      owner = "aio-libs";
      repo = "aiohttp";
      rev = "2eccb8b47ff7c77596955071cfb4dbbd5dfe63d5";
      sha256 = "sha256-3/dDUiC9+2zvzP0VTZAEmZwjDXBHeOEqyMXL8BW9we0=";
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
