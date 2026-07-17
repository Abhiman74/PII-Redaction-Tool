import hashlib
import logging
from typing import Dict, Tuple
from faker import Faker
from datetime import datetime
from dateutil import parser as date_parser

logger = logging.getLogger(__name__)

class PIIReplacer:
    """
    Handles deterministic mapping and replacement of PII text with realistic fake data.
    """
    def __init__(self, locale: str = "en_US"):
        self.fake = Faker(locale)
        # Store in-memory mapping to ensure strict consistency in a single run
        self.mapping: Dict[Tuple[str, str], str] = {}

    def _get_stable_seed(self, text: str) -> int:
        """
        Generate a stable integer seed from a text string using MD5.
        """
        hash_object = hashlib.md5(text.encode("utf-8"))
        # Use modulo to fit within 32-bit integer range for Faker seeding
        return int(hash_object.hexdigest(), 16) % (10**8)

    def get_replacement(self, original_text: str, entity_type: str) -> str:
        """
        Get a deterministic fake replacement for the given PII text and entity type.
        """
        key = (original_text.strip(), entity_type)
        if key in self.mapping:
            return self.mapping[key]

        # Seed Faker instance with a stable seed derived from the original text
        seed = self._get_stable_seed(original_text)
        self.fake.seed_instance(seed)

        replacement = ""
        
        # Dispatch based on entity type
        if entity_type == "PERSON":
            replacement = self.fake.name()
        elif entity_type == "EMAIL_ADDRESS":
            # Extract parts or generate standard fake email
            username = self.fake.user_name()
            # Try to preserve domain if it is a corporate domain
            if "@" in original_text:
                parts = original_text.split("@")
                domain = parts[1].lower()
                if domain in ["gmail.com", "yahoo.com", "hotmail.com", "outlook.com"]:
                    replacement = f"{username}@example.com"
                else:
                    # Keep corporate domains looking realistic (e.g. kshinternational.com -> globaltech.com)
                    domain_seed = self._get_stable_seed(domain)
                    Faker().seed_instance(domain_seed)
                    fake_company_domain = Faker().domain_name()
                    replacement = f"{username}@{fake_company_domain}"
            else:
                replacement = f"{username}@example.com"
        elif entity_type == "PHONE_NUMBER":
            # Detect if it starts with +91 (Indian number) or other prefixes
            cleaned = "".join(c for c in original_text if c.isdigit())
            if original_text.startswith("+91") or (len(cleaned) == 12 and cleaned.startswith("91")):
                # Generate a realistic Indian mobile or landline number
                # Faker seed will make it deterministic
                suffix = "".join(str(self.fake.random_digit()) for _ in range(8))
                # Preserve prefix and area codes if present
                if " 20 " in original_text or "-20-" in original_text or " 22 " in original_text:
                    area = "20" if "20" in original_text else "22"
                    replacement = f"+91 {area} 4{suffix[:7]}"
                else:
                    replacement = f"+91 9{suffix}0"
            else:
                replacement = self.fake.phone_number()
        elif entity_type in ["ORG", "COMPANY"]:
            replacement = self.fake.company()
            # If the original has corporate suffix, try to match it
            orig_lower = original_text.lower()
            if "limited" in orig_lower or "ltd" in orig_lower:
                if "private" in orig_lower or "pvt" in orig_lower:
                    replacement += " Pvt Ltd"
                else:
                    replacement += " Limited"
            elif "llp" in orig_lower:
                replacement += " LLP"
            elif "inc" in orig_lower:
                replacement += " Inc."
        elif entity_type in ["GPE", "LOCATION", "LOC", "FAC"]:
            replacement = self.fake.city()
        elif entity_type == "POSTAL_CODE":
            # Generates a 6-digit postal code for India or 5-digit for US
            if len(original_text.replace(" ", "")) == 6:
                replacement = f"{self.fake.random_int(100, 999)} {self.fake.random_int(100, 999)}"
            else:
                replacement = self.fake.postcode()
        elif entity_type == "CREDIT_CARD":
            replacement = self.fake.credit_card_number()
        elif entity_type == "US_SSN":
            replacement = self.fake.ssn()
        elif entity_type == "IP_ADDRESS":
            if ":" in original_text:
                replacement = self.fake.ipv6()
            else:
                replacement = self.fake.ipv4()
        elif entity_type == "INDIAN_PAN":
            # PAN Card format: 5 letters, 4 numbers, 1 letter
            letters1 = "".join(self.fake.random_uppercase_letter() for _ in range(5))
            digits = "".join(str(self.fake.random_digit()) for _ in range(4))
            letter2 = self.fake.random_uppercase_letter()
            replacement = f"{letters1}{digits}{letter2}"
        elif entity_type in ["DATE_OF_BIRTH", "DATE"]:
            try:
                # Try to parse and match the date format
                parsed_date = date_parser.parse(original_text)
                fake_year = self.fake.random_int(1970, 2010)
                fake_month = self.fake.random_int(1, 12)
                fake_day = self.fake.random_int(1, 28)
                fake_dt = datetime(fake_year, fake_month, fake_day)
                
                # Check formatting style
                if "-" in original_text:
                    if len(original_text.split("-")[0]) == 4:
                        replacement = fake_dt.strftime("%Y-%m-%d")
                    else:
                        replacement = fake_dt.strftime("%d-%m-%Y")
                elif "/" in original_text:
                    if len(original_text.split("/")[2]) == 4:
                        replacement = fake_dt.strftime("%m/%d/%Y")
                    else:
                        replacement = fake_dt.strftime("%d/%m/%y")
                elif "," in original_text:
                    replacement = fake_dt.strftime("%B %d, %Y")
                else:
                    replacement = fake_dt.strftime("%B %d, %Y")
            except Exception:
                # Fallback to generic date string
                replacement = self.fake.date()
        else:
            # Fallback for unrecognized types
            replacement = f"[REDACTED_{entity_type}]"

        # Save mapping and return
        self.mapping[key] = replacement
        return replacement
