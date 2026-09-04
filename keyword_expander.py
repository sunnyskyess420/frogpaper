"""
Keyword Expansion System for FrogPaper

Provides AI-enhanced synonym expansion and semantic similarity matching
to improve user input understanding and theme generation.
"""

import json
import logging
from typing import List, Dict, Optional, Tuple
import re
from datetime import datetime

from utils import get_app_dir, get_bundle_dir

logger = logging.getLogger(__name__)

# Optional library flags — actual imports happen lazily inside the methods that need them.
NLTK_AVAILABLE = None
SENTENCE_TRANSFORMERS_AVAILABLE = None

BASE_DIR = get_app_dir()
BUNDLE_DIR = get_bundle_dir()
KEYWORDS_FILE = BUNDLE_DIR / "keywords.json"
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)

# Lazy database helper — avoids import-time dependency on database.py
_db = None


def _get_db():
    global _db
    if _db is None:
        try:
            import database
            if not database.DB_AVAILABLE:
                return None
            _db = database
            if _db._SessionFactory is None:
                _db.init_db()
        except ImportError:
            return None
    return _db


class KeywordExpander:
    """Intelligent keyword expansion system using thesaurus and semantic similarity."""
    
    def __init__(self):
        self.keywords_data = {}
        self.user_thesaurus = {}
        self.expansion_history = []
        self.sentence_model = None
        self.keyword_embeddings = None
        self.indexed_keywords = []
        self._initialized = False
        self._expansion_cache = {}  # Cache results to avoid redundant BERT inference
        
    def _check_nltk(self):
        """Lazy check for NLTK availability."""
        global NLTK_AVAILABLE
        if NLTK_AVAILABLE is None:
            try:
                import nltk  # noqa: F401  (availability probe)
                from nltk.corpus import wordnet as _wn  # noqa: F401  (availability probe)
                NLTK_AVAILABLE = True
            except ImportError:
                NLTK_AVAILABLE = False
        return NLTK_AVAILABLE

    def _check_sentence_transformers(self):
        """Lazy check for sentence-transformers availability."""
        global SENTENCE_TRANSFORMERS_AVAILABLE
        if SENTENCE_TRANSFORMERS_AVAILABLE is None:
            try:
                from sentence_transformers import SentenceTransformer as _ST  # noqa: F401  (availability probe)
                import numpy as _np  # noqa: F401  (availability probe)
                SENTENCE_TRANSFORMERS_AVAILABLE = True
            except ImportError:
                SENTENCE_TRANSFORMERS_AVAILABLE = False
        return SENTENCE_TRANSFORMERS_AVAILABLE

    def initialize(self):
        """Initialize the keyword expansion system."""
        if self._initialized:
            return
            
        # Load keywords first so we have them for embeddings
        self._load_keywords()
        self._load_user_thesaurus()
        
        # Don't load BERT yet — do it lazily on first semantic search
        # to keep app startup fast.
        
        self._initialized = True
    
    def warmup(self):
        """Pre-warm NLTK on app startup (reduces cold-start latency).
        
        Note: sentence-transformers warmup disabled to prevent system freezes.
        The BERT model will lazy-load only when semantic similarity is actually needed.
        """
        if not self._initialized:
            self.initialize()
        
        # Warm up NLTK only (lightweight)
        if self._check_nltk():
            try:
                self._setup_nltk()
                logger.info("NLTK warmup completed successfully")
            except Exception as e:
                logger.warning("NLTK warmup failed: %s", e)
        
        # Pre-load keyword data for faster lookups
        if self.keywords_data:
            logger.info(f"Keyword data loaded: {len(self.keywords_data)} categories, {len(self.all_keywords_set)} keywords")
        
        # sentence-transformers warmup disabled - causes system freezes due to heavy PyTorch model loading
        # Model will lazy-load on first semantic similarity request instead
    
    def _load_keywords(self):
        """Load keywords and create a flat set for fast lookups."""
        try:
            kw_path = KEYWORDS_FILE if KEYWORDS_FILE.exists() else BASE_DIR / "keywords.json"
            if kw_path.exists():
                with open(kw_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Filter out comments/metadata
                    self.keywords_data = {k: v for k, v in data.items() if not k.startswith("_")}
                    
                    # Create flat set of all known keywords for O(1) lookup
                    self.all_keywords_set = set()
                    for category_list in self.keywords_data.values():
                        if isinstance(category_list, list):
                            for kw in category_list:
                                self.all_keywords_set.add(kw.lower().strip())
            else:
                self.keywords_data = {}
                self.all_keywords_set = set()
        except Exception as e:
            logger.error("Error loading keywords: %s", e)
            self.keywords_data = {}
            self.all_keywords_set = set()
    
    def _load_user_thesaurus(self):
        """Load user-defined thesaurus mappings from SQLite, with JSON fallback."""
        try:
            db = _get_db()
            if db is not None:
                session = db.get_db_session()
                try:
                    rows = session.query(db.UserThesaurus).all()
                    self.user_thesaurus = {row.from_word: row.to_word for row in rows}
                finally:
                    session.close()
            else:
                # JSON fallback when DB is unavailable
                thesaurus_file = BASE_DIR / "user_thesaurus.json"
                if thesaurus_file.exists():
                    with open(thesaurus_file, "r", encoding="utf-8") as f:
                        self.user_thesaurus = json.load(f)
                else:
                    self.user_thesaurus = {}
        except Exception as e:
            logger.error("Error loading user thesaurus: %s", e)
            self.user_thesaurus = {}
    
    def _setup_nltk(self):
        """Download required NLTK data. Called lazily on first NLTK use."""
        if not self._check_nltk():
            return
        try:
            import nltk
            nltk.download('wordnet', quiet=True)
            nltk.download('omw-1.4', quiet=True)
            logger.info("NLTK WordNet data ready")
        except Exception as e:
            logger.error("Error setting up NLTK: %s", e)
    
    def _setup_sentence_transformers(self):
        """Setup sentence transformer model for semantic similarity. Called lazily on first use."""
        if not self._check_sentence_transformers():
            return
        try:
            from sentence_transformers import SentenceTransformer
            
            # Load a lightweight model
            self.sentence_model = SentenceTransformer('all-MiniLM-L6-v2')
            
            # Create embeddings for all keywords in a single batch
            all_keywords = sorted(list(self.all_keywords_set))
            if all_keywords:
                # Store the list so we can map indices back to words
                self.indexed_keywords = all_keywords
                self.keyword_embeddings = self.sentence_model.encode(all_keywords, convert_to_tensor=True)
            
        except Exception as e:
            logger.error("Error setting up sentence transformers: %s", e)
            self.sentence_model = None
    
    def get_synonyms_from_thesaurus(self, word: str) -> List[str]:
        """Get synonyms using NLTK WordNet thesaurus."""
        if not self._check_nltk():
            return []
        
        try:
            from nltk.corpus import wordnet
            synonyms = set()
            for syn in wordnet.synsets(word):
                for lemma in syn.lemmas():
                    synonym = lemma.name().replace('_', ' ')
                    if synonym != word and len(synonym) > 1:
                        synonyms.add(synonym)
            return list(synonyms)[:5]
        except Exception:
            return []
    
    def find_semantic_similarities(self, word: str, top_k: int = 3) -> List[Tuple[str, float]]:
        """Find semantically similar keywords using vectorized cosine similarity."""
        if not self._check_sentence_transformers():
            return []
        if self.sentence_model is None:
            self._setup_sentence_transformers()
        if self.sentence_model is None or self.keyword_embeddings is None:
            return []
        
        try:
            from sentence_transformers import util
            
            # Encode target word
            word_embedding = self.sentence_model.encode(word, convert_to_tensor=True)
            
            # Use vectorized cosine similarity
            cos_scores = util.cos_sim(word_embedding, self.keyword_embeddings)[0]
            
            # Get top K results
            import torch
            top_results = torch.topk(cos_scores, k=min(top_k, len(self.indexed_keywords)))
            
            results = []
            for score, idx in zip(top_results[0], top_results[1]):
                results.append((self.indexed_keywords[int(idx)], float(score)))
            
            return results
            
        except Exception as e:
            logger.error("Error finding semantic similarities: %s", e)
            return []
    
    def check_user_thesaurus(self, word: str) -> Optional[str]:
        """Check if user has defined a custom mapping for this word."""
        return self.user_thesaurus.get(word.lower())
    
    def expand_keyword(self, word: str) -> str:
        """Expand a single keyword using the expansion pipeline with caching."""
        if not self._initialized:
            self.initialize()
            
        word_clean = word.lower().strip()
        if not word_clean:
            return ""
            
        # Check cache first
        if word_clean in self._expansion_cache:
            return self._expansion_cache[word_clean]
        
        # Step 1: Check user thesaurus first
        user_mapping = self.check_user_thesaurus(word_clean)
        if user_mapping:
            self._log_expansion(word_clean, user_mapping, "user_thesaurus")
            self._expansion_cache[word_clean] = user_mapping
            return user_mapping
        
        # Step 2: Check if word exists in keywords set
        if word_clean in self.all_keywords_set:
            self._expansion_cache[word_clean] = word_clean
            return word_clean
        
        # Step 3: Try semantic similarity (BERT)
        similar_words = self.find_semantic_similarities(word_clean)
        if similar_words and similar_words[0][1] > 0.75:  # Higher threshold for safety
            best_match = similar_words[0][0]
            self._log_expansion(word_clean, best_match, "semantic_similarity", similar_words[0][1])
            self._expansion_cache[word_clean] = best_match
            return best_match
        
        # Step 4: Try thesaurus expansion (NLTK)
        synonyms = self.get_synonyms_from_thesaurus(word_clean)
        if synonyms:
            # We don't want to recursively do semantic search for every synonym here
            # as it multiplies latency. Just check if any synonym is a direct hit.
            for syn in synonyms:
                syn_clean = syn.lower().strip()
                if syn_clean in self.all_keywords_set:
                    self._log_expansion(word_clean, syn_clean, "thesaurus_match")
                    self._expansion_cache[word_clean] = syn_clean
                    return syn_clean
        
        # Step 5: Return original word if no expansion found
        self._expansion_cache[word_clean] = word_clean
        return word_clean
    
    def expand_text(self, text: str) -> str:
        """Expand all keywords in a text string."""
        if not self._initialized:
            self.initialize()
        
        # Split text into words and expand each one
        words = re.findall(r'\b\w+\b', text)
        expanded_words = []
        
        for word in words:
            expanded_word = self.expand_keyword(word)
            expanded_words.append(expanded_word)
        
        # Reconstruct the text with expanded words
        result = text
        for original, expanded in zip(words, expanded_words):
            # Skip case-only differences: an unexpanded word keeps the
            # user's original casing ("NEON Signs" stays "NEON Signs").
            # Only genuine expansions (cat -> frog) are rewritten.
            if original.lower() != expanded.lower():
                # Replace whole word only
                pattern = r'\b' + re.escape(original) + r'\b'
                result = re.sub(pattern, expanded, result, flags=re.IGNORECASE)
        
        return result
    
    def add_user_mapping(self, from_word: str, to_word: str):
        """Add a custom user thesaurus mapping.

        Clears the per-word expansion cache after saving: a word expanded
        before the mapping existed (e.g. cached as "no change") would
        otherwise shadow the new mapping until the app restarted.
        """
        self.user_thesaurus[from_word.lower()] = to_word.lower()
        self._save_user_thesaurus()
        self._expansion_cache.clear()

    def remove_user_mapping(self, from_word: str):
        """Remove a custom user thesaurus mapping (and stale cached expansions)."""
        if from_word.lower() in self.user_thesaurus:
            del self.user_thesaurus[from_word.lower()]
            self._save_user_thesaurus()
            self._expansion_cache.clear()
    
    def _save_user_thesaurus(self):
        """Save user thesaurus to SQLite (delete-all + re-insert), with JSON fallback."""
        try:
            db = _get_db()
            if db is not None:
                session = db.get_db_session()
                try:
                    session.query(db.UserThesaurus).delete()
                    for from_word, to_word in self.user_thesaurus.items():
                        session.add(db.UserThesaurus(from_word=from_word, to_word=to_word))
                    session.commit()
                except Exception:
                    session.rollback()
                    raise
                finally:
                    session.close()
            else:
                # JSON fallback when DB is unavailable
                thesaurus_file = BASE_DIR / "user_thesaurus.json"
                with open(thesaurus_file, "w", encoding="utf-8") as f:
                    json.dump(self.user_thesaurus, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error("Error saving user thesaurus: %s", e)
    
    def _log_expansion(self, original: str, expanded: str, method: str, confidence: float = 0.0):
        """Log keyword expansion for debugging and analytics."""
        log_entry = {
            "original": original,
            "expanded": expanded,
            "method": method,
            "confidence": confidence,
            "timestamp": datetime.now().isoformat()
        }
        self.expansion_history.append(log_entry)
        
        # Save log periodically
        if len(self.expansion_history) % 10 == 0:
            self._save_expansion_log()
    
    def _save_expansion_log(self):
        """Save expansion history to SQLite (delete-all + re-insert last 100),
        with JSON fallback. Non-critical analytics — skip silently when DB unavailable."""
        try:
            db = _get_db()
            if db is not None:
                session = db.get_db_session()
                try:
                    session.query(db.ExpansionLogEntry).delete()
                    for entry in self.expansion_history[-100:]:
                        session.add(db.ExpansionLogEntry(
                            original=entry.get("original", ""),
                            expanded=entry.get("expanded", ""),
                            method=entry.get("method", ""),
                            confidence=entry.get("confidence", 0.0),
                            timestamp=entry.get("timestamp", ""),
                        ))
                    session.commit()
                except Exception:
                    session.rollback()
                    raise
                finally:
                    session.close()
            else:
                # JSON fallback — write last 100 entries
                log_file = LOGS_DIR / "keyword_expansion.json"
                with open(log_file, "w", encoding="utf-8") as f:
                    json.dump(self.expansion_history[-100:], f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error("Error saving expansion log: %s", e)
    
    def get_expansion_stats(self) -> Dict:
        """Get statistics about keyword expansions."""
        if not self.expansion_history:
            return {"total_expansions": 0, "methods": {}, "success_rate": 0}
        
        total = len(self.expansion_history)
        methods = {}
        successful = 0
        
        for entry in self.expansion_history:
            method = entry["method"]
            methods[method] = methods.get(method, 0) + 1
            if entry["original"] != entry["expanded"]:
                successful += 1
        
        return {
            "total_expansions": total,
            "methods": methods,
            "success_rate": (successful / total) * 100 if total > 0 else 0
        }


# Global instance
_expander = None

def get_keyword_expander() -> KeywordExpander:
    """Get the global keyword expander instance."""
    global _expander
    if _expander is None:
        _expander = KeywordExpander()
    return _expander

def expand_user_input(text: str) -> str:
    """Convenience function to expand user input."""
    expander = get_keyword_expander()
    return expander.expand_text(text)

def warmup_keyword_expander():
    """Pre-warm the keyword expander on app startup (reduces cold-start latency)."""
    try:
        expander = get_keyword_expander()
        expander.warmup()
        logger.info("Keyword expander warmup completed")
    except Exception as e:
        logger.warning("Could not warmup keyword expander: %s", e)
