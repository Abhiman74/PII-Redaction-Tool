import re
from dataclasses import dataclass
from typing import List, Tuple
from docx.text.run import Run

@dataclass
class PIIEntity:
    text: str
    entity_type: str
    start: int
    end: int
    score: float = 1.0

def validate_luhn(card_number: str) -> bool:
    """
    Validate a credit card number using the Luhn algorithm.
    """
    # Remove non-digits
    digits = [int(c) for c in card_number if c.isdigit()]
    if not digits or len(digits) < 9 or len(digits) > 19:
        return False
    
    # Luhn algorithm implementation
    checksum = 0
    reverse_digits = digits[::-1]
    for i, digit in enumerate(reverse_digits):
        if i % 2 == 1:
            doubled = digit * 2
            checksum += doubled if doubled < 10 else doubled - 9
        else:
            checksum += digit
            
    return checksum % 10 == 0

def get_paragraph_runs(paragraph) -> List[Run]:
    """
    Retrieve all runs in a paragraph in document order, including runs nested
    within w:hyperlink, w:ins, w:smartTag, etc.
    """
    runs = []
    
    def _find_runs(element):
        for child in element:
            # Check for w:r (run)
            if child.tag.endswith('}r'):
                runs.append(Run(child, paragraph))
            # Recurse into elements that can contain w:r
            elif child.tag.endswith('}hyperlink') or child.tag.endswith('}ins') or child.tag.endswith('}smartTag') or child.tag.endswith('}sdt'):
                _find_runs(child)
                
    _find_runs(paragraph._p)
    return runs

def resolve_overlapping_entities(entities: List[PIIEntity]) -> List[PIIEntity]:
    """
    Resolve overlapping entity spans using a greedy interval scheduling approach.
    Prioritizes longer spans and keeps the first span in case of exact index matches.
    """
    # Sort by start index ascending, and length descending
    sorted_entities = sorted(entities, key=lambda e: (e.start, -(e.end - e.start)))
    resolved = []
    
    last_end = -1
    for entity in sorted_entities:
        if entity.start >= last_end:
            resolved.append(entity)
            last_end = entity.end
        else:
            # Overlap exists. Check if this entity has a higher priority or is longer
            # With greedy scheduling, since we sorted by start and length, the first one
            # processed is the most dominant.
            pass
            
    return resolved
