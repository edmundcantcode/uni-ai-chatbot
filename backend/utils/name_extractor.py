import spacy

# Load spaCy English model once
nlp = spacy.load("en_core_web_lg")

def extract_name_spacy(text: str):
    doc = nlp(text)
    for ent in doc.ents:
        if ent.label_ == "PERSON":
            return ent.text.strip()
    return None
