import sys
import os

# Add the src directory to the path so we can import quadstore for testing
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from quadstore import QuadStore

def main():
    qs = QuadStore()
    
    # Batch add
    qs.batch_add([
        ("LeBron James", "scored", "27.4", "2019"),
        ("LeBron James", "scored", "25.3", "2020"),
        ("Kevin Durant", "scored", "26.0", "2019")
    ])

    print("All quads:")
    print(qs.query())

    print("\nQueries by subject:")
    print(qs.query(subject="LeBron James"))

    print("\nQueries by predicate:")
    print(qs.query(predicate="scored"))

    print("\nQueries by object:")
    print(qs.query(object="26.0"))

    print("\nQueries by context:")
    print(qs.query(context="2019"))

    print("\nQueries with multiple parameters:")
    print(qs.query(subject="LeBron James", context="2019"))

    # Demonstrate saving and loading
    filename = "basketball_stats.jsonl"
    qs.save_to_file(filename)
    loaded_qs = QuadStore.load_from_file(filename)
    print("\nLoaded quads:")
    print(loaded_qs.query())

    # Clean up the example file after demonstrating
    if os.path.exists(filename):
        os.remove(filename)

if __name__ == "__main__":
    main()
