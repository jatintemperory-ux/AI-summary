""" AI Summary Tool — Flask Web Application
Extracts text from .txt, .pdf, .docx files and generates main points + summary 
using multi-algorithm consensus (LSA + TextRank + LexRank) with redundancy removal.
"""

import os
import re
import ssl
import uuid
import math
from collections import Counter

# Fix SSL certificate issue for NLTK downloads on macOS
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

import nltk
from flask import Flask, render_template, request, jsonify
from PyPDF2 import PdfReader
from docx import Document
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer
from nltk.tokenize import sent_tokenize, word_tokenize

from sumy.parsers.plaintext import PlaintextParser
from sumy.nlp.tokenizers import Tokenizer
from sumy.summarizers.lsa import LsaSummarizer
from sumy.summarizers.text_rank import TextRankSummarizer
from sumy.summarizers.lex_rank import LexRankSummarizer
from sumy.nlp.stemmers import Stemmer
from sumy.utils import get_stop_words

# ---------------------------------------------------------------------------
# NLTK data downloads (one-time, silent)
# ---------------------------------------------------------------------------
for resource, path in [
    ("punkt", "tokenizers/punkt"),
    ("punkt_tab", "tokenizers/punkt_tab"),
    ("stopwords", "corpora/stopwords"),
    ("wordnet", "corpora/wordnet"),
]:
    try:
        nltk.data.find(path)
    except LookupError:
        nltk.download(resource, quiet=True)

# Cache stopwords set (loaded once)
STOP_WORDS_EN = set(stopwords.words("english"))
LEMMATIZER = WordNetLemmatizer()

# ---------------------------------------------------------------------------
# Flask app setup
# ---------------------------------------------------------------------------
app = Flask(__name__)
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ALLOWED_EXTENSIONS = {".txt", ".pdf", ".docx"}

# ---------------------------------------------------------------------------
# Text extraction helpers
# ---------------------------------------------------------------------------
def extract_text_from_txt(file_path: str) -> str:
    """Extracts text from a .txt file."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"Error reading TXT file: {e}"

def extract_text_from_pdf(file_path: str) -> str:
    """Extracts text from a .pdf file."""
    try:
        text = ""
        with open(file_path, "rb") as f:
            reader = PdfReader(f)
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        return text
    except Exception as e:
        return f"Error reading PDF file: {e}"

def extract_text_from_docx(file_path: str) -> str:
    """Extracts text from a .docx file."""
    try:
        document = Document(file_path)
        text = [paragraph.text for paragraph in document.paragraphs]
        return "\n".join(text)
    except Exception as e:
        return f"Error reading DOCX file: {e}"

def extract_text(file_path: str) -> str:
    """Determines file type and extracts text using the appropriate function."""
    if not os.path.exists(file_path):
        return f"Error: File not found at {file_path}"
    
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".txt":
        return extract_text_from_txt(file_path)
    elif ext == ".pdf":
        return extract_text_from_pdf(file_path)
    elif ext == ".docx":
        return extract_text_from_docx(file_path)
    else:
        return f"Unsupported file type: {ext}. Only .txt, .pdf, and .docx are supported."

# ---------------------------------------------------------------------------
# Text cleaning — improve quality before summarization
# ---------------------------------------------------------------------------
def clean_text(text: str) -> str:
    """Clean raw extracted text for better summarization quality."""
    # Remove excessive whitespace / blank lines
    text = re.sub(r"\n\s*\n", "\n", text)
    # Collapse multiple spaces
    text = re.sub(r"[ \t]+", " ", text)
    
    # Remove very short lines that are likely headers / noise (< 4 words)
    lines = text.split("\n")
    cleaned_lines = []
    for line in lines:
        stripped = line.strip()
        # Keep lines with substantial content
        if len(stripped.split()) >= 3 or stripped.endswith("."):
            cleaned_lines.append(stripped)
        elif stripped:
            # Short line — append to previous if exists (likely a heading or fragment)
            if cleaned_lines:
                cleaned_lines[-1] += " " + stripped
            else:
                cleaned_lines.append(stripped)
                
    text = " ".join(cleaned_lines)
    # Ensure sentences end with proper punctuation for tokenizer
    text = re.sub(r"([a-zA-Z0-9])\n", r"\1. ", text)
    return text.strip()

# ---------------------------------------------------------------------------
# TF-IDF sentence scoring
# ---------------------------------------------------------------------------
def tokenize_words(sentence: str) -> list[str]:
    """Tokenize a sentence into cleaned, lemmatized words."""
    words = word_tokenize(sentence.lower())
    return [
        LEMMATIZER.lemmatize(w) 
        for w in words 
        if w.isalpha() and w not in STOP_WORDS_EN and len(w) > 2
    ]

def compute_tfidf_scores(sentences: list[str]) -> dict[int, float]:
    """Compute TF-IDF importance score for each sentence."""
    if not sentences:
        return {}
    
    # Tokenize each sentence
    sent_tokens = [tokenize_words(s) for s in sentences]
    n_docs = len(sentences)
    
    # Document frequency for each term
    df = Counter()
    for tokens in sent_tokens:
        for t in set(tokens):
            df[t] += 1
            
    # Compute TF-IDF score per sentence
    scores = {}
    for i, tokens in enumerate(sent_tokens):
        if not tokens:
            scores[i] = 0.0
            continue
        tf = Counter(tokens)
        score = 0.0
        for term, count in tf.items():
            tf_val = count / len(tokens)
            idf_val = math.log((n_docs + 1) / (df[term] + 1)) + 1
            score += tf_val * idf_val
        scores[i] = score
        
    return scores

# ---------------------------------------------------------------------------
# Sentence similarity for redundancy removal
# ---------------------------------------------------------------------------
def sentence_similarity(s1: str, s2: str) -> float:
    """Cosine similarity between two sentences based on word overlap."""
    w1 = set(tokenize_words(s1))
    w2 = set(tokenize_words(s2))
    if not w1 or not w2:
        return 0.0
    intersection = w1 & w2
    return len(intersection) / (math.sqrt(len(w1)) * math.sqrt(len(w2)))

def remove_redundant(sentences: list[str], threshold: float = 0.6) -> list[str]:
    """Remove sentences that are too similar to already-selected ones."""
    if not sentences:
        return []
        
    selected = [sentences[0]]
    for sent in sentences[1:]:
        is_redundant = False
        for existing in selected:
            if sentence_similarity(sent, existing) > threshold:
                is_redundant = True
                break
        if not is_redundant:
            selected.append(sent)
            
    return selected

# ---------------------------------------------------------------------------
# Multi-algorithm consensus summarization
# ---------------------------------------------------------------------------
def generate_summary_and_main_points(
    text: str,
    main_points_count: int = 3,
    summary_sentence_count: int = 5,
) -> tuple[list[str], str]:
    """
    Generate main points and summary using multi-algorithm consensus.
    Approach:
    1. Run 3 algorithms (LSA, TextRank, LexRank) independently
    2. Score each sentence by how many algorithms selected it
    3. Use TF-IDF as a tiebreaker for equal consensus scores
    4. Remove redundant sentences (cosine similarity > 0.6)
    5. Return diverse, high-quality key points and summary
    """
    if not text.strip():
        return [], "No content to summarize."
    
    # Clean the text first
    cleaned = clean_text(text)
    if not cleaned:
        return [], "No content to summarize."
        
    # Parse with sumy
    parser = PlaintextParser.from_string(cleaned, Tokenizer("english"))
    stemmer = Stemmer("english")
    stop_words = get_stop_words("english")
    
    # Get all sentences from the document
    all_sentences = [str(s) for s in parser.document.sentences]
    if not all_sentences:
        return [], "No sentences could be extracted from the document."
    
    # Request more sentences from each algorithm than needed,
    # so consensus has more to work with
    fetch_count = min(len(all_sentences), max(summary_sentence_count * 2, 10))
    
    # --- Run three summarization algorithms ---
    summarizers = {
        "lsa": LsaSummarizer(stemmer),
        "textrank": TextRankSummarizer(stemmer),
        "lexrank": LexRankSummarizer(stemmer),
    }
    
    for s in summarizers.values():
        s.stop_words = stop_words
        
    # Track which sentences each algorithm selected
    algo_results = {}
    for name, summarizer in summarizers.items():
        try:
            selected = [str(s) for s in summarizer(parser.document, fetch_count)]
            algo_results[name] = selected
        except Exception:
            algo_results[name] = []
            
    # --- Build consensus scores ---
    # Map sentence -> index in original order
    sent_to_idx = {s: i for i, s in enumerate(all_sentences)}
    
    # Count how many algorithms picked each sentence
    consensus = Counter()
    for name, selected in algo_results.items():
        for rank, sent in enumerate(selected):
            if sent in sent_to_idx:
                # Higher rank (lower index) = more important within that algo
                consensus[sent] += 1
                
    # Compute TF-IDF scores for all sentences as tiebreaker
    tfidf_scores = compute_tfidf_scores(all_sentences)
    
    # --- Rank sentences ---
    # Sort by: consensus count (desc), then TF-IDF score (desc), 
    # then original position (asc) for readability
    def sort_key(sent):
        idx = sent_to_idx.get(sent, 999)
        return (
            -consensus.get(sent, 0),    # more algorithms = better
            -tfidf_scores.get(idx, 0),  # higher TF-IDF = better
            idx,                        # earlier in doc = preferred
        )
        
    ranked_sentences = sorted(consensus.keys(), key=sort_key)
    
    # --- Generate main points (with redundancy removal) ---
    main_candidates = ranked_sentences[:main_points_count * 2]
    main_candidates = remove_redundant(main_candidates, threshold=0.55)
    
    # Re-sort by original document order for coherent reading
    main_points = sorted(
        main_candidates[:main_points_count],
        key=lambda s: sent_to_idx.get(s, 999),
    )
    
    # --- Generate summary (with redundancy removal) ---
    summary_candidates = ranked_sentences[:summary_sentence_count * 2]
    summary_candidates = remove_redundant(summary_candidates, threshold=0.5)
    
    summary_sents = sorted(
        summary_candidates[:summary_sentence_count],
        key=lambda s: sent_to_idx.get(s, 999),
    )
    summary = " ".join(summary_sents)
    
    # Fallback: if consensus produced nothing, use LSA directly
    if not main_points:
        lsa = LsaSummarizer(stemmer)
        lsa.stop_words = stop_words
        main_points = [str(s) for s in lsa(parser.document, main_points_count)]
        
    if not summary:
        lsa = LsaSummarizer(stemmer)
        lsa.stop_words = stop_words
        summary = " ".join(str(s) for s in lsa(parser.document, summary_sentence_count))
        
    return main_points, summary

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    """Serve the main UI page."""
    return render_template("index.html")

@app.route("/summarize", methods=["POST"])
def summarize():
    """Accept a file upload and return main points + summary as JSON."""
    # --- Validate file ---
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded."}), 400
        
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No file selected."}), 400
        
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return jsonify({
            "error": f"Unsupported file type: {ext}. Only .txt, .pdf, and .docx are supported."
        }), 400
        
    # --- Save temporarily ---
    safe_name = f"{uuid.uuid4().hex}{ext}"
    save_path = os.path.join(UPLOAD_FOLDER, safe_name)
    file.save(save_path)
    
    try:
        # --- Extract text ---
        text = extract_text(save_path)
        if text.startswith("Error"):
            return jsonify({"error": text}), 400
            
        if not text.strip():
            return jsonify({"error": "The file appears to be empty or contains no extractable text."}), 400
            
        # --- Read optional params ---
        main_points_count = int(request.form.get("main_points_count", 3))
        summary_sentence_count = int(request.form.get("summary_sentence_count", 5))
        
        # Clamp values
        main_points_count = max(1, min(main_points_count, 10))
        summary_sentence_count = max(1, min(summary_sentence_count, 10))
        
        # --- Generate summary ---
        main_points, summary = generate_summary_and_main_points(
            text,
            main_points_count=main_points_count,
            summary_sentence_count=summary_sentence_count,
        )
        
        return jsonify({
            "filename": file.filename,
            "main_points": main_points,
            "summary": summary,
            "word_count": len(text.split()),
            "char_count": len(text),
        })
    except Exception as e:
        return jsonify({"error": f"Summarization failed: {str(e)}"}), 500
    finally:
        # Clean up temp file
        if os.path.exists(save_path):
            os.remove(save_path)

# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_ENV") != "production"
    print(f"\n✨ AI Summary Tool is running at http://localhost:{port}\n")
    app.run(debug=debug, host="0.0.0.0", port=port)
