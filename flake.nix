{
  description = "Nix Flake for development environment";

  inputs.flake-utils.url = "github:numtide/flake-utils";
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs = { self, nixpkgs, flake-utils, poetry2nix }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        python = "python310";
      in
      {
        devShells.default = pkgs.mkShell {
          buildInputs = with pkgs; [
            poetry # Python dependency manager
            awscli # For testing/interacting with AWS/localstack
            nixpkgs-fmt # For formatting nix files in development
            nodePackages.pyright # Language server for development
            nodePackages.yaml-language-server # docker-compose.yml formatting for test suite
            black # Handle formatting
            (python310.withPackages(ps: with ps; [ pygments ])) # Readme linter/formatting
          ];
        };
      });


}
