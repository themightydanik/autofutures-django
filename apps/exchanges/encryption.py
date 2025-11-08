# ===== apps/exchanges/encryption.py =====
from cryptography.fernet import Fernet
from django.conf import settings
import base64
import hashlib

class EncryptionService:
    """Service for encrypting/decrypting API keys"""
    
    def __init__(self):
        # Generate key from settings
        key = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
        self.cipher = Fernet(base64.urlsafe_b64encode(key))
    
    def encrypt(self, text: str) -> str:
        """Encrypt text"""
        if not text:
            return ''
        return self.cipher.encrypt(text.encode()).decode()
    
    def decrypt(self, encrypted_text: str) -> str:
        """Decrypt text"""
        if not encrypted_text:
            return ''
        return self.cipher.decrypt(encrypted_text.encode()).decode()

encryption_service = EncryptionService()
