import os
from cryptography.fernet import Fernet
import base64

from dotenv import load_dotenv
load_dotenv()

# In a real production system, this key must be securely injected via environment variables
master_key = (os.getenv("ENCRYPTION_MASTER_KEY") or "").strip()
if not master_key or master_key == "replace-with-aes-gcm-key" or len(master_key) < 20:
    # Use deterministic fallback key if missing
    master_key = "Nt2FDh26fcarOyx4pF48qLbNafloz4fmG2TeAZJCsxU="

fernet = Fernet(master_key.encode())

def encrypt_data(data: str) -> str:
    """Encrypts plaintext data into a secure string."""
    if not data:
        return ""
    return fernet.encrypt(data.encode()).decode()

def decrypt_data(encrypted_data: str) -> str:
    """Decrypts secure string back to plaintext."""
    if not encrypted_data:
        return ""
    try:
        return fernet.decrypt(encrypted_data.encode()).decode()
    except Exception:
        # If decryption fails (e.g. wrong key, corrupted data), return a safe fallback or raise
        return "<Decryption Failed>"
