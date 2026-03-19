"""Bidirectional conversion between libp2p PeerIDs and W3C did:key identifiers.

The did:key method encodes an Ed25519 public key as::

    did:key:z<base58btc(multicodec_prefix + raw_public_key)>

where the multicodec prefix for Ed25519 is ``0xed01`` (varint-encoded 0xed).

This module provides pure-Python implementations that produce identical
output to the Go daemon's ``crypto.PeerIDToDIDKey`` / ``DIDKeyToPeerID``.
"""

from __future__ import annotations

import base58

# Ed25519 multicodec varint prefix.
_ED25519_MULTICODEC_PREFIX = bytes([0xED, 0x01])

# libp2p identity multihash code (used for Ed25519 PeerIDs).
_IDENTITY_MULTIHASH_CODE = 0x00

# Protobuf field tag for Ed25519 public key in libp2p's crypto.pb.
# PeerID = multihash(identity, protobuf(type=Ed25519, data=pubkey))
_PROTOBUF_ED25519_TYPE = 1
_PROTOBUF_DATA_FIELD = 2


def peer_id_to_did_key(peer_id: str) -> str:
    """Convert a libp2p PeerID (base58btc-encoded) to a ``did:key`` string.

    Only Ed25519-based PeerIDs are supported. These are encoded with the
    identity multihash and directly embed the public key.

    Args:
        peer_id: Base58btc-encoded libp2p PeerID (e.g., ``12D3KooW...``).

    Returns:
        A ``did:key:z...`` string.

    Raises:
        ValueError: If the PeerID is not a valid Ed25519-based identity.
    """
    raw = base58.b58decode(peer_id)

    # libp2p PeerIDs for Ed25519 use identity multihash:
    # <varint:0x00> <varint:length> <protobuf-encoded-public-key>
    if len(raw) < 2 or raw[0] != _IDENTITY_MULTIHASH_CODE:
        raise ValueError(f"unsupported PeerID format (expected identity multihash): {peer_id}")

    # Read varint length (single byte is safe: Ed25519 protobuf is 36 bytes, always < 128).
    length = raw[1]
    proto_bytes = raw[2 : 2 + length]

    # Parse the minimal protobuf: field 1 (type) = Ed25519 (1), field 2 (data) = raw key.
    pubkey = _parse_libp2p_pubkey_proto(proto_bytes)

    # Encode as did:key.
    mc_bytes = _ED25519_MULTICODEC_PREFIX + pubkey
    return "did:key:z" + str(base58.b58encode(mc_bytes).decode("ascii"))


def did_key_to_peer_id(did_key: str) -> str:
    """Convert a ``did:key`` string back to a libp2p PeerID.

    Args:
        did_key: A ``did:key:z...`` string (Ed25519 only).

    Returns:
        Base58btc-encoded libp2p PeerID.

    Raises:
        ValueError: If the did:key is malformed or uses an unsupported key type.
    """
    if not did_key.startswith("did:key:z"):
        raise ValueError(f"invalid did:key format: {did_key}")

    encoded = did_key[len("did:key:z") :]
    decoded = base58.b58decode(encoded)

    if len(decoded) < len(_ED25519_MULTICODEC_PREFIX) + 32:
        raise ValueError("did:key payload too short")

    prefix = decoded[: len(_ED25519_MULTICODEC_PREFIX)]
    if prefix != _ED25519_MULTICODEC_PREFIX:
        raise ValueError("unsupported multicodec prefix (only Ed25519 supported)")

    pubkey = decoded[len(_ED25519_MULTICODEC_PREFIX) :]

    # Reconstruct the libp2p protobuf-encoded public key.
    proto_bytes = _encode_libp2p_pubkey_proto(pubkey)

    # Wrap in identity multihash: <0x00> <length> <data>
    mh = bytes([_IDENTITY_MULTIHASH_CODE, len(proto_bytes)]) + proto_bytes
    return str(base58.b58encode(mh).decode("ascii"))


def _parse_libp2p_pubkey_proto(data: bytes) -> bytes:
    """Parse a minimal libp2p crypto.pb.PublicKey protobuf to extract the raw key."""
    # Field 1 (KeyType): varint, should be 1 (Ed25519)
    # Field 2 (Data): length-delimited, the raw public key bytes
    idx = 0
    key_type = None
    key_data = None

    while idx < len(data):
        # Read field tag.
        tag = data[idx]
        idx += 1
        field_number = tag >> 3
        wire_type = tag & 0x07

        if wire_type == 0:  # varint
            val = 0
            shift = 0
            while idx < len(data):
                b = data[idx]
                idx += 1
                val |= (b & 0x7F) << shift
                if b < 0x80:
                    break
                shift += 7
            if field_number == 1:
                key_type = val
        elif wire_type == 2:  # length-delimited
            length = data[idx]
            idx += 1
            if field_number == 2:
                key_data = data[idx : idx + length]
            idx += length

    if key_type != _PROTOBUF_ED25519_TYPE:
        raise ValueError(f"unsupported key type {key_type} (expected Ed25519=1)")
    if key_data is None or len(key_data) != 32:
        raise ValueError("invalid Ed25519 public key data")

    return key_data


def _encode_libp2p_pubkey_proto(pubkey: bytes) -> bytes:
    """Encode a raw Ed25519 public key as libp2p crypto.pb.PublicKey protobuf."""
    # Field 1 (KeyType=Ed25519=1): tag=0x08, value=0x01
    # Field 2 (Data): tag=0x12, length, data
    return bytes([0x08, 0x01, 0x12, len(pubkey)]) + pubkey
