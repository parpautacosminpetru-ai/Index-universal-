import sqlite3
import tempfile
import unittest
from pathlib import Path

from index_universal.db import IndexDB


class UniversalIndexTests(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory()
        self.home=Path(self.t.name)
        self.db=IndexDB(self.home/"library")

    def tearDown(self):
        self.db.close()
        self.t.cleanup()

    def test_zero_data_no_invented_results(self):
        self.assertEqual(self.db.matches("Europa"),[])
        self.assertEqual(self.db.stats()["relations"],0)

    def test_unique_nodes_and_mirrored_access_without_second_relation(self):
        rid=self.db.relation("Clovis","a activat în","Europa",context="Galia, secolele V–VI",qualities=[("perioadă","V–VI")])
        self.assertEqual(rid,self.db.relation("Clovis","a activat în","Europa",context="Galia, secolele V–VI"))
        self.assertEqual(self.db.stats()["relations"],1)
        self.assertEqual(len(self.db.matches("Clovis")),1)
        self.assertEqual(len(self.db.matches("Europa")),1)
        self.assertEqual(self.db.matches("Europa")[0]["subject"],"Clovis")
        self.assertEqual(self.db.matches("Europa")[0]["object"],"Europa")

    def test_dynamic_criteria_and_query(self):
        self.db.relation("Clovis","rege în","Europa",qualities=[("dinastie","merovingiană"),("interval","secolele V–VI")])
        self.assertEqual(len(self.db.matches("Europa merovingiană")),1)
        self.assertEqual(len(self.db.matches("Europa secolele")),1)
        self.assertEqual(len(self.db.matches("Europa China")),0)

    def test_source_anchor_without_duplicate_provenance(self):
        source_file=self.home/"proba.txt"
        source_file.write_text("Un paragraf original.",encoding="utf-8")
        src=self.db.source(source_file,title="Sursa A",creator="Autorul")
        a=self.db.anchor(src,14,15,"2","3","Un paragraf original")
        self.assertEqual(a,self.db.anchor(src,14,15,"2","3","Un paragraf original"))
        rid=self.db.relation("Paragraf în sursa A","face parte din","Capitolul 1",anchor_id=a)
        self.db.attach_relation(rid,a)
        self.assertEqual(len(self.db.evidence_for_relation(rid)),1)
        self.assertEqual(self.db.evidence_for_relation(rid)[0]["paragraph"],"2")
        nid=self.db.node("Paragraf în sursa A")
        self.db.attach_node(nid,a)
        self.assertEqual(len(self.db.evidence_for_node(nid)),1)

    def test_interpretation_does_not_merge_with_explicit(self):
        self.db.relation("A","implică","B",status="explicit")
        self.db.relation("A","implică","B",status="interpretare")
        self.assertEqual(len(self.db.matches("A")),2)

    def test_renamed_node_keeps_relations_and_search(self):
        self.db.relation("Clovis","a activat în","Europa")
        n=self.db.get_node("Clovis")
        self.db.rename_node(n["id"],"Clovis I")
        self.assertEqual(len(self.db.matches("Clovis I")),1)
        self.assertEqual(self.db.matches("Europa")[0]["subject"],"Clovis I")
        self.assertIsNone(self.db.get_node("Clovis"))

    def test_export_and_restore_with_copied_local_sources(self):
        source_file=self.home/"original.txt"
        source_file.write_text("Text de referință.",encoding="utf-8")
        s=self.db.source(source_file,copy_in=True)
        a=self.db.anchor(s,1,1,exact_text="Text de referință")
        self.db.relation("Text de referință","apare în","Prima pagină",anchor_id=a)
        archive=self.home/"backup.zip"
        self.db.export_zip(archive)
        self.db.relation("Înregistrare temporară","este","alt nod")
        self.db.restore_zip(archive)
        self.assertEqual(len(self.db.matches("Înregistrare temporară")),0)
        self.assertEqual(len(self.db.matches("Text de referință")),1)
        rid=self.db.matches("Text de referință")[0]["id"]
        evidence=self.db.evidence_for_relation(rid)
        self.assertTrue(Path(evidence[0]["file_path"]).is_file())

    def test_source_metadata_and_indexed_exact_locator_are_searchable(self):
        srcfile=self.home/"carte.txt"
        srcfile.write_text("pasaj izvor pentru index",encoding="utf-8")
        sid=self.db.source(srcfile,title="Carte de istorie",creator="Autor")
        anchor=self.db.anchor(sid,9,paragraph="trei",exact_text="pasaj izvor")
        rid=self.db.relation("Text original","este citat în","Lucrare",anchor_id=anchor)
        self.assertEqual(len(self.db.matches("pasaj izvor")),1)
        self.assertEqual(len(self.db.matches("Autor")),1)
        self.db.update_source(sid,"Carte de istorie","Autor revizuit","ediția a doua")
        self.assertEqual(len(self.db.matches("revizuit")),1)
        self.assertEqual(len(self.db.matches("doua")),1)

    def test_managed_source_copies_deduplicate_identical_bytes(self):
        a=self.home/"a.txt"
        b=self.home/"b.txt"
        a.write_text("Aceeași sursă.",encoding="utf-8")
        b.write_text("Aceeași sursă.",encoding="utf-8")
        first=self.db.source(a,copy_in=True)
        second=self.db.source(b,copy_in=True)
        self.assertEqual(first,second)
        self.assertEqual(len(self.db.sources()),1)

    def test_mnemonic_grid_extensible_canonical_references_and_renaming(self):
        gid=self.db.mnemonic_grid("Memorie universală",columns=6)
        self.assertEqual(gid,self.db.mnemonic_grid("Memorie universală",columns=6))
        self.assertEqual(self.db.mnemonic_extend(gid,12),12)
        self.assertEqual(self.db.mnemonic_extend(gid,50),62)
        self.assertEqual(self.db.mnemonic_cell_count(gid),62)
        self.db.relation("Clovis I","a activat în","Europa")
        self.db.mnemonic_assign(gid,9,"Europa",cue="Imagine mentală a continentului",
                                place_cue="Arca de sus",time_cue="Secolul VI, doar reper")
        slot=self.db.mnemonic_cell(gid,9)
        self.assertEqual(slot["node_title"],"Europa")
        self.assertEqual(slot["place_cue"],"Arca de sus")
        self.assertEqual(self.db.stats()["nodes"],2)
        self.assertEqual(self.db.stats()["relations"],1)
        self.assertEqual(len(self.db.mnemonic_places_for_node(self.db.get_node("Europa")["id"])),1)
        self.db.rename_node(self.db.get_node("Europa")["id"],"Europa (continent)")
        self.assertEqual(self.db.mnemonic_cell(gid,9)["node_title"],"Europa (continent)")
        self.assertEqual(len(self.db.matches("Europa (continent)")),1)

    def test_mnemonic_cells_no_invented_nodes_and_backup(self):
        gid=self.db.mnemonic_grid("Loci",columns=10)
        self.db.mnemonic_extend(gid,3)
        with self.assertRaises(ValueError):
            self.db.mnemonic_assign(gid,1,"Nod inexistent")
        with self.assertRaises(ValueError):
            self.db.mnemonic_assign(gid,9,None)
        self.db.node("Pagina 45")
        self.db.mnemonic_assign(gid,1,"Pagina 45",cue="Fața foii")
        archive=self.home/"memory.zip"
        self.db.export_zip(archive)
        self.db.mnemonic_assign(gid,1,None)
        self.db.restore_zip(archive)
        gid2=self.db.mnemonic_grids()[0]["id"]
        self.assertEqual(self.db.mnemonic_cell(gid2,1)["node_title"],"Pagina 45")
        self.assertEqual(self.db.mnemonic_cell(gid2,1)["cue"],"Fața foii")

    def test_direct_access_does_not_infer_transitive_facts(self):
        self.db.relation("Paris","se află în","Franța")
        self.db.relation("Franța","se află în","Europa")
        europe=self.db.matches("Europa")
        self.assertEqual(len(europe),1)
        self.assertEqual(europe[0]["subject"],"Franța")


if __name__=="__main__":
    unittest.main()
