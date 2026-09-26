import pytest

from btcintel.chain.validate import (
    address_type,
    classify_query,
    is_address,
    is_txid,
    normalize_address,
)

VALID = {
    "bc1qqqqsyqcyq5rqwzqfpg9scrgwpugpzysn4v0345": "v0_p2wpkh",
    "bc1qqqqsyqcyq5rqwzqfpg9scrgwpugpzysnzs23v9ccrydpk8qarc0szrtjt7": "v0_p2wsh",
    "bc1pqqqsyqcyq5rqwzqfpg9scrgwpugpzysnzs23v9ccrydpk8qarc0sg5tmnz": "v1_p2tr",
    "112D2adLM3UKy4Z4giRbReR6gjWuvHUqB": "p2pkh",
    "31h38a54tFMrR8kzBnP2241MFD2EUHtGha": "p2sh",
    "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa": "p2pkh",  # genesis coinbase
    "bc1qntndgqfx46wks63jep34cjk3pw63es86kp45c6": "v0_p2wpkh",  # mainnet, block 900000
    "3NDzzVxiLBUs1WPvVGRfCYDTAD2Ua2PvW4": "p2sh",
}

INVALID = [
    "bc1qqqqsyqcyq5rqwzqfpg9scrgwpugpzysn4v0344",  # bad checksum
    "bc1qqqqsyqcyq5rqwzqfpg9scrgwpugpzysn4V0345",  # mixed case
    "bc1pqqqsyqcyq5rqwzqfpg9scrgwpugpzysnzs23v9ccrydpk8qarc0sagmhkq",  # v1 with bech32 (needs bech32m)
    "bc1qqqqsyqcyq5rqwzqfpg9scrgwpugpzysnqslask",  # v0 with bech32m (needs bech32)
    "tb1qqqqsyqcyq5rqwzqfpg9scrgwpugpzysnl25zw8",  # testnet
    "bc1qqqqsyqcyq5rqwzqfpg9scrgwpugpzysnzs23v9cc7vgsh7",  # v0 program of 25 bytes
    "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNb",  # base58 checksum
    "1A1zP1eP5QGefi2DMPTfTL5SLmv7Divf0a",  # '0' is not base58
    "",
    "hello",
    "0x252a8bd2319d8a555b872990601221b3a2053bce",  # ethereum
    " 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",  # leading space
]

TXID = "c5908e04daea83ec38101692a0663130bcafa7d0ddaef1fd8821d179d1db1c8c"


@pytest.mark.parametrize("addr,expected", VALID.items())
def test_valid_addresses(addr, expected):
    assert address_type(addr) == expected
    assert is_address(addr)


@pytest.mark.parametrize("addr", INVALID)
def test_invalid_addresses(addr):
    assert address_type(addr) is None
    assert not is_address(addr)


def test_uppercase_bech32_is_valid_and_normalizes_to_lowercase():
    upper = "BC1QQQQSYQCYQ5RQWZQFPG9SCRGWPUGPZYSN4V0345"
    assert address_type(upper) == "v0_p2wpkh"
    assert normalize_address(upper) == upper.lower()
    assert normalize_address("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa") == "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"


def test_is_txid():
    assert is_txid(TXID)
    assert is_txid(TXID.upper())
    assert not is_txid(TXID[:-1])
    assert not is_txid(TXID[:-1] + "g")


def test_classify_query():
    assert classify_query(TXID.upper()) == ("txid", TXID)
    assert classify_query(f" {TXID}:3 ") == ("outpoint", f"{TXID}:3")
    assert classify_query(f"{TXID}:x") == ("text", f"{TXID}:x")
    assert classify_query(" bc1qntndgqfx46wks63jep34cjk3pw63es86kp45c6 ") == (
        "address",
        "bc1qntndgqfx46wks63jep34cjk3pw63es86kp45c6",
    )
    assert classify_query("Lazarus") == ("text", "Lazarus")
