import base64
import hashlib
import os
from typing import Tuple

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi import HTTPException

from app.core.config import settings


class LocalKeyEncryptionService:
    """Development KMS abstraction for envelope encryption."""
    
    def __init__(self):
        # Decode the 32-byte hex master key from config
        try:
            self._master_key = bytes.fromhex(settings.ENCRYPTION_MASTER_KEY)
            if len(self._master_key) != 32:
                raise ValueError("Master key must be exactly 32 bytes")
        except ValueError:
            raise RuntimeError("Invalid ENCRYPTION_MASTER_KEY in configuration")
            
        self._master_aead = AESGCM(self._master_key)

    def generate_dek(self) -> Tuple[bytes, str]:
        """Generate a random DEK and return (plaintext_dek, base64_encrypted_dek)."""
        dek = AESGCM.generate_key(bit_length=256)
        nonce = os.urandom(12)
        # Encrypt the DEK with the master key
        encrypted_dek_bytes = self._master_aead.encrypt(nonce, dek, None)
        # We prepend the nonce to the encrypted DEK to store them together
        b64_encrypted_dek = base64.b64encode(nonce + encrypted_dek_bytes).decode('utf-8')
        return dek, b64_encrypted_dek

    def decrypt_dek(self, b64_encrypted_dek: str) -> bytes:
        """Decrypt the DEK using the master key."""
        try:
            encrypted_data = base64.b64decode(b64_encrypted_dek)
            nonce = encrypted_data[:12]
            ciphertext = encrypted_data[12:]
            return self._master_aead.decrypt(nonce, ciphertext, None)
        except Exception:
            raise ValueError("Failed to decrypt DEK")


key_provider = LocalKeyEncryptionService()


def encrypt_artifact(plaintext: bytes, dek: bytes) -> Tuple[bytes, str, str, str]:
    """
    Encrypts artifact data using AES-256-GCM.
    Returns: (ciphertext, b64_nonce, b64_tag, b64_checksum)
    """
    aead = AESGCM(dek)
    nonce = os.urandom(12)
    # Encrypt the plaintext. AESGCM appends the 16-byte authentication tag to the ciphertext.
    encrypted_data = aead.encrypt(nonce, plaintext, None)
    
    # Split the ciphertext and tag
    ciphertext = encrypted_data[:-16]
    tag = encrypted_data[-16:]
    
    b64_nonce = base64.b64encode(nonce).decode('utf-8')
    b64_tag = base64.b64encode(tag).decode('utf-8')
    
    # SHA-256 of the ciphertext
    sha256 = hashlib.sha256()
    sha256.update(ciphertext)
    b64_checksum = base64.b64encode(sha256.digest()).decode('utf-8')
    
    return ciphertext, b64_nonce, b64_tag, b64_checksum


def decrypt_artifact(ciphertext: bytes, dek: bytes, b64_nonce: str, b64_tag: str) -> bytes:
    """
    Decrypts artifact data using AES-256-GCM.
    """
    try:
        aead = AESGCM(dek)
        nonce = base64.b64decode(b64_nonce)
        tag = base64.b64decode(b64_tag)
        # Reconstruct the encrypted payload that AESGCM expects
        encrypted_data = ciphertext + tag
        return aead.decrypt(nonce, encrypted_data, None)
    except Exception:
        raise HTTPException(status_code=400, detail="Artifact decryption failed or data tampered")
