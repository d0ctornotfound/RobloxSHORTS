"""Fail-closed assembly contract tests; synthetic manifests are NOT production evidence."""
import json,tempfile,unittest
from pathlib import Path
from assemble_bench_release import verify

class ReleaseGate(unittest.TestCase):
    def test_missing_shots(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(AssertionError,"Missing release shots"):
                verify(Path(d),[{"shot":1}])
    def test_duplicate_shots(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(AssertionError,"Duplicate shot entries"):
                verify(Path(d),[{"shot":1},{"shot":1}],complete=False)
    def test_out_of_range(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(AssertionError):
                verify(Path(d),[{"shot":49}],complete=False)
    def test_missing_artifact(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(FileNotFoundError):
                verify(Path(d),[{"shot":1}],complete=False)
    def test_failed_chunk(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"shot_01";p.mkdir()
            e={"shot":1,"source_commit":"a"*40,"preflight_run":1}
            q={**e,"passed":False,"frames":60,"duration":2.5,"encoded_max_near_black_percent":0}
            for name,doc in (("chunk_validation.json",q),("manifest.json",{}),("geometry_all_frames.json",[])):
                (p/name).write_text(json.dumps(doc))
            with self.assertRaises(AssertionError):
                verify(Path(d),[e],complete=False)
    def test_wrong_provenance(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"shot_01";p.mkdir()
            e={"shot":1,"source_commit":"a"*40,"preflight_run":1}
            q={**e,"source_commit":"b"*40,"passed":True,"frames":60,"duration":2.5}
            for name,doc in (("chunk_validation.json",q),("manifest.json",{}),("geometry_all_frames.json",[])):
                (p/name).write_text(json.dumps(doc))
            with self.assertRaises(AssertionError):
                verify(Path(d),[e],complete=False)

if __name__=="__main__":
    unittest.main()
