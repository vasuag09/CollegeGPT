import sys
import os
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

def test_embeddings():
    print("--- Testing Embeddings ---")
    try:
        # Single query
        q_vec = embed_query("What is the student handbook?")
        print(f"Query embedding success! Size: {len(q_vec)}")
        
        # Batch texts
        t_vecs = embed_texts(["Paragraph one about college.", "Paragraph two about fees."])
        print(f"Batch embedding success! Count: {len(t_vecs)}")
        return True
    except Exception as e:
        print(f"Embeddings failed: {e}")
        return False

def test_llm():
    print("\n--- Testing LLM ---")
    try:
        response = generate("Say 'The DNS fix is working!'")
        print(f"LLM Success! Response: {response}")
        return True
    except Exception as e:
        print(f"LLM failed: {e}")
        return False

if __name__ == "__main__":
    # Force .env loading from project root
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=PROJECT_ROOT / ".env")

    from backend.embeddings import embed_query, embed_texts
    from backend.llm_client import generate

    emb_ok = test_embeddings()
    llm_ok = test_llm()

    if emb_ok and llm_ok:
        print("\n✅ API Verification PASSED!")
        sys.exit(0)
    else:
        print("\n❌ API Verification FAILED!")
        sys.exit(1)
