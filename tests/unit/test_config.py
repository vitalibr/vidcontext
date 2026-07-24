from pathlib import Path

from vidcontext.config import load_config


def test_defaults_when_nothing_provided():
    config = load_config()
    assert config.transcriber == "mock"
    assert config.transcription_language == "auto"
    assert config.force is False


def test_env_overrides_defaults():
    env = {"VIDCONTEXT_TRANSCRIBER": "base", "VIDCONTEXT_TRANSCRIPTION_LANGUAGE": "pt"}
    config = load_config(env=env)
    assert config.transcriber == "base"
    assert config.transcription_language == "pt"


def test_file_overrides_defaults_but_not_env(tmp_path: Path):
    config_file = tmp_path / "config.toml"
    config_file.write_text('transcriber = "small"\ntranscription_language = "es"\n')

    config = load_config(config_file=config_file, env={"VIDCONTEXT_TRANSCRIBER": "base"})

    assert config.transcriber == "base"  # env vence o arquivo
    assert config.transcription_language == "es"  # arquivo vence o default


def test_cli_overrides_win_over_everything(tmp_path: Path):
    config_file = tmp_path / "config.toml"
    config_file.write_text('transcriber = "small"\n')

    config = load_config(
        config_file=config_file,
        env={"VIDCONTEXT_TRANSCRIBER": "base"},
        cli_overrides={"transcriber": "tiny"},
    )

    assert config.transcriber == "tiny"


def test_cli_none_values_do_not_override():
    config = load_config(
        env={"VIDCONTEXT_TRANSCRIBER": "base"},
        cli_overrides={"transcriber": None},
    )
    assert config.transcriber == "base"


def test_bool_and_numeric_env_coercion():
    config = load_config(
        env={"VIDCONTEXT_VERBOSE": "true", "VIDCONTEXT_MAX_FILE_SIZE_BYTES": "1024"}
    )
    assert config.verbose is True
    assert config.max_file_size_bytes == 1024
