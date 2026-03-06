from backend.config.settings import ENV_FILES, PROJECT_ROOT


def test_env_files_are_absolute_paths():
    for p in ENV_FILES:
        assert p.is_absolute()


def test_env_files_include_project_root_dotenv():
    assert ENV_FILES[0] == PROJECT_ROOT / ".env"
