"""Offline relational index. One canonical node/relation, many contextual access paths.

SQLite internal numeric identifiers are implementation details, never shown as user codes.
No information or relationship is inferred by the program.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import sqlite3
import zipfile
from datetime import datetime, timezone
from pathlib import Path


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def clean(value):
    return str(value or "").strip()


def join_location(anchor):
    if not anchor:
        return "Sursă neancorată"
    a, b = anchor["page_first"], anchor["page_last"]
    bits = [f"p. {a}" if a == b else f"pp. {a}–{b}"]
    if anchor["paragraph"]:
        bits.append(f"paragraf {anchor['paragraph']}")
    if anchor["line"]:
        bits.append(f"rând {anchor['line']}")
    return ", ".join(bits)


class IndexDB:
    def __init__(self, root):
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "index.sqlite3"
        self.sources_path = self.root / "surse"
        self.sources_path.mkdir(exist_ok=True)
        self.conn = sqlite3.connect(str(self.path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA busy_timeout=5000")
        self.init()

    def init(self):
        self.conn.executescript("""
        CREATE TABLE IF NOT EXISTS nodes (
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL UNIQUE COLLATE NOCASE,
            descriptor TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sources (
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            creator TEXT NOT NULL DEFAULT '',
            edition TEXT NOT NULL DEFAULT '',
            file_path TEXT NOT NULL UNIQUE,
            checksum TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS anchors (
            id INTEGER PRIMARY KEY,
            source_id INTEGER NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
            page_first INTEGER NOT NULL DEFAULT 1 CHECK(page_first>=1),
            page_last INTEGER NOT NULL DEFAULT 1 CHECK(page_last>=page_first),
            paragraph TEXT NOT NULL DEFAULT '',
            line TEXT NOT NULL DEFAULT '',
            exact_text TEXT NOT NULL DEFAULT '',
            UNIQUE(source_id,page_first,page_last,paragraph,line,exact_text)
        );
        CREATE TABLE IF NOT EXISTS relations (
            id INTEGER PRIMARY KEY,
            subject_id INTEGER NOT NULL REFERENCES nodes(id),
            predicate TEXT NOT NULL,
            object_id INTEGER NOT NULL REFERENCES nodes(id),
            context TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'explicit'
                 CHECK (status IN ('explicit','interpretare','inferență','de verificat')),
            created_at TEXT NOT NULL,
            UNIQUE(subject_id,predicate,object_id,context,status)
        );
        CREATE INDEX IF NOT EXISTS idx_subject ON relations(subject_id);
        CREATE INDEX IF NOT EXISTS idx_object ON relations(object_id);
        CREATE TABLE IF NOT EXISTS qualities (
            relation_id INTEGER NOT NULL REFERENCES relations(id) ON DELETE CASCADE,
            criterion TEXT NOT NULL,
            value TEXT NOT NULL,
            PRIMARY KEY (relation_id,criterion,value)
        );
        CREATE TABLE IF NOT EXISTS evidence (
            relation_id INTEGER NOT NULL REFERENCES relations(id) ON DELETE CASCADE,
            anchor_id INTEGER NOT NULL REFERENCES anchors(id) ON DELETE CASCADE,
            PRIMARY KEY(relation_id,anchor_id)
        );
        CREATE TABLE IF NOT EXISTS node_evidence (
            node_id INTEGER NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
            anchor_id INTEGER NOT NULL REFERENCES anchors(id) ON DELETE CASCADE,
            PRIMARY KEY(node_id,anchor_id)
        );
        -- Optional mnemonic scaffold: loci are addresses, never copies of facts.
        CREATE TABLE IF NOT EXISTS mnemonic_grids (
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL UNIQUE COLLATE NOCASE,
            columns INTEGER NOT NULL DEFAULT 6 CHECK(columns BETWEEN 2 AND 12),
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS mnemonic_cells (
            grid_id INTEGER NOT NULL REFERENCES mnemonic_grids(id) ON DELETE CASCADE,
            position INTEGER NOT NULL CHECK(position>0),
            node_id INTEGER REFERENCES nodes(id),
            cue TEXT NOT NULL DEFAULT '',
            place_cue TEXT NOT NULL DEFAULT '',
            time_cue TEXT NOT NULL DEFAULT '',
            PRIMARY KEY(grid_id,position)
        );
        CREATE INDEX IF NOT EXISTS idx_mnemonic_node ON mnemonic_cells(node_id);
        CREATE VIRTUAL TABLE IF NOT EXISTS relation_fts USING fts5(
            subject, predicate, object, context, qualifiers, sources,
            tokenize='unicode61 remove_diacritics 2'
        );
        CREATE VIRTUAL TABLE IF NOT EXISTS node_fts USING fts5(
            title, descriptor, sources, tokenize='unicode61 remove_diacritics 2'
        );
        """)
        if "checksum" not in [c["name"] for c in self.conn.execute("PRAGMA table_info(sources)").fetchall()]:
            self.conn.execute("ALTER TABLE sources ADD COLUMN checksum TEXT NOT NULL DEFAULT ''")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_source_hash ON sources(checksum)")
        if "sources" not in [c["name"] for c in self.conn.execute("PRAGMA table_info(relation_fts)").fetchall()]:
            self.conn.execute("DROP TABLE relation_fts")
            self.conn.execute("""CREATE VIRTUAL TABLE relation_fts USING fts5(
                subject, predicate, object, context, qualifiers, sources,
                tokenize='unicode61 remove_diacritics 2')""")
        if "sources" not in [c["name"] for c in self.conn.execute("PRAGMA table_info(node_fts)").fetchall()]:
            self.conn.execute("DROP TABLE node_fts")
            self.conn.execute("""CREATE VIRTUAL TABLE node_fts USING fts5(
                title, descriptor, sources, tokenize='unicode61 remove_diacritics 2')""")
        self.conn.commit()
        n=self.conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
        r=self.conn.execute("SELECT COUNT(*) FROM relations").fetchone()[0]
        nf=self.conn.execute("SELECT COUNT(*) FROM node_fts").fetchone()[0]
        rf=self.conn.execute("SELECT COUNT(*) FROM relation_fts").fetchone()[0]
        if n!=nf or r!=rf:
            self.rebuild_search()

    def close(self):
        self.conn.close()

    def transaction(self):
        return self.conn

    def get_node(self, title):
        return self.conn.execute(
            "SELECT * FROM nodes WHERE title=? COLLATE NOCASE", (clean(title),)
        ).fetchone()

    def node(self, title, descriptor=""):
        title = clean(title)
        if not title:
            raise ValueError("Denumirea informației nu poate fi goală.")
        with self.conn:
            self.conn.execute(
                "INSERT OR IGNORE INTO nodes(title,descriptor,created_at) VALUES(?,?,?)",
                (title,clean(descriptor),now())
            )
            found = self.get_node(title)
            if descriptor and not found["descriptor"]:
                self.conn.execute("UPDATE nodes SET descriptor=? WHERE id=?", (clean(descriptor),found["id"]))
            self.index_node(found["id"])
            return found["id"]

    def nodes(self):
        return self.conn.execute("SELECT * FROM nodes ORDER BY title COLLATE NOCASE").fetchall()

    def get_node_by_id(self, node_id):
        return self.conn.execute("SELECT * FROM nodes WHERE id=?",(node_id,)).fetchone()

    def source(self, filename, title=None, creator="", edition="", copy_in=False):
        path = Path(filename).expanduser().resolve()
        if not path.is_file():
            raise ValueError("Fișierul sursă nu există.")
        if path.suffix.lower() not in (".pdf",".txt"):
            raise ValueError("În această versiune sunt acceptate PDF și TXT.")
        found=self.conn.execute("SELECT id FROM sources WHERE file_path=?",(str(path),)).fetchone()
        if found:
            return found["id"]
        sha=hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda:f.read(1048576),b""):
                sha.update(chunk)
        checksum=sha.hexdigest()
        # For managed source copies, identical file bytes are stored exactly once.
        if copy_in:
            duplicate=self.conn.execute("SELECT id FROM sources WHERE checksum=? LIMIT 1",(checksum,)).fetchone()
            if duplicate:
                return duplicate["id"]
            candidate = self.sources_path / path.name
            counter = 1
            while candidate.exists() and candidate.resolve() != path:
                candidate = self.sources_path / f"{path.stem} ({counter}){path.suffix}"
                counter += 1
            if candidate.resolve() != path:
                shutil.copy2(path,candidate)
            path = candidate.resolve()
        with self.conn:
            self.conn.execute("""INSERT OR IGNORE INTO sources(title,creator,edition,file_path,checksum,created_at)
                VALUES(?,?,?,?,?,?)""",(clean(title) or path.stem,clean(creator),clean(edition),str(path),checksum,now()))
            return self.conn.execute("SELECT id FROM sources WHERE file_path=?",(str(path),)).fetchone()["id"]

    def update_source(self, source_id, title, creator="", edition=""):
        if not clean(title):
            raise ValueError("Sursa trebuie să aibă titlu.")
        with self.conn:
            self.conn.execute("UPDATE sources SET title=?,creator=?,edition=? WHERE id=?",
                              (clean(title),clean(creator),clean(edition),source_id))
            for row in self.conn.execute("""SELECT DISTINCT e.relation_id AS id FROM evidence e
               JOIN anchors a ON a.id=e.anchor_id WHERE a.source_id=?""",(source_id,)).fetchall():
                self.index_relation(row["id"])
            for row in self.conn.execute("""SELECT DISTINCT ne.node_id AS id FROM node_evidence ne
               JOIN anchors a ON a.id=ne.anchor_id WHERE a.source_id=?""",(source_id,)).fetchall():
                self.index_node(row["id"])

    def sources(self):
        return self.conn.execute("SELECT * FROM sources ORDER BY title COLLATE NOCASE").fetchall()

    def get_source(self, source_id):
        return self.conn.execute("SELECT * FROM sources WHERE id=?",(source_id,)).fetchone()

    def anchor(self, source_id, page_first=1, page_last=None, paragraph="", line="", exact_text=""):
        a, b = int(page_first),int(page_last or page_first)
        if a < 1 or b < a:
            raise ValueError("Intervalul de pagini este invalid.")
        if not self.get_source(source_id):
            raise ValueError("Sursa nu există.")
        fields=(source_id,a,b,clean(paragraph),clean(line),clean(exact_text))
        with self.conn:
            self.conn.execute("""INSERT OR IGNORE INTO anchors
              (source_id,page_first,page_last,paragraph,line,exact_text) VALUES(?,?,?,?,?,?)""",fields)
            return self.conn.execute("""SELECT id FROM anchors WHERE source_id=? AND page_first=?
              AND page_last=? AND paragraph=? AND line=? AND exact_text=?""", fields).fetchone()["id"]

    def get_anchor(self, anchor_id):
        return self.conn.execute("""SELECT a.*,s.title AS source_title,s.creator,s.edition,s.file_path
            FROM anchors a JOIN sources s ON s.id=a.source_id WHERE a.id=?""",(anchor_id,)).fetchone()

    def attach_node(self, node_id, anchor_id):
        with self.conn:
            self.conn.execute("INSERT OR IGNORE INTO node_evidence VALUES(?,?)",(node_id,anchor_id))
            self.index_node(node_id)

    def attach_relation(self, relation_id, anchor_id):
        with self.conn:
            self.conn.execute("INSERT OR IGNORE INTO evidence VALUES(?,?)",(relation_id,anchor_id))
            self.index_relation(relation_id)

    def relation(self, subject, predicate, obj, context="", status="explicit", qualities=None, anchor_id=None):
        subject, predicate, obj = clean(subject), clean(predicate), clean(obj)
        if not all([subject,predicate,obj]):
            raise ValueError("Sunt necesare două informații și relația dintre ele.")
        if status not in ("explicit","interpretare","inferență","de verificat"):
            raise ValueError("Statut invalid.")
        a,b = self.node(subject), self.node(obj)
        with self.conn:
            self.conn.execute("""INSERT OR IGNORE INTO relations
                (subject_id,predicate,object_id,context,status,created_at)
                VALUES(?,?,?,?,?,?)""",(a,predicate,b,clean(context),status,now()))
            rid=self.conn.execute("""SELECT id FROM relations WHERE subject_id=? AND predicate=?
                AND object_id=? AND context=? AND status=?""",(a,predicate,b,clean(context),status)).fetchone()["id"]
            for criterion,value in (qualities or []):
                if clean(criterion) and clean(value):
                    self.conn.execute("INSERT OR IGNORE INTO qualities VALUES(?,?,?)",(rid,clean(criterion),clean(value)))
            if anchor_id is not None:
                self.attach_relation(rid,anchor_id)
            self.index_relation(rid)
            return rid

    def qualities(self, relation_id):
        return self.conn.execute("SELECT criterion,value FROM qualities WHERE relation_id=? ORDER BY criterion,value",(relation_id,)).fetchall()

    def evidence_for_relation(self, relation_id):
        return self.conn.execute("""SELECT a.*,s.title AS source_title,s.creator,s.edition,s.file_path
            FROM evidence e JOIN anchors a ON a.id=e.anchor_id JOIN sources s ON s.id=a.source_id
            WHERE e.relation_id=? ORDER BY s.title,a.page_first,a.paragraph""",(relation_id,)).fetchall()

    def evidence_for_node(self, node_id):
        return self.conn.execute("""SELECT a.*,s.title AS source_title,s.creator,s.edition,s.file_path
            FROM node_evidence ne JOIN anchors a ON a.id=ne.anchor_id JOIN sources s ON s.id=a.source_id
            WHERE ne.node_id=? ORDER BY s.title,a.page_first""",(node_id,)).fetchall()

    def index_node(self, nid):
        n=self.get_node_by_id(nid)
        src=" ".join(" ".join([str(a["source_title"]),str(a["creator"]),str(a["edition"]),str(a["exact_text"]),str(a["paragraph"]),str(a["line"])])
                     for a in self.evidence_for_node(nid))
        self.conn.execute("DELETE FROM node_fts WHERE rowid=?",(nid,))
        self.conn.execute("INSERT INTO node_fts(rowid,title,descriptor,sources) VALUES(?,?,?,?)",
                          (nid,n["title"],n["descriptor"],src))

    def index_relation(self, rid):
        r=self.relation_by_id(rid)
        if not r:
            return
        q=" ".join(f"{v['criterion']} {v['value']}" for v in self.qualities(rid))
        sources=" ".join(" ".join([str(a["source_title"]),str(a["creator"]),str(a["edition"]),str(a["exact_text"]),str(a["paragraph"]),str(a["line"])])
                         for a in self.evidence_for_relation(rid))
        self.conn.execute("DELETE FROM relation_fts WHERE rowid=?",(rid,))
        self.conn.execute("""INSERT INTO relation_fts(rowid,subject,predicate,object,context,qualifiers,sources)
           VALUES(?,?,?,?,?,?,?)""",(rid,r["subject"],r["predicate"],r["object"],r["context"],q,sources))

    def rebuild_search(self):
        with self.conn:
            self.conn.execute("DELETE FROM node_fts")
            self.conn.execute("DELETE FROM relation_fts")
            for row in self.conn.execute("SELECT id FROM nodes").fetchall():
                self.index_node(row["id"])
            for row in self.conn.execute("SELECT id FROM relations").fetchall():
                self.index_relation(row["id"])

    def relation_by_id(self, relation_id):
        return self.conn.execute("""SELECT r.*,a.title AS subject,b.title AS object
           FROM relations r JOIN nodes a ON a.id=r.subject_id
           JOIN nodes b ON b.id=r.object_id WHERE r.id=?""",(relation_id,)).fetchone()

    def matches(self, query, limit=100, offset=0):
        """Returns stored relations only. Exact named node shows ALL direct edges, both directions.
        Other queries match all entered tokens through FTS5; no inferred paths.
        """
        query=clean(query)
        if not query:
            return []
        selected=self.get_node(query)
        if selected:
            rows=self.conn.execute("""SELECT r.*,a.title AS subject,b.title AS object
              FROM relations r JOIN nodes a ON a.id=r.subject_id JOIN nodes b ON b.id=r.object_id
              WHERE r.subject_id=? OR r.object_id=? ORDER BY a.title,b.title,r.predicate LIMIT ? OFFSET ?""",
              (selected["id"],selected["id"],limit,offset)).fetchall()
        else:
            words=re.findall(r"[^\W_]+",query,flags=re.UNICODE)
            if not words:
                return []
            expr=" ".join('"'+w.replace('"','')+'"*' for w in words[:25])
            try:
                rows=self.conn.execute("""SELECT r.*,a.title AS subject,b.title AS object
                  FROM relation_fts f JOIN relations r ON r.id=f.rowid
                  JOIN nodes a ON a.id=r.subject_id JOIN nodes b ON b.id=r.object_id
                  WHERE relation_fts MATCH ? ORDER BY rank LIMIT ? OFFSET ?""",(expr,limit,offset)).fetchall()
            except sqlite3.OperationalError:
                rows=[]
        return rows

    def count_matches(self, query):
        q=clean(query)
        if not q: return 0
        node=self.get_node(q)
        if node:
            return self.conn.execute("SELECT COUNT(*) AS n FROM relations WHERE subject_id=? OR object_id=?",(node["id"],node["id"])).fetchone()["n"]
        words=re.findall(r"[^\W_]+",q,flags=re.UNICODE)
        if not words: return 0
        expr=" ".join('"'+w.replace('"','')+'"*' for w in words[:25])
        try:
            return self.conn.execute("SELECT COUNT(*) AS n FROM relation_fts WHERE relation_fts MATCH ?",(expr,)).fetchone()["n"]
        except sqlite3.OperationalError:
            return 0

    def find_nodes(self, query, limit=20):
        q=clean(query)
        if not q: return []
        terms=re.findall(r"[^\W_]+",q,flags=re.UNICODE)
        if not terms: return []
        expr=" ".join('"'+w+'"*' for w in terms[:25])
        try:
            return self.conn.execute("""SELECT n.* FROM node_fts f
              JOIN nodes n ON n.id=f.rowid WHERE node_fts MATCH ? ORDER BY rank LIMIT ?""",(expr,limit)).fetchall()
        except sqlite3.OperationalError:
            return []

    # Hugh of St Victor-inspired memory loci: an optional projection of existing nodes.
    # Positions are mnemonic ordinal addresses, not public codes for knowledge items.
    def mnemonic_grid(self, title, columns=6):
        title=clean(title)
        columns=int(columns)
        if not title:
            raise ValueError("Grila mnemonică trebuie să aibă o denumire.")
        if not 2 <= columns <= 12:
            raise ValueError("Grila poate avea între 2 și 12 coloane.")
        with self.conn:
            self.conn.execute("INSERT OR IGNORE INTO mnemonic_grids(title,columns,created_at) VALUES(?,?,?)",
                              (title,columns,now()))
            return self.conn.execute("SELECT id FROM mnemonic_grids WHERE title=? COLLATE NOCASE",
                                     (title,)).fetchone()["id"]

    def mnemonic_grids(self):
        return self.conn.execute("SELECT * FROM mnemonic_grids ORDER BY title COLLATE NOCASE").fetchall()

    def mnemonic_grid_by_id(self, grid_id):
        return self.conn.execute("SELECT * FROM mnemonic_grids WHERE id=?",(grid_id,)).fetchone()

    def mnemonic_cell_count(self, grid_id):
        return self.conn.execute("SELECT COUNT(*) FROM mnemonic_cells WHERE grid_id=?",(grid_id,)).fetchone()[0]

    def mnemonic_extend(self, grid_id, count=12):
        count=int(count)
        if not 1 <= count <= 1000:
            raise ValueError("Adaugă între 1 și 1000 de celule odată.")
        if not self.mnemonic_grid_by_id(grid_id):
            raise ValueError("Grila nu există.")
        with self.conn:
            start=self.conn.execute("SELECT COALESCE(MAX(position),0) FROM mnemonic_cells WHERE grid_id=?",
                                    (grid_id,)).fetchone()[0]
            self.conn.executemany("INSERT INTO mnemonic_cells(grid_id,position) VALUES(?,?)",
                                  [(grid_id,start+i) for i in range(1,count+1)])
        return start+count

    def mnemonic_cell(self, grid_id, position):
        return self.conn.execute("""SELECT mc.*,n.title AS node_title
            FROM mnemonic_cells mc LEFT JOIN nodes n ON n.id=mc.node_id
            WHERE mc.grid_id=? AND mc.position=?""",(grid_id,int(position))).fetchone()

    def mnemonic_cells(self, grid_id, offset=0, limit=60):
        return self.conn.execute("""SELECT mc.*,n.title AS node_title
            FROM mnemonic_cells mc LEFT JOIN nodes n ON n.id=mc.node_id
            WHERE mc.grid_id=? ORDER BY mc.position LIMIT ? OFFSET ?""",
            (grid_id,int(limit),int(offset))).fetchall()

    def mnemonic_assign(self, grid_id, position, node_title=None, cue="", place_cue="", time_cue=""):
        """Bind a stable locus to an EXISTING node; no source or fact is duplicated."""
        if not self.mnemonic_cell(grid_id,position):
            raise ValueError("Celula nu există. Extinde mai întâi grila.")
        title=clean(node_title)
        node=self.get_node(title) if title else None
        if title and not node:
            raise ValueError("Fișa selectată nu există; creeaz-o în index mai întâi.")
        with self.conn:
            self.conn.execute("""UPDATE mnemonic_cells SET node_id=?,cue=?,place_cue=?,time_cue=?
                 WHERE grid_id=? AND position=?""",
                 (node["id"] if node else None,clean(cue),clean(place_cue),clean(time_cue),grid_id,int(position)))

    def mnemonic_places_for_node(self, node_id):
        return self.conn.execute("""SELECT g.id AS grid_id,g.title AS grid_title,mc.position,
                mc.cue,mc.place_cue,mc.time_cue
             FROM mnemonic_cells mc JOIN mnemonic_grids g ON g.id=mc.grid_id
             WHERE mc.node_id=? ORDER BY g.title,mc.position""",(node_id,)).fetchall()

    def stats(self):
        return {k:self.conn.execute(f"SELECT COUNT(*) FROM {k}").fetchone()[0]
                for k in ("nodes","relations","sources","anchors")}

    def export_zip(self, filename):
        """Creates a recoverable offline backup; original sources are not modified."""
        filename=Path(filename)
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            backup=Path(tmp)/"index.sqlite3"
            target=sqlite3.connect(str(backup))
            self.conn.backup(target)
            target.close()
            sources=self.sources()
            manifest=[]
            with zipfile.ZipFile(filename,"w",zipfile.ZIP_DEFLATED,compresslevel=6) as z:
                z.write(backup,"index.sqlite3")
                for s in sources:
                    p=Path(s["file_path"])
                    saved=f"surse/{s['id']}{p.suffix.lower()}"
                    if p.is_file():
                        z.write(p,saved)
                    else:
                        saved=None
                    manifest.append({"id":s["id"],"filename":str(p),"backup_path":saved})
                z.writestr("manifest.json",json.dumps({"version":1,"sources":manifest},ensure_ascii=False,indent=2))
        return filename

    def rename_node(self, node_id, title, descriptor=None):
        title=clean(title)
        if not title:
            raise ValueError("Denumirea informației nu poate fi goală.")
        with self.conn:
            if descriptor is None:
                self.conn.execute("UPDATE nodes SET title=? WHERE id=?",(title,node_id))
            else:
                self.conn.execute("UPDATE nodes SET title=?,descriptor=? WHERE id=?",(title,clean(descriptor),node_id))
            self.index_node(node_id)
            for r in self.conn.execute("SELECT id FROM relations WHERE subject_id=? OR object_id=?",(node_id,node_id)).fetchall():
                self.index_relation(r["id"])

    def update_relation(self, relation_id, subject, predicate, obj, context, status, qualities):
        a=self.node(subject)
        b=self.node(obj)
        if not clean(predicate):
            raise ValueError("Relația nu poate fi goală.")
        with self.conn:
            self.conn.execute("""UPDATE relations SET subject_id=?,predicate=?,object_id=?,context=?,status=? WHERE id=?""",
                              (a,clean(predicate),b,clean(context),status,relation_id))
            self.conn.execute("DELETE FROM qualities WHERE relation_id=?",(relation_id,))
            for criterion,value in qualities:
                if clean(criterion) and clean(value):
                    self.conn.execute("INSERT OR IGNORE INTO qualities VALUES(?,?,?)",
                                      (relation_id,clean(criterion),clean(value)))
            self.index_relation(relation_id)

    def delete_relation(self, relation_id):
        with self.conn:
            self.conn.execute("DELETE FROM relations WHERE id=?",(relation_id,))
            self.conn.execute("DELETE FROM relation_fts WHERE rowid=?",(relation_id,))

    def restore_zip(self, file_path):
        """Restore complete archive, with source paths rewritten for this machine.

        Existing data remain backed up until restoration succeeds. Caller must reload GUI.
        """
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            td=Path(td)
            with zipfile.ZipFile(file_path) as archive:
                names=set(archive.namelist())
                if "index.sqlite3" not in names or "manifest.json" not in names:
                    raise ValueError("Arhiva nu este o copie validă Index Universal.")
                data=json.loads(archive.read("manifest.json"))
                if data.get("version")!=1:
                    raise ValueError("Versiune de arhivă incompatibilă.")
                raw_db=td/"restored.sqlite3"
                raw_db.write_bytes(archive.read("index.sqlite3"))
                test=sqlite3.connect(str(raw_db))
                check=test.execute("PRAGMA integrity_check").fetchone()[0]
                if check!="ok":
                    test.close()
                    raise ValueError("Arhiva conține o bază deteriorată.")
                imported=td/"surse"
                imported.mkdir()
                suffix=datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
                restored_dir=self.root/f"surse-restaurate-{suffix}"
                for item in data["sources"]:
                    internal=item["backup_path"]
                    if internal:
                        if internal not in names or not internal.startswith("surse/"):
                            test.close();raise ValueError("Fișier sursă lipsă din arhivă.")
                        dest=imported/Path(internal).name
                        dest.write_bytes(archive.read(internal))
                        filepath=str(restored_dir/dest.name)
                    else:
                        filepath=item["filename"]
                    test.execute("UPDATE sources SET file_path=? WHERE id=?",(filepath,item["id"]))
                test.commit();test.close()
                safety=self.root/f"index-inainte-de-restaurare-{suffix}.sqlite3"
                old_backup=sqlite3.connect(str(safety))
                self.conn.backup(old_backup)
                old_backup.close()
                self.conn.close()
                try:
                    restored_dir.mkdir()
                    for file in imported.iterdir():
                        shutil.copy2(file,restored_dir/file.name)
                    for suffix in ("-wal","-shm"):
                        side=Path(str(self.path)+suffix)
                        if side.exists():side.unlink()
                    shutil.copy2(raw_db,self.path)
                    self.conn=sqlite3.connect(str(self.path))
                    self.conn.row_factory=sqlite3.Row
                    self.conn.execute("PRAGMA foreign_keys=ON")
                    self.conn.execute("PRAGMA journal_mode=WAL")
                    self.conn.execute("PRAGMA busy_timeout=5000")
                    self.rebuild_search()
                except Exception:
                    if safety.exists():
                        shutil.copy2(safety,self.path)
                    self.conn=sqlite3.connect(str(self.path))
                    self.conn.row_factory=sqlite3.Row
                    self.conn.execute("PRAGMA foreign_keys=ON")
                    raise
