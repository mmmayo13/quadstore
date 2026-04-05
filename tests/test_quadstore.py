import sys
import os
import unittest
import tempfile

# Add the src directory to the path so we can import quadstore for testing
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from quadstore import QuadStore

class TestQuadStore(unittest.TestCase):
    def setUp(self):
        self.qs = QuadStore()

    def test_add_and_len(self):
        self.assertEqual(len(self.qs), 0)
        self.qs.add("S1", "P1", "O1", "C1")
        self.assertEqual(len(self.qs), 1)
        
        # Adding duplicate should not increase length
        self.qs.add("S1", "P1", "O1", "C1")
        self.assertEqual(len(self.qs), 1)

    def test_query_single_dimension(self):
        self.qs.batch_add([
            ("LeBron", "plays_for", "Lakers", "2023"),
            ("LeBron", "scored", "30", "2023"),
            ("Curry", "plays_for", "Warriors", "2023")
        ])
        # Test Subject
        self.assertEqual(len(self.qs.query(subject="LeBron")), 2)
        self.assertEqual(len(self.qs.query(subject="Jordan")), 0)
        # Test Predicate
        self.assertEqual(len(self.qs.query(predicate="plays_for")), 2)
        # Test Object
        self.assertEqual(len(self.qs.query(object="Lakers")), 1)
        # Test Context
        self.assertEqual(len(self.qs.query(context="2023")), 3)

    def test_query_multiple_dimensions(self):
        self.qs.batch_add([
            ("LeBron", "plays_for", "Lakers", "2023"),
            ("LeBron", "scored", "30", "2023"),
            ("Curry", "plays_for", "Warriors", "2023"),
            ("LeBron", "plays_for", "Cavaliers", "2018")
        ])
        results = self.qs.query(subject="LeBron", predicate="plays_for")
        self.assertEqual(len(results), 2)
        
        results = self.qs.query(subject="LeBron", context="2023")
        self.assertEqual(len(results), 2)

        results = self.qs.query(subject="LeBron", predicate="plays_for", object="Lakers")
        self.assertEqual(len(results), 1)
        
        results = self.qs.query(subject="LeBron", predicate="plays_for", object="Lakers", context="2023")
        self.assertEqual(len(results), 1)

    def test_remove(self):
        self.qs.add("S1", "P1", "O1", "C1")
        self.qs.remove("S1", "P1", "O1", "C1")
        self.assertEqual(len(self.qs), 0)
        self.assertEqual(len(self.qs.query(subject="S1")), 0)

        # Removing non-existent should not crash
        self.qs.remove("Non", "Existent", "Quad", "Here")
        self.assertEqual(len(self.qs), 0)

    def test_batch_remove(self):
        self.qs.batch_add([
            ("LeBron", "plays_for", "Lakers", "2023"),
            ("Curry", "plays_for", "Warriors", "2023")
        ])
        self.qs.batch_remove([
            ("LeBron", "plays_for", "Lakers", "2023"),
            ("Not", "Real", "Data", "123")
        ])
        self.assertEqual(len(self.qs), 1)

    def test_update(self):
        self.qs.add("S1", "P1", "O1", "C1")
        self.qs.update("S1", "P1", "O1", "NEW_O1", "C1")
        
        results = self.qs.query(subject="S1")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][2], "NEW_O1")

    def test_clear(self):
        self.qs.add("S1", "P1", "O1", "C1")
        self.qs.clear()
        self.assertEqual(len(self.qs), 0)
        self.assertEqual(len(self.qs._str_to_id), 0)
        self.assertEqual(len(self.qs._id_to_str), 0)

    def test_save_and_load(self):
        original_quads = [
            ("S1", "P1", "O1", "C1"),
            ("S2", "P2", "O2", "C2")
        ]
        self.qs.batch_add(original_quads)
        
        # Use a temporary file so we don't rely on hardcoded jsonl files
        with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.jsonl') as temp_file:
            temp_filename = temp_file.name
            
        try:
            self.qs.save_to_file(temp_filename)
            
            loaded_qs = QuadStore.load_from_file(temp_filename)
            self.assertEqual(len(loaded_qs), 2)
            
            results = loaded_qs.query()
            self.assertIn(("S1", "P1", "O1", "C1"), results)
            self.assertIn(("S2", "P2", "O2", "C2"), results)
        finally:
            if os.path.exists(temp_filename):
                os.remove(temp_filename)

    def test_load_nonexistent_file(self):
        # Should gracefully handle loading a file that doesn't exist
        loaded_qs = QuadStore.load_from_file("definitely_does_not_exist_12345.jsonl")
        self.assertEqual(len(loaded_qs), 0)

if __name__ == '__main__':
    unittest.main()
