{
  description = "Development environment for the Lobbyregister ingestion stack";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = {
    self,
    nixpkgs,
    flake-utils,
  }:
    flake-utils.lib.eachDefaultSystem (system: let
      pkgs = import nixpkgs {
        inherit system;
        config = {allowUnfree = true;};
      };
      python = pkgs.python313;
    in {
      devShells.default = pkgs.mkShell {
        packages = with pkgs; [
          uv
          python
          docker-compose
          docker-buildx
          ruff
        ];

        shellHook = ''
          export UV_PROJECT_ROOT="$PWD"
          export UV_PYTHON="${python}/bin/python3"
          export UV_NO_SYNC_PROGRESS=1
          if [ ! -d .venv ]; then
            echo "[flake] Creating virtualenv via uv..."
            uv sync --python "$UV_PYTHON"
          fi
          if [ -f .venv/bin/activate ]; then
            # shellcheck disable=SC1091
            source .venv/bin/activate
          fi
        '';
      };
    });
}
