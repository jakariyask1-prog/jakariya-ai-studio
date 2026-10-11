"""Utility to inspect provider API Key readiness."""

from app.providers.manager.provider_manager import ProviderManager
from app.providers.manager.provider_registry import ProviderRegistry
from app.utils.paths import load_environment


def main():
    load_environment()
    mgr = ProviderManager.instance()
    print("=" * 65)
    print(f"{'PROVIDER NAME':<25} | {'PROVIDER ID':<15} | {'API KEY STATUS':<15}")
    print("=" * 65)

    for p_id in mgr.list_providers():
        provider = mgr.get_provider(p_id)
        is_valid = provider.validate_api_key() if provider else False
        status_str = "[VALID / READY]" if is_valid else "[MISSING / UNSET]"
        meta = ProviderRegistry.get_provider_meta(p_id)
        name = meta.name if meta else p_id
        print(f"{name:<25} | {p_id:<15} | {status_str:<15}")

    print("=" * 65)


if __name__ == "__main__":
    main()
