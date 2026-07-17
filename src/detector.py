import re
import logging
from abc import ABC, abstractmethod
from typing import List, Set
from datetime import datetime
from dateutil import parser as date_parser

from src.utils import PIIEntity, validate_luhn, resolve_overlapping_entities

logger = logging.getLogger(__name__)

class BaseDetector(ABC):
    """
    Abstract base class for PII detectors.
    """
    @abstractmethod
    def detect(self, text: str) -> List[PIIEntity]:
        """
        Analyze text and return a list of detected PII entities.
        """
        pass

class PresidioDetector(BaseDetector):
    """
    PII Detector using Microsoft Presidio Analyzer Engine.
    """
    def __init__(self):
        try:
            from presidio_analyzer import AnalyzerEngine
            from presidio_analyzer.nlp_engine import NlpEngineProvider
            # Configure Presidio to use lightweight en_core_web_sm model to prevent runtime downloads and OOM
            configuration = {
                "nlp_engine_name": "spacy",
                "models": [{"lang_code": "en", "model_name": "en_core_web_sm"}]
            }
            provider = NlpEngineProvider(nlp_configuration=configuration)
            nlp_engine = provider.create_engine()
            self.analyzer = AnalyzerEngine(nlp_engine=nlp_engine)
        except ImportError as e:
            logger.error("Presidio is not installed: %s", e)
            raise RuntimeError("presidio-analyzer is required but not installed.") from e
        except Exception as e:
            logger.error("Failed to initialize Presidio: %s", e)
            raise RuntimeError("Failed to initialize Presidio Analyzer.") from e

    def detect(self, text: str) -> List[PIIEntity]:
        if not text.strip():
            return []
            
        try:
            results = self.analyzer.analyze(
                text=text,
                language="en",
                entities=[
                    "PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER", "US_SSN", 
                    "CREDIT_CARD", "DATE_TIME", "IP_ADDRESS", "LOCATION"
                ]
            )
            
            entities = []
            for r in results:
                # Map Presidio type to our standard PII type
                entities.append(PIIEntity(
                    text=text[r.start:r.end],
                    entity_type=r.entity_type,
                    start=r.start,
                    end=r.end,
                    score=r.score
                ))
            return entities
        except Exception as e:
            logger.error("Error running Presidio detection: %s", e)
            return []

class SpacyDetector(BaseDetector):
    """
    PII Detector using spaCy en_core_web_lg model.
    """
    def __init__(self, model_name: str = "en_core_web_sm"):
        try:
            import spacy
            try:
                self.nlp = spacy.load(model_name)
            except OSError:
                logger.warning("spaCy model %s not found. Attempting to download...", model_name)
                from spacy.cli import download
                download(model_name)
                self.nlp = spacy.load(model_name)
        except ImportError as e:
            logger.error("spaCy is not installed: %s", e)
            raise RuntimeError("spacy is required but not installed.") from e

    def detect(self, text: str) -> List[PIIEntity]:
        if not text.strip():
            return []
            
        try:
            doc = self.nlp(text)
            entities = []
            # We want to detect PERSON, ORG, GPE, LOC, FAC
            target_labels = {"PERSON", "ORG", "GPE", "LOC", "FAC"}
            
            for ent in doc.ents:
                if ent.label_ in target_labels:
                    entities.append(PIIEntity(
                        text=ent.text,
                        entity_type=ent.label_,
                        start=ent.start_char,
                        end=ent.end_char,
                        score=0.85  # spaCy does not provide confidence scores natively, use default high confidence
                    ))
            return entities
        except Exception as e:
            logger.error("Error running spaCy detection: %s", e)
            return []

class RegexDetector(BaseDetector):
    """
    PII Detector using custom regular expressions for high-precision matching of specific formats.
    """
    def __init__(self):
        # 1. Emails
        self.email_re = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
        
        # 2. Phone numbers (e.g. +91 22 4009 4400, +91 81081 14949, +91 20 45053237, +91-22-6807-7100, 020-45053237)
        # Matches numbers starting with international prefix, optional 0, 10 digits, or standard formats.
        self.phone_re = re.compile(
            r'(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,5}\)?[-.\s]?\d{3,5}[-.\s]?\d{3,5}'
        )
        
        # 3. Credit Cards (matches various card digit groupings, later verified with Luhn)
        self.cc_re = re.compile(
            r'\b(?:\d[ -]*?){13,19}\b'
        )
        
        # 4. SSNs (US format)
        self.ssn_re = re.compile(r'\b\d{3}-\d{2}-\d{4}\b')
        
        # 5. IPv4 and IPv6
        self.ipv4_re = re.compile(
            r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b'
        )
        self.ipv6_re = re.compile(
            r'\b(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}\b'
        )
        
        # 6. Dates of Birth and generic dates (to filter and check for DOB context)
        # Matches YYYY-MM-DD, DD/MM/YYYY, Month DD, YYYY, etc.
        self.date_re = re.compile(
            r'\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}[/-]\d{1,2}[/-]\d{1,2}|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}|\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4})\b',
            re.IGNORECASE
        )
        
        # 7. Indian PAN Card numbers (e.g. NBWPS1951N, which appears in document)
        self.pan_re = re.compile(r'\b[A-Z]{5}[0-9]{4}[A-Z]\b')
        
        # 8. Postal codes / PIN codes (especially Indian 6 digit PIN codes with optional space, e.g. 410 501, 411 045)
        self.pin_re = re.compile(r'\b\d{3}\s?\d{3}\b')

    def detect(self, text: str) -> List[PIIEntity]:
        if not text:
            return []
            
        entities = []
        
        # Email Detection
        for m in self.email_re.finditer(text):
            entities.append(PIIEntity(m.group(), "EMAIL_ADDRESS", m.start(), m.end(), 1.0))
            
        # Phone Detection (Verify with phonenumbers if possible)
        for m in self.phone_re.finditer(text):
            match_str = m.group()
            # Clean up the match to see if it has at least 7 digits (to prevent matching random number strings)
            digit_count = sum(1 for c in match_str if c.isdigit())
            if digit_count >= 7:
                # We can also double check with the phonenumbers library
                try:
                    import phonenumbers
                    # Check if it could be a valid phone number (parse with generic or local regions)
                    for region in [None, "IN", "US", "GB"]:
                        try:
                            parsed = phonenumbers.parse(match_str, region)
                            if phonenumbers.is_possible_number(parsed):
                                entities.append(PIIEntity(match_str, "PHONE_NUMBER", m.start(), m.end(), 0.95))
                                break
                        except Exception:
                            continue
                except ImportError:
                    # Fallback to pure regex match if library not loaded
                    entities.append(PIIEntity(match_str, "PHONE_NUMBER", m.start(), m.end(), 0.90))

        # Credit Card Detection ( Luhn verification is MANDATORY)
        for m in self.cc_re.finditer(text):
            cc_str = m.group()
            # Strip spaces/dashes for Luhn check
            cleaned = "".join(c for c in cc_str if c.isdigit())
            if len(cleaned) >= 13 and len(cleaned) <= 19:
                if validate_luhn(cleaned):
                    entities.append(PIIEntity(cc_str, "CREDIT_CARD", m.start(), m.end(), 1.0))

        # SSN Detection
        for m in self.ssn_re.finditer(text):
            entities.append(PIIEntity(m.group(), "US_SSN", m.start(), m.end(), 1.0))
            
        # IP Addresses
        for m in self.ipv4_re.finditer(text):
            entities.append(PIIEntity(m.group(), "IP_ADDRESS", m.start(), m.end(), 1.0))
        for m in self.ipv6_re.finditer(text):
            entities.append(PIIEntity(m.group(), "IP_ADDRESS", m.start(), m.end(), 1.0))
            
        # PAN Cards
        for m in self.pan_re.finditer(text):
            entities.append(PIIEntity(m.group(), "INDIAN_PAN", m.start(), m.end(), 1.0))

        # Postal codes (only capture as PII if associated with locations or explicitly matching)
        # Note: We classify postal codes as POSTAL_CODE to be used for validation / location checks
        for m in self.pin_re.finditer(text):
            # Check context: usually surrounded by India, Pune, Maharashtra, Chakan Taluka etc.
            # For robustness, we classify them as POSTAL_CODE
            entities.append(PIIEntity(m.group(), "POSTAL_CODE", m.start(), m.end(), 0.90))

        # Dates (Checking for DOB context)
        # Since not all dates are Dates of Birth, we check nearby context for keywords like "born", "birth", "dob", "date of birth", "age"
        for m in self.date_re.finditer(text):
            date_str = m.group()
            # Check if it parses as a valid date
            try:
                dt = date_parser.parse(date_str)
                # Verify context around the date to classify as DATE_OF_BIRTH vs normal DATE
                # Search window of 50 chars before the match
                start_window = max(0, m.start() - 50)
                context = text[start_window:m.start()].lower()
                # Restrict context window to the current sentence/clause
                if "." in context:
                    context = context.split(".")[-1]
                if "\n" in context:
                    context = context.split("\n")[-1]
                
                if any(keyword in context for keyword in ["born", "birth", "dob", "d.o.b", "date of birth", "age"]):
                    entities.append(PIIEntity(date_str, "DATE_OF_BIRTH", m.start(), m.end(), 1.0))
                else:
                    # Generic date
                    entities.append(PIIEntity(date_str, "DATE", m.start(), m.end(), 0.80))
            except Exception:
                continue

        return entities

class HybridDetector(BaseDetector):
    """
    PII Detector combining Presidio, spaCy, and Regex-based detection.
    """
    def __init__(self, use_presidio: bool = True, use_spacy: bool = True):
        self.detectors: List[BaseDetector] = []
        
        # Load regex detector first (highest precision for pattern-based PII)
        self.detectors.append(RegexDetector())
        
        # Load Presidio
        if use_presidio:
            try:
                self.detectors.append(PresidioDetector())
            except RuntimeError as e:
                logger.warning("PresidioDetector failed to load: %s. Continuing without it.", e)
                
        # Load spaCy
        if use_spacy:
            try:
                self.detectors.append(SpacyDetector())
            except RuntimeError as e:
                logger.warning("SpacyDetector failed to load: %s. Continuing without it.", e)

    def detect(self, text: str) -> List[PIIEntity]:
        if not text or not text.strip():
            return []
            
        all_entities = []
        for detector in self.detectors:
            all_entities.extend(detector.detect(text))
            
        # Resolve overlapping spans using greedy interval scheduling
        resolved_entities = resolve_overlapping_entities(all_entities)
        
        return resolved_entities
