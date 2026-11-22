"""Launch NOVA (Neural Omnimodal Virtual Agent) with Qwen TTS."""
from nova_core.app import main, parse_config


if __name__ == "__main__":
    # Validate CLI arguments before creating the macOS runtime bundle.
    parse_config()
    from nova_core.macos import launch_in_app_bundle
    launch_in_app_bundle(__file__)
    main()
