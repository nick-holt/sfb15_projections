#!/usr/bin/env python3
"""
Player name normalization utility to handle character encoding differences
and name variations across different data sources.
"""

import re
import unicodedata
from typing import List, Dict

class NameNormalizer:
    """Utility class to normalize player names for consistent joins"""
    
    def __init__(self):
        # Common character replacements
        self.char_replacements = {
            # Apostrophes - using actual Unicode characters
            '\u2019': "'",  # curly apostrophe (ord 8217) -> straight apostrophe (ord 39)
            '\u2018': "'",  # left single quotation mark
            '`': "'",  # grave accent
            
            # Hyphens and dashes
            '\u2013': "-",  # en dash
            '\u2014': "-",  # em dash
            
            # Periods and dots
            '.': "",   # Remove periods (for Jr., Sr., etc.)
            
            # Common abbreviations
            'Jr.': 'Jr',
            'Sr.': 'Sr',
            'III': '3rd',
            'II': '2nd',
        }
        
        # Common name variations
        self.name_variations = {
            'D.J.': 'DJ',
            'T.J.': 'TJ',
            'A.J.': 'AJ',
            'C.J.': 'CJ',
            'J.J.': 'JJ',
            'D.K.': 'DK',
            'J.K.': 'JK',
            'K.J.': 'KJ',
            'P.J.': 'PJ',
            'R.J.': 'RJ',
        }
    
    def normalize_name(self, name: str) -> str:
        """
        Normalize a player name by standardizing characters and format
        
        Args:
            name: Original player name
            
        Returns:
            Normalized player name
        """
        if not isinstance(name, str) or not name.strip():
            return ""
        
        normalized = name.strip()
        
        # Apply character replacements
        for old_char, new_char in self.char_replacements.items():
            normalized = normalized.replace(old_char, new_char)
        
        # Apply name variations
        for old_variation, new_variation in self.name_variations.items():
            normalized = normalized.replace(old_variation, new_variation)
        
        # Normalize unicode characters
        normalized = unicodedata.normalize('NFKD', normalized)
        
        # Remove extra whitespace
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        
        # Ensure proper capitalization
        normalized = self.fix_capitalization(normalized)
        
        return normalized
    
    def fix_capitalization(self, name: str) -> str:
        """Fix common capitalization issues in player names"""
        if not name:
            return name
        
        # Split into parts
        parts = name.split()
        fixed_parts = []
        
        for part in parts:
            # Handle special cases
            if part.lower() in ['jr', 'sr', 'iii', 'ii', 'iv', 'v']:
                fixed_parts.append(part.capitalize())
            elif part.upper() in ['DJ', 'TJ', 'AJ', 'CJ', 'JJ', 'DK', 'JK', 'KJ', 'PJ', 'RJ']:
                fixed_parts.append(part.upper())
            elif "'" in part:
                # Handle apostrophes (like O'Dell)
                apostrophe_parts = part.split("'")
                capitalized_parts = [p.capitalize() for p in apostrophe_parts]
                fixed_parts.append("'".join(capitalized_parts))
            elif "-" in part:
                # Handle hyphens (like Jean-Baptiste)
                hyphen_parts = part.split("-")
                capitalized_parts = [p.capitalize() for p in hyphen_parts]
                fixed_parts.append("-".join(capitalized_parts))
            else:
                fixed_parts.append(part.capitalize())
        
        return " ".join(fixed_parts)
    
    def create_name_mapping(self, names_list: List[str]) -> Dict[str, str]:
        """
        Create a mapping from original names to normalized names
        
        Args:
            names_list: List of original names
            
        Returns:
            Dictionary mapping original names to normalized names
        """
        mapping = {}
        for name in names_list:
            if isinstance(name, str):
                normalized = self.normalize_name(name)
                mapping[name] = normalized
        return mapping
    
    def find_best_match(self, target_name: str, candidate_names: List[str], 
                       threshold: float = 0.85) -> str:
        """
        Find the best matching name from a list of candidates
        
        Args:
            target_name: Name to match
            candidate_names: List of potential matches
            threshold: Minimum similarity threshold
            
        Returns:
            Best matching name or empty string if no good match
        """
        from difflib import SequenceMatcher
        
        target_normalized = self.normalize_name(target_name)
        best_match = ""
        best_score = 0
        
        for candidate in candidate_names:
            if not isinstance(candidate, str):
                continue
                
            candidate_normalized = self.normalize_name(candidate)
            
            # Calculate similarity
            similarity = SequenceMatcher(None, target_normalized.lower(), 
                                       candidate_normalized.lower()).ratio()
            
            if similarity > best_score and similarity >= threshold:
                best_score = similarity
                best_match = candidate
        
        return best_match
    
    def batch_normalize(self, df, name_column: str) -> None:
        """
        Normalize names in a DataFrame in place
        
        Args:
            df: DataFrame to modify
            name_column: Name of the column containing names
        """
        if name_column in df.columns:
            df[name_column] = df[name_column].apply(self.normalize_name)
    
    def test_normalization(self) -> None:
        """Test the normalization with common problematic names"""
        test_names = [
            "Ja'Marr Chase",  # curly apostrophe
            "Ja'Marr Chase",  # straight apostrophe
            "D'Andre Swift",  # apostrophe variations
            "T.J. Hockenson",  # periods
            "Calvin Ridley Jr.",  # suffix
            "A.J. Brown",  # initials with periods
            "Jean-Baptiste",  # hyphen
            "DJ Moore",  # initials without periods
        ]
        
        print("=== NAME NORMALIZATION TEST ===")
        for name in test_names:
            normalized = self.normalize_name(name)
            print(f"'{name}' -> '{normalized}'")
            print(f"  Ord values: {[ord(c) for c in name]} -> {[ord(c) for c in normalized]}")
            print()

# Create a global instance for easy import
name_normalizer = NameNormalizer()

if __name__ == "__main__":
    normalizer = NameNormalizer()
    normalizer.test_normalization() 