import pytest

from btcintel.config import DEFAULT_BACKENDS, load_settings, parse_backends


def test_default_backends():
    mempool, blockstream = parse_backends(DEFAULT_BACKENDS)
    assert (mempool.name, mempool.base_url, mempool.rate_per_sec, mempool.burst) == (
        "mempool", "https://mempool.space/api", 1.0, 1,
    )
    assert mempool.supports_price
    assert (blockstream.name, blockstream.rate_per_sec, blockstream.burst) == ("blockstream", 4.0, 4)
    assert not blockstream.supports_price


def test_self_hosted_backend_with_price_and_trailing_slash():
    (local,) = parse_backends("local=http://10.0.0.5:3006/api/@25+price")
    assert local.base_url == "http://10.0.0.5:3006/api"
    assert local.rate_per_sec == 25.0 and local.burst == 25 and local.supports_price


@pytest.mark.parametrize("spec", ["", "nourl", "x=http://a@0", "x=http://a", "x=http://a@abc"])
def test_invalid_backend_specs(spec):
    with pytest.raises(ValueError):
        parse_backends(spec)


def test_load_settings_from_env(tmp_path):
    s = load_settings({
        "BTCINTEL_DATA_DIR": str(tmp_path),
        "BTCINTEL_PROXY": "socks5h://127.0.0.1:9050",
        "BTCINTEL_PORT": "9999",
    })
    assert s.data_dir == tmp_path
    assert s.cache_path == tmp_path / "cache.db" and s.intel_path == tmp_path / "intel.db"
    assert s.proxy == "socks5h://127.0.0.1:9050"
    assert (s.host, s.port) == ("127.0.0.1", 9999)
    assert s.backends[0].name == "mempool"


def test_load_settings_defaults_point_into_repo():
    s = load_settings({})
    assert s.catalog_dir.name == "catalog" and s.kb_dir.parts[-2:] == ("docs", "kb")
    assert s.proxy is None
