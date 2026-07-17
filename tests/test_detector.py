import unittest
from src.utils import validate_luhn, resolve_overlapping_entities, PIIEntity
from src.detector import RegexDetector
from src.replacer import PIIReplacer

class TestPIIUtils(unittest.TestCase):
    def test_luhn_validation(self):
        # Valid credit cards
        self.assertTrue(validate_luhn("49927398716"))
        self.assertTrue(validate_luhn("4111111111111111"))
        # Invalid credit cards
        self.assertFalse(validate_luhn("49927398717"))
        self.assertFalse(validate_luhn("1234567812345671"))

    def test_overlap_resolution(self):
        entities = [
            PIIEntity("KSH International", "ORG", 0, 17),
            PIIEntity("KSH", "ORG", 0, 3),  # Subset
            PIIEntity("International Limited", "ORG", 4, 25),  # Overlapping
            PIIEntity("Sarthak", "PERSON", 30, 37)  # Disjoint
        ]
        resolved = resolve_overlapping_entities(entities)
        
        # Expected resolved:
        # 1. "KSH International" (0, 17) - first and longest
        # 2. "Sarthak" (30, 37) - disjoint from "KSH International"
        self.assertEqual(len(resolved), 2)
        self.assertEqual(resolved[0].text, "KSH International")
        self.assertEqual(resolved[1].text, "Sarthak")

class TestRegexDetector(unittest.TestCase):
    def setUp(self):
        self.detector = RegexDetector()

    def test_email_detection(self):
        text = "Contact us at cs.connect@kshinternational.com or info@gmail.com."
        entities = self.detector.detect(text)
        emails = [e.text for e in entities if e.entity_type == "EMAIL_ADDRESS"]
        self.assertIn("cs.connect@kshinternational.com", emails)
        self.assertIn("info@gmail.com", emails)

    def test_phone_detection(self):
        text = "Our number is +91 20 45053237 and +91 81081 14949."
        entities = self.detector.detect(text)
        phones = [e.text for e in entities if e.entity_type == "PHONE_NUMBER"]
        self.assertIn("+91 20 45053237", phones)
        self.assertIn("+91 81081 14949", phones)

    def test_ssn_detection(self):
        text = "Employee SSN: 000-12-3456."
        entities = self.detector.detect(text)
        ssns = [e.text for e in entities if e.entity_type == "US_SSN"]
        self.assertIn("000-12-3456", ssns)

    def test_ip_detection(self):
        text = "Server IPs are 192.168.1.1 and 2001:db8:3333:4444:5555:6666:7777:8888."
        entities = self.detector.detect(text)
        ips = [e.text for e in entities if e.entity_type == "IP_ADDRESS"]
        self.assertIn("192.168.1.1", ips)
        self.assertIn("2001:db8:3333:4444:5555:6666:7777:8888", ips)

    def test_pan_detection(self):
        text = "PAN card is NBWPS1951N."
        entities = self.detector.detect(text)
        pans = [e.text for e in entities if e.entity_type == "INDIAN_PAN"]
        self.assertIn("NBWPS1951N", pans)

    def test_postal_code_detection(self):
        text = "Registered office in Pune 411045 or Chakan Pune – 410 501."
        entities = self.detector.detect(text)
        pins = [e.text for e in entities if e.entity_type == "POSTAL_CODE"]
        self.assertIn("411045", pins)
        self.assertIn("410 501", pins)

    def test_date_detection(self):
        text = "Date of Birth: December 10, 2025. DOB is 06/05/2000. Normal date: July 4, 1996."
        entities = self.detector.detect(text)
        
        dobs = [e.text for e in entities if e.entity_type == "DATE_OF_BIRTH"]
        self.assertIn("December 10, 2025", dobs)
        self.assertIn("06/05/2000", dobs)
        
        dates = [e.text for e in entities if e.entity_type == "DATE"]
        self.assertIn("July 4, 1996", dates)

class TestReplacer(unittest.TestCase):
    def setUp(self):
        self.replacer = PIIReplacer()

    def test_deterministic_replacement(self):
        name1 = "Kushal Subbayya Hegde"
        name2 = "Kushal Subbayya Hegde"
        rep1 = self.replacer.get_replacement(name1, "PERSON")
        rep2 = self.replacer.get_replacement(name2, "PERSON")
        self.assertEqual(rep1, rep2)
        
        # Different name should have a different replacement (generally)
        name3 = "Sarthak Malvadkar"
        rep3 = self.replacer.get_replacement(name3, "PERSON")
        self.assertNotEqual(rep1, rep3)

    def test_date_formatting(self):
        # Format preservation
        self.assertEqual(len(self.replacer.get_replacement("1999-01-05", "DATE_OF_BIRTH").split("-")), 3)
        self.assertEqual(len(self.replacer.get_replacement("06/05/2000", "DATE_OF_BIRTH").split("/")), 3)
        self.assertTrue("," in self.replacer.get_replacement("December 10, 2025", "DATE_OF_BIRTH"))

if __name__ == "__main__":
    unittest.main()
