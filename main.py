import sys
import subprocess
import requests
import spacy
import argparse
import chromadb
from chromadb.config import Settings
from quadstore import QuadStore

# Global spaCy model to avoid repeated loading
nlp = None

# NBA 2023 stats data file
NBA_2023_STATS_FILE = "data/nba_stats_2023_quads.jsonl"

def get_nlp():
    global nlp
    if nlp is None:
        nlp = spacy.load("en_core_web_sm")
    return nlp

def quit(msg, code):
    print(f"\n[ERROR] System exited with error code {code}: {msg}")
    sys.exit(code)

def query_llama(system_prompt, user_query, model_name="llama3.2"):
    """
    Note: If using Llama 3, make sure Ollama is running locally with the Llama 3 model loaded. You can start it with: ollama run llama3.2
    """
    OLLAMA_API_URL = "http://localhost:11434/api/chat"
    data = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_query}
        ],
        "stream": False
    }
    response = requests.post(OLLAMA_API_URL, json=data)
    if response.status_code == 200:
        return response.json()["message"]["content"]
    else:
        return f"Error: {response.status_code} - {response.text}"

def extract_entities(text):
    """
    Extract entities from the given text using spaCy. Using set eliminates duplicates.
    """
    doc = get_nlp()(text)
    return list(set([ent.text for ent in doc.ents]))

def get_facts(qs, entities):
    """
    Retrieve facts for a list of entities from the QuadStore, querying both subjects and objects.
    """
    facts = []
    for entity in entities:
        subject_facts = qs.query(subject=entity)
        object_facts = qs.query(object=entity)
        facts.extend(subject_facts + object_facts)
    # Convert each fact (which is a list) to a tuple so it can be hashed
    return list(set(tuple(fact) for fact in facts))

def create_system_prompt(facts, stats, info):
    # Try formatting facts and stats into declarative sentences
    formatted_facts = "\n".join([f"In {q[3]}, {q[0]} {str(q[1]).replace('_', ' ')} {q[2]}." if len(q) >= 4 else str(q) for q in facts])
    formatted_stats = "\n".join([f"In {q[3]}, {q[0]} {str(q[1]).replace('_', ' ')} {q[2]}." if len(q) >= 4 else str(q) for q in stats])

    # Convert retrieved info dict to a string of text documents
    retrieved_context = ""
    if info and 'documents' in info and info['documents']:
        retrieved_context = " ".join(info['documents'][0])

    return f"""You are a strict data-retrieval AI. Your ONLY knowledge comes from the text provided below. You must completely ignore your internal training weights.
    
PRIORITY RULES (strict):
1. If Priority 1 (Facts) contains a direct answer, use ONLY that answer. Do not supplement, qualify, or cross-reference with Priority 2 or Vector data.
2. Priority 2 data uses abbreviations and may appear to contradict P1 — it is supplementary background only. Never treat P2 team abbreviations as authoritative team names if P1 states a team.
3. Only use P2 if P1 has no relevant answer on the specific attribute asked.
4. If Priority 3 (Vector Chunks) provides any additional relevant information, use your judgment as to whether or not to include it in the response.
5. If none of the sections contain the answer, you must explicitly say "I do not have enough information." Do not guess or hallucinate.

Your output **MUST** follow these rules:
- Provide only the single authoritative answer based on the priority rules.
- Do not present multiple conflicting answers.
- Make no mention of the source of this data.
- Phrase this in the form of a sentence or multiple sentences, as is appropriate.

---
[PRIORITY 1 - ABSOLUTE GRAPH FACTS]
{formatted_facts}

[Priority 2: Background Statistics (team abbreviations here are NOT authoritative — defer to Priority 1 for factual claims)]
{formatted_stats}

[PRIORITY 3 - VECTOR DOCUMENTS]
{retrieved_context}
---
"""

def main(args):
    user_prompt = args.prompt
    print("\n[SYSTEM]") 

    # Initialize Priority 1: Facts QuadStore
    facts_qs = QuadStore()
    facts_qs.add("LeBron James", "likes", "coconut milk", "NBA_trivia")
    facts_qs.add("LeBron James", "played_for", "Ottawa Beavers", "NBA_2023_regular_season")
    facts_qs.add("Ottawa Beavers", "obtained", "LeBron James", "2020_expansion_draft")
    facts_qs.add("Ottawa Beavers", "based_in", "downtown Ottawa", "NBA_trivia")
    facts_qs.add("Kevin Durant", "is", "a person", "NBA_trivia")
    facts_qs.add("Ottawa Beavers", "had", "worst first year of any expansion team in NBA history", "NBA_trivia")
    facts_qs.add("LeBron James", "average_mpg", "12.0", "NBA_2023_regular_season")
    
    print("  ○ Quadstore P1 ......................................... [LOADED]")

    # Initialize Priority 2: Stats QuadStore
    stats_qs = QuadStore()
    try:
        stats_qs = QuadStore.load_from_file(NBA_2023_STATS_FILE)
        print("  ○ Quadstore P2 ......................................... [LOADED]")
    except FileNotFoundError:
        print("  ● Quadstore P2 ......................................... [FAILED TO LOAD]")

    # Initialize Priority 3: Vector Embeddings
    chroma_client = chromadb.PersistentClient(
        path="./chroma_db",
        settings=Settings(anonymized_telemetry=False)
    )
    collection = chroma_client.get_or_create_collection(name="basketball")

    doc1 = (
        "LeBron injured for remainder of NBA 2023 season\n"
        "LeBron James suffered an ankle injury early in the season, which led to him playing far "
        "fewer minutes per game than he has recently averaged in other seasons. The injury got much "
        "worse today, and he is out for the rest of the season."
    )
    doc2 = (
        "Ottawa Beavers\n"
        "The Ottawa Beavers star player LeBron James is out for the rest of the 2023 NBA season, "
        "after his ankle injury has worsened. The teams' abysmal regular season record may end up "
        "being the worst of any team ever, with only 6 wins as of now, with only 4 gmaes left in "
        "the regular season."
    )

    collection.upsert(
        documents=[doc1, doc2],
        ids=["doc1", "doc2"]
    )

    if collection.count() == 0:
        print("  ● Vector DB ............................................ [EMPTY]")
    else:
        print(f"  ○ Vector DB ............................................ [LOADED with {collection.count()} docs]")

    print(f"\n[PROMPT] \"{user_prompt}\"")
    
    # Extract entities from user prompt
    user_entities = extract_entities(user_prompt)
    print("\n[ANALYSIS]")
    if user_entities:
        print(f"  └─ Entities: {', '.join(user_entities)}")
    else:
        print("  └─ Entities: [None extracted]")

    # Query Priority 1 facts
    facts_p1 = get_facts(facts_qs, user_entities)

    # Query Priority 2 stats
    facts_p2 = get_facts(stats_qs, user_entities)

    # Query Priority 3 embeddings
    vec_info = None
    if collection.count() > 0:
        vec_info = collection.query(
            query_texts=[" ".join(user_entities)],
            n_results=3
        )

    # Print UI formatting for knowledge retrieval
    print("\n[KNOWLEDGE RETRIEVAL]")

    # Priority 1 Block
    print("  ┌── Priority 1: High-Confidence Facts")
    if not facts_p1:
        print("  │   └─ [No facts found]")
    else:
        facts_by_ent = {}
        for q in facts_p1: 
            if len(q) >= 4:
                facts_by_ent.setdefault(q[0], []).append((q[1], q[2]))
        
        for ent in user_entities:
            if ent in facts_by_ent:
                print(f"  │   {ent}")
                items = facts_by_ent[ent]
                for i, (pred, obj) in enumerate(items):
                    prefix = "  │   └─" if i == len(items)-1 else "  │   ├─"
                    print(f"{prefix} {pred.replace('has_', '').replace('_', ' ')}: {obj}")
      
    print("  │")

    # Priority 2 Block
    print("  ├── Priority 2: General Statistics")
    if not facts_p2:
        print("  │   └─ [No stats found]")
    else:
        stats_by_ent = {}
        for q in facts_p2:
            if len(q) >= 4:
                stats_by_ent.setdefault(q[0], []).append((q[1], q[2]))
        
        for ent in user_entities:
            if ent in stats_by_ent:
                items = stats_by_ent[ent]
                team = next((obj for p, obj in items if 'plays_for' in p), "N/A")
                pos = next((obj for p, obj in items if 'plays_as' in p), "N/A")
                print(f"  │   {ent} ({team} / {pos})")
                
                stats_only = [(p, obj) for p, obj in items if 'plays_' not in p]
                # Chunk into grid
                for i in range(0, len(stats_only), 4):
                    chunk = stats_only[i:i+4]
                    prefix = "  │   └─" if i + 4 >= len(stats_only) else "  │   ├─"
                    formatted_chunk = " │ ".join([f"{p.replace('has_', '').upper()}: {obj}".ljust(14) for p, obj in chunk])
                    print(f"{prefix} {formatted_chunk}")

    print("  │")

    # Priority 3 Block
    print("  └── Vector Search: Supporting Documents")
    if not vec_info or not vec_info.get('documents') or not vec_info['documents'][0]:
        print("      └─ [No relevant chunks found in database]")
    else:
        docs = vec_info['documents'][0]
        for i, doc in enumerate(docs):
            prefix = "      └─" if i == len(docs)-1 else "      ├─"
            print(f"{prefix} {doc}")

    # Create system prompt
    system_prompt = create_system_prompt(facts_p1, facts_p2, vec_info)

    # Query LLM
    print("\n[EXECUTION]")
    print("  ● Querying model...")
        
    print("\n[RESPONSE]")
    response = query_llama(system_prompt, user_prompt, model_name=args.model)
    print(f"{response}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Query QuadStore and LLM with an initial prompt.")
    parser.add_argument("prompt", nargs="+", help="The user prompt to query.")
    parser.add_argument("--model", type=str, default="llama3.2", help="Ollama model to use.")
    
    args = parser.parse_args()
    args.prompt = " ".join(args.prompt)
    main(args)
