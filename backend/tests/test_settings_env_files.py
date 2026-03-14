from backend.config.settings import BACKEND_DIR, BACKEND_ENV_FILE, ENV_FILES


def test_env_files_are_absolute_paths():
    for p in ENV_FILES:
        assert p.is_absolute()


def test_env_files_include_backend_dotenv():
    assert ENV_FILES == (BACKEND_ENV_FILE,)
    assert BACKEND_ENV_FILE == BACKEND_DIR / ".env"
