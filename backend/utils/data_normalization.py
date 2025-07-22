import re
from difflib import get_close_matches
from typing import List, Dict, Optional

class DataNormalizer:
    def __init__(self, unique_values: Dict):
        self.unique_values = unique_values
        self.subject_mappings = self._create_subject_mappings()
        self.programme_mappings = self._create_programme_mappings()
    
    def _create_subject_mappings(self) -> Dict[str, str]:
        """Create mappings for subject names to handle variations"""
        mappings = {}
        
        # Clean and normalize all subject names
        normalized_subjects = {}
        for subject in self.unique_values["subjectname"]:
            if subject and subject != "null":
                # Remove special characters, convert to lowercase, normalize spacing
                clean_name = re.sub(r'[§~()\[\]&]', '', subject.lower())
                clean_name = re.sub(r'\s+', ' ', clean_name).strip()
                
                # Store both original and cleaned versions
                normalized_subjects[clean_name] = subject
                mappings[subject.lower()] = subject
        
        # Create specific mappings for common variations
        common_mappings = {
            # Programming subjects
            "programming principles": "PROGRAMMING PRINCIPLES",
            "programmingprinciples": "PROGRAMMING PRINCIPLES",
            
            # Database subjects  
            "database fundamentals": "DATABASE FUNDAMENTALS",
            "databasefundamentals": "DATABASE FUNDAMENTALS",
            
            # Network subjects
            "network security": "NETWORK SECURITY",
            "networksecurity": "NETWORK SECURITY",
            "networking principles": "NETWORKING PRINCIPLES",
            "networkingprinciples": "NETWORKING PRINCIPLES",
            
            # Web programming
            "web programming": "WEB PROGRAMMING",
            "webprogramming": "WEB PROGRAMMING",
            
            # Mathematics subjects
            "linear algebra applications": "LINEAR ALGEBRA & APPLICATIONS",
            "linear algebra and applications": "LINEAR ALGEBRA & APPLICATIONS",
            "linearalgebraapplications": "LINEAR ALGEBRA & APPLICATIONS",
            
            # Ethics subjects
            "appreciation of ethics and civilisation": "APPRECIATION OF ETHICS AND CIVILISATION",
            "penghayatan etika dan peradaban": "PENGHAYATAN ETIKA DAN PERADABAN",
            
            # Language subjects
            "bahasa kebangsaan a": "BAHASA KEBANGSAAN A",
            "english for computer technology studies": "ENGLISH FOR COMPUTER TECHNOLOGY STUDIES",
            
            # Project subjects
            "capstone project 1": "CapstoneProject1",
            "capstone project 2": "CapstoneProject2",
            "capstone project (2)": "CAPSTONE PROJECT (2)",
            
            # AI subjects
            "artificial intelligence": "ArtificialIntelligence",
            "ai": "ArtificialIntelligence",
            
            # Mobile subjects
            "mobile application development": "MobileApplicationDevelopment",
            "mobile app development": "MobileApplicationDevelopment",
            
            # Statistics subjects
            "statistics": "Statistics",
            "applied statistics": "AppliedStatistics",
            "introduction to statistics": "IntroductiontoStatistics",
            
            # Computer subjects
            "computer fundamentals": "ComputerFundamentals",
            "computer mathematics": "ComputerMathematics",
            "computer networks": "ComputerNetworks",
            "computer security": "ComputerSecurity",
            "computer organisation": "ComputerOrganisation",
            
            # Engineering subjects
            "engineering mathematics 1": "EngineeringMathematics1",
            "engineering mathematics 2": "EngineeringMathematics2", 
            "engineering mathematics 3": "EngineeringMathematics3",
            "engineering mathematics 4": "EngineeringMathematics4",
            "engineering physics": "EngineeringPhysics",
            
            # Other common subjects
            "calculus": "Calculus",
            "precalculus": "Precalculus",
            "discrete mathematics": "DiscreteMathematics",
            "data structures algorithms": "DataStructures&Algorithms",
            "data structures and algorithms": "DataStructures&Algorithms",
            "operating system fundamentals": "OperatingSystemFundamentals",
            "human computer interaction": "HumanComputerInteraction",
            "software engineering": "SoftwareEngineering",
            "internship": "INTERNSHIP"
        }
        
        # Add common mappings
        mappings.update(common_mappings)
        
        return mappings
    
    def _create_programme_mappings(self) -> Dict[str, str]:
        """Create mappings for programme names"""
        mappings = {}
        
        for programme in self.unique_values["programme"]:
            if programme and programme != "null":
                # Create lowercase mapping
                mappings[programme.lower()] = programme
        
        # Add common abbreviations and variations
        common_mappings = {
            "computer science": "BSc (Hons) in Computer Science",
            "cs": "BSc (Hons) in Computer Science",
            "information technology": "BSc (Hons) Information Technology", 
            "it": "BSc (Hons) Information Technology",
            "information systems": "BSc (Hons) Information Systems",
            "is": "BSc (Hons) Information Systems",
            "software engineering": "Bachelor of Software Engineering (Hons)",
            "se": "Bachelor of Software Engineering (Hons)",
            "civil engineering": "Bachelor of Civil Engineering with Honours",
            "mechanical engineering": "Bachelor of Mechanical Engineering with Honours",
            "electrical engineering": "Bachelor of Electronic and Electrical Engineering with Honours",
            "chemical engineering": "Bachelor of Chemical Engineering with Honours",
            "mechatronic engineering": "Bachelor of Mechatronic Engineering (Robotics) with Honours",
            "data analytics": "Bachelor of Information Systems (Honours) (Data Analytics)",
            "mobile computing": "Bachelor of Information Systems (Hons) in Mobile Computing with Entrepreneurship",
            "business analytics": "Bachelor of Science (Honours) Information Systems (Business Analytics)",
            "networking security": "BSc (Hons) Information Technology (Computer Networking and Security)"
        }
        
        mappings.update(common_mappings)
        return mappings
    
    def normalize_subject_name(self, subject_query: str) -> Optional[str]:
        """Normalize subject name using mappings and fuzzy matching"""
        if not subject_query:
            return None
            
        # Clean the query
        clean_query = subject_query.lower().strip()
        clean_query = re.sub(r'[§~()\[\]&]', '', clean_query)
        clean_query = re.sub(r'\s+', ' ', clean_query)
        
        # Try direct mapping first
        if clean_query in self.subject_mappings:
            return self.subject_mappings[clean_query]
        
        # Try fuzzy matching
        all_subjects = [s for s in self.unique_values["subjectname"] if s and s != "null"]
        matches = get_close_matches(subject_query, all_subjects, n=1, cutoff=0.6)
        
        if matches:
            return matches[0]
        
        # Try partial matching
        for subject in all_subjects:
            if clean_query in subject.lower() or subject.lower() in clean_query:
                return subject
                
        return None
    
    def normalize_programme_name(self, programme_query: str) -> Optional[str]:
        """Normalize programme name using mappings and fuzzy matching"""
        if not programme_query:
            return None
            
        clean_query = programme_query.lower().strip()
        
        # Try direct mapping first
        if clean_query in self.programme_mappings:
            return self.programme_mappings[clean_query]
        
        # Try fuzzy matching
        all_programmes = [p for p in self.unique_values["programme"] if p and p != "null"]
        matches = get_close_matches(programme_query, all_programmes, n=1, cutoff=0.6)
        
        if matches:
            return matches[0]
            
        # Try partial matching
        for programme in all_programmes:
            if clean_query in programme.lower() or programme.lower() in clean_query:
                return programme
                
        return None
    
    def find_similar_values(self, query: str, field: str, limit: int = 5) -> List[str]:
        """Find similar values for a given field"""
        if field not in self.unique_values:
            return []
            
        values = [v for v in self.unique_values[field] if v and v != "null"]
        matches = get_close_matches(query, values, n=limit, cutoff=0.4)
        return matches

# Example usage and testing
if __name__ == "__main__":
    # Test with sample data
    sample_unique_values = {
        "subjectname": [
            "PROGRAMMING PRINCIPLES", "ProgrammingPrinciples", "Programming Principles",
            "DATABASE FUNDAMENTALS", "DatabaseFundamentals", "Database Fundamentals",
            "NETWORK SECURITY", "NetworkSecurity", "Network Security",
            "Artificial Intelligence", "ArtificialIntelligence", "AI"
        ],
        "programme": [
            "BSc (Hons) in Computer Science",
            "BSc (Hons) Information Technology", 
            "Bachelor of Software Engineering (Hons)"
        ]
    }
    
    normalizer = DataNormalizer(sample_unique_values)
    
    # Test subject normalization
    print("Subject Tests:")
    test_subjects = [
        "programming principles", 
        "database fundamentals",
        "artificial intelligence",
        "ai",
        "network security"
    ]
    
    for subject in test_subjects:
        normalized = normalizer.normalize_subject_name(subject)
        print(f"'{subject}' -> '{normalized}'")
    
    # Test programme normalization  
    print("\nProgramme Tests:")
    test_programmes = [
        "computer science",
        "information technology", 
        "software engineering"
    ]
    
    for programme in test_programmes:
        normalized = normalizer.normalize_programme_name(programme)
        print(f"'{programme}' -> '{normalized}'")