import polars as pl
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from typing import List, Tuple, Dict, Any

class EntityMatchingEngine:
    """
    Implements Entity Matching (Phase 3) using TF-IDF token comparison 
    to detect duplicate or highly similar records referring to the same entity.
    """
    
    @staticmethod
    def detect_duplicates(lf: pl.LazyFrame, threshold: float = 0.95) -> List[Tuple[int, int, float]]:
        """
        Returns a list of tuples (row_idx_1, row_idx_2, similarity_score) 
        for records that are likely duplicates.
        """
        df = lf.collect()
        if len(df) < 2:
            return []
            
        # Serialize each row into a single string document
        # (similar to the Transformer-based serialization in the academic paper)
        documents = []
        columns = df.columns
        for row in df.iter_rows():
            # Combine all string/text attributes into a single token string
            doc = " ".join([f"{col}: {str(val)}" for col, val in zip(columns, row) if val is not None])
            documents.append(doc)
            
        # Token comparison via TF-IDF
        vectorizer = TfidfVectorizer(analyzer='word', stop_words='english')
        try:
            tfidf_matrix = vectorizer.fit_transform(documents)
        except ValueError:
            # Vocabulary empty (e.g. all stop words or numbers)
            return []
            
        # Compute cosine similarity
        cosine_sim = cosine_similarity(tfidf_matrix, tfidf_matrix)
        
        duplicates = []
        n = len(documents)
        for i in range(n):
            for j in range(i + 1, n):
                sim = cosine_sim[i, j]
                if sim >= threshold:
                    duplicates.append((i, j, float(sim)))
                    
        return duplicates
