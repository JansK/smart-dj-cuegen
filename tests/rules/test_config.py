import pytest
import textwrap
from dj_cue_system.rules.config import load_config, AppConfig


MINIMAL_YAML = textwrap.dedent("""
    rulesets:
      vocal-cue:
        rules:
          - element: first_vocal_onset
            type: memory_cue
            offset_bars: -64
            name: "Vox -64"
            color: blue
    playlists:
      Deep House:
        rulesets: [vocal-cue]
    defaults:
      rulesets: [vocal-cue]
""")


def test_load_config_parses_ruleset(tmp_path):
    cfg_file = tmp_path / "rules.yaml"
    cfg_file.write_text(MINIMAL_YAML)
    config = load_config(str(cfg_file))

    assert isinstance(config, AppConfig)
    assert "vocal-cue" in config.rulesets
    rules = config.rulesets["vocal-cue"].rules
    assert len(rules) == 1
    assert rules[0].element == "first_vocal_onset"
    assert rules[0].type == "memory_cue"
    assert rules[0].offset_bars == -64
    assert rules[0].color == "blue"


def test_load_config_playlist_mapping(tmp_path):
    cfg_file = tmp_path / "rules.yaml"
    cfg_file.write_text(MINIMAL_YAML)
    config = load_config(str(cfg_file))

    assert "Deep House" in config.playlists
    assert config.playlists["Deep House"].rulesets == ["vocal-cue"]


def test_load_config_defaults(tmp_path):
    cfg_file = tmp_path / "rules.yaml"
    cfg_file.write_text(MINIMAL_YAML)
    config = load_config(str(cfg_file))
    assert config.defaults.rulesets == ["vocal-cue"]


def test_load_config_settings_defaults(tmp_path):
    cfg_file = tmp_path / "rules.yaml"
    cfg_file.write_text(MINIMAL_YAML)
    config = load_config(str(cfg_file))
    assert config.settings.demucs_model == "htdemucs"
    assert config.settings.onset_thresholds.vocal == pytest.approx(0.02)


def test_qualifier_parsed(tmp_path):
    yaml_str = textwrap.dedent("""
        rulesets:
          break-hunter:
            rules:
              - element: break_start
                type: memory_cue
                offset_bars: -8
                name: "Break"
                qualifier:
                  position: after_midpoint
                  min_duration_bars: 16
                  occurrence: last
        defaults:
          rulesets: []
    """)
    cfg_file = tmp_path / "rules.yaml"
    cfg_file.write_text(yaml_str)
    config = load_config(str(cfg_file))

    rule = config.rulesets["break-hunter"].rules[0]
    assert rule.qualifier is not None
    assert rule.qualifier.position == "after_midpoint"
    assert rule.qualifier.min_duration_bars == 16
    assert rule.qualifier.occurrence == "last"


def test_invalid_color_raises(tmp_path):
    yaml_str = textwrap.dedent("""
        rulesets:
          bad:
            rules:
              - element: intro_start
                type: memory_cue
                offset_bars: 0
                name: "X"
                color: chartreuse
        defaults:
          rulesets: []
    """)
    cfg_file = tmp_path / "rules.yaml"
    cfg_file.write_text(yaml_str)
    with pytest.raises(Exception):
        load_config(str(cfg_file))
