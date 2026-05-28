"""
apply_data_contract.py
Upload data contracts defined in YAML files to an OpenMetadata server.

Usage:
    # Single file
    python apply_data_contract.py --yaml contracts/ecommerce/dim_customer.yaml --token <JWT>

    # All files in a flat folder
    python apply_data_contract.py --dir contracts/ecommerce/ --token <JWT>

    # All domain subfolders under a root (contracts/ecommerce/, contracts/loyalty/, ...)
    python apply_data_contract.py --domains-root contracts/ --token <JWT>

    # Authenticate with username/password
    python apply_data_contract.py --domains-root contracts/ --username admin --password admin

    # Inspect payloads without sending anything
    python apply_data_contract.py --domains-root contracts/ --token <JWT> --dry-run

Dependencies:
    pip install requests pyyaml
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

import requests
import yaml


class OMClient:
    """Wraps the OpenMetadata REST API with a persistent session."""

    def __init__(self, host: str, token: str):
        self.host = host.rstrip("/")
        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        })

    @classmethod
    def from_credentials(cls, host: str, username: str, password: str) -> "OMClient":
        resp = requests.post(
            f"{host.rstrip('/')}/api/v1/users/login",
            json={"email": username, "password": password},
            timeout=10,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"Login failed ({resp.status_code}): {resp.text}")
        token = resp.json().get("accessToken")
        print("JWT token obtained.")
        return cls(host, token)

    def health_check(self) -> bool:
        resp = self._session.get(f"{self.host}/api/v1/system/status", timeout=10)
        if resp.status_code == 200:
            print(f"OpenMetadata available at {self.host}")
            return True
        print(f"Cannot connect to OpenMetadata: {resp.status_code}")
        return False

    def get_table_by_fqn(self, fqn: str) -> Optional[dict]:
        encoded = requests.utils.quote(fqn, safe="")
        resp = self._session.get(
            f"{self.host}/api/v1/tables/name/{encoded}",
            params={"fields": "id,name,fullyQualifiedName"},
            timeout=10,
        )
        if resp.status_code == 200:
            table = resp.json()
            print(f"  Table found -> id: {table['id']}")
            return table
        print(f"  Table not found ({resp.status_code}): {resp.text}")
        return None

    def resolve_owner(self, owner: dict) -> Optional[dict]:
        if "id" in owner:
            return {"id": owner["id"], "type": owner.get("type", "user")}

        fqn = owner.get("fqn", "")
        owner_type = "user"
        if fqn.startswith("team:"):
            owner_type = "team"
            fqn = fqn.removeprefix("team:")
        elif fqn.startswith("user:"):
            fqn = fqn.removeprefix("user:")

        endpoint = "teams" if owner_type == "team" else "users"
        encoded = requests.utils.quote(fqn, safe="")
        resp = self._session.get(f"{self.host}/api/v1/{endpoint}/name/{encoded}", timeout=10)
        if resp.status_code == 200:
            entity = resp.json()
            print(f"  Owner resolved: {fqn} -> {entity['id']}")
            return {"id": entity["id"], "type": owner_type}
        print(f"  Owner not found, skipping: {fqn}")
        return None

    def upsert_contract(self, payload: dict) -> Optional[dict]:
        """PUT /api/v1/dataContracts — creates or updates (server-side upsert)."""
        yaml_body = yaml.dump(payload, allow_unicode=True, default_flow_style=False, sort_keys=False)
        resp = self._session.put(
            f"{self.host}/api/v1/dataContracts",
            data=yaml_body.encode("utf-8"),
            headers={"Content-Type": "application/yaml"},
            timeout=15,
        )
        if resp.status_code in (200, 201):
            result = resp.json()
            action = "created" if resp.status_code == 201 else "updated"
            print(f"  Contract {action} -> id: {result.get('id')}")
            return result
        print(f"  Error upserting ({resp.status_code}):\n{resp.text}")
        return None


class ContractUploader:
    """
    Processes a single YAML contract file and uploads it to OpenMetadata.

    Relies on OMClient for all network calls so it stays easy to test
    by swapping in a fake client.
    """

    _SIMPLE_FIELDS = ("displayName", "description", "entityStatus", "termsOfUse", "sourceUrl")
    _LIST_FIELDS = ("schema", "semantics", "qualityExpectations", "odcsQualityRules",
                    "tags", "domains", "dataProducts")

    def __init__(self, client: OMClient):
        self.client = client

    def upload(self, yaml_path: Path, *, dry_run: bool = False) -> bool:
        print(f"\n--- {yaml_path} ---")

        cfg = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))

        table_fqn = cfg.get("tableFQN")
        if not table_fqn:
            print("  Missing 'tableFQN' field. Skipping.")
            return False

        print(f"  tableFQN: {table_fqn}")

        table = self.client.get_table_by_fqn(table_fqn)
        if not table:
            return False

        resolved_owners = [
            ref
            for raw in (cfg.get("owners") or [])
            if (ref := self.client.resolve_owner(raw)) is not None
        ]

        payload = self._build_payload(cfg, table, resolved_owners)

        if dry_run:
            print("\n[DRY RUN] Payload to send (YAML):")
            print(yaml.dump(payload, allow_unicode=True, default_flow_style=False, sort_keys=False))
            return True

        return self.client.upsert_contract(payload) is not None

    def _build_payload(self, cfg: dict, table: dict, owners: list) -> dict:
        payload: dict = {
            "name": cfg["name"],
            "entity": {
                "id": table["id"],
                "type": "table",
                "fullyQualifiedName": table.get("fullyQualifiedName", cfg.get("tableFQN", "")),
            },
            "owners": owners,
            "reviewers": [],
        }
        for field in self._SIMPLE_FIELDS:
            if field in cfg:
                payload[field] = cfg[field]
        for field in self._LIST_FIELDS:
            if field == "semantics" and cfg.get("semantics"):
                # enabled is required by the schema; default True if omitted in YAML
                payload["semantics"] = [
                    {**rule, "enabled": rule.get("enabled", True)}
                    for rule in cfg["semantics"]
                ]
            elif cfg.get(field):
                payload[field] = cfg[field]
        for field in ("effectiveFrom", "effectiveUntil"):
            if cfg.get(field):
                payload[field] = cfg[field]
        if cfg.get("sla"):
            payload["sla"] = self._migrate_sla(cfg["sla"])
        return payload

    @staticmethod
    def _migrate_sla(sla: dict) -> dict:
        # Migrate old schema {unitOfTime, value} → new {refreshFrequency: {interval, unit}}
        if "unitOfTime" in sla and "refreshFrequency" not in sla:
            return {
                "refreshFrequency": {
                    "interval": sla.get("value", 1),
                    "unit": sla["unitOfTime"].lower(),
                }
            }
        return sla


class DomainScanner:
    """
    Discovers contract YAML files under three layouts:

    - Single file  : --yaml path/to/contract.yaml
    - Flat folder  : --dir contracts/ecommerce/
    - Domain tree  : --domains-root contracts/
                       contracts/
                       ├── ecommerce/
                       │   ├── dim_customer.yaml
                       │   └── fact_orders.yaml
                       └── loyalty/
                           └── dim_loyalty.yaml
    """

    def collect(
        self,
        *,
        yaml_file: Optional[str] = None,
        directory: Optional[str] = None,
        domains_root: Optional[str] = None,
    ) -> list[Path]:
        if yaml_file:
            return [Path(yaml_file)]

        if directory:
            return self._glob_dir(Path(directory))

        if domains_root:
            root = Path(domains_root)
            files: list[Path] = []
            for domain_dir in sorted(root.iterdir()):
                if domain_dir.is_dir():
                    domain_files = self._glob_dir(domain_dir)
                    if domain_files:
                        print(f"Domain '{domain_dir.name}': {len(domain_files)} file(s)")
                    files.extend(domain_files)
            return files

        return []

    @staticmethod
    def _glob_dir(path: Path) -> list[Path]:
        return sorted(path.glob("*.yaml")) + sorted(path.glob("*.yml"))


def main():
    parser = argparse.ArgumentParser(
        description="Upload Data Contracts from YAML files to OpenMetadata.",
        formatter_class=argparse.RawTextHelpFormatter,
    )

    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--yaml", metavar="FILE", help="Path to a single YAML contract file")
    source.add_argument("--dir", metavar="DIR", help="Folder containing YAML contract files")
    source.add_argument("--domains-root", metavar="DIR",
                        help="Root folder with domain subfolders each containing YAML files")

    parser.add_argument("--host", default="http://localhost:8585",
                        help="OpenMetadata base URL (default: http://localhost:8585)")
    parser.add_argument("--token", help="JWT token")
    parser.add_argument("--username", help="OpenMetadata username")
    parser.add_argument("--password", help="OpenMetadata password")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print payloads without sending anything to the API")

    args = parser.parse_args()

    # Auth
    try:
        if args.token:
            client = OMClient(args.host, args.token)
        elif args.username and args.password:
            client = OMClient.from_credentials(args.host, args.username, args.password)
        else:
            print("Provide --token or both --username and --password.")
            sys.exit(1)
    except RuntimeError as e:
        print(e)
        sys.exit(1)

    if not args.dry_run and not client.health_check():
        sys.exit(1)

    # Collect files
    yaml_files = DomainScanner().collect(
        yaml_file=args.yaml,
        directory=args.dir,
        domains_root=args.domains_root,
    )
    if not yaml_files:
        print("No YAML files found.")
        sys.exit(1)

    print(f"Found {len(yaml_files)} file(s) to process.")

    # Upload
    uploader = ContractUploader(client)
    ok = fail = 0
    for path in yaml_files:
        if uploader.upload(path, dry_run=args.dry_run):
            ok += 1
        else:
            fail += 1

    print(f"\n{'=' * 60}")
    print(f"Summary: {ok} succeeded, {fail} failed")
    print(f"{'=' * 60}")

    if fail > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
